/**
 * @file bridge.c
 * @brief E80 STM32F103 binary bridge for FIPS over LR2021/FLRC.
 *
 * Entered by the `BRIDGE` console command. It speaks the same host protocol as
 * the RP2040 reference firmware and uses the proven radio_bench driver, which
 * already selects LF/HF by frequency. The host owns fragmentation, ACK/ARQ and
 * FIPS framing; this file only moves raw radio packets.
 */

#include "bridge.h"

#include "main.h"
#include "console.h"
#include "radio_bench.h"

#include "bridge_protocol.h"

#include <string.h>

extern UART_HandleTypeDef huart1;

static bool active = false;
static BridgeDecoder decoder;
static CfgPayload cfg;
static radio_bench_cfg_t radio_cfg;

static uint32_t tx_packets = 0;
static uint32_t rx_packets = 0;
static uint32_t crc_errors = 0;
static uint32_t drops = 0;
static uint32_t tx_timeouts = 0;
static uint32_t resets = 0;
static uint32_t last_ok_ms = 0;
static uint32_t last_init_ms = 0;
static uint8_t chip_major = 0;
static uint8_t chip_minor = 0;

#define RELAY_CACHE 16
static uint32_t relay_hash[RELAY_CACHE];
static uint32_t relay_at[RELAY_CACHE];
static uint8_t relay_next = 0;

static void send_frame(uint8_t kind, const uint8_t* payload, uint16_t len)
{
    uint8_t out[BRIDGE_MAX_PAYLOAD + 16];
    size_t n = bridgeEncode(kind, payload, len, out, sizeof(out));
    if (n)
        HAL_UART_Transmit(&huart1, out, (uint16_t)n, 100);
}

static void send_event(const char* text)
{
    send_frame(BR_EVT, (const uint8_t*)text, (uint16_t)strlen(text));
}

static void send_stat(void)
{
    uint8_t p[24];
    uint32_t v[6] = {tx_packets, rx_packets, crc_errors, drops, tx_timeouts, resets};
    for (int i = 0; i < 6; i++)
    {
        p[i * 4 + 0] = (uint8_t)(v[i] & 0xFF);
        p[i * 4 + 1] = (uint8_t)((v[i] >> 8) & 0xFF);
        p[i * 4 + 2] = (uint8_t)((v[i] >> 16) & 0xFF);
        p[i * 4 + 3] = (uint8_t)((v[i] >> 24) & 0xFF);
    }
    send_frame(BR_STAT, p, sizeof(p));
}

static size_t frame_length(const uint8_t* data, size_t len)
{
    if (len < 20 || data[0] != 0xF1 || data[1] != 0x50 || (data[2] >> 4) != 1)
        return len;
    size_t payload = (size_t)data[18] | ((size_t)data[19] << 8);
    size_t total = 20 + payload + 4;
    return total <= len ? total : len;
}

static bool relay_duplicate(const uint8_t* data, size_t len)
{
    uint32_t h = 2166136261u;
    for (size_t i = 0; i < len; i++)
    {
        h ^= data[i];
        h *= 16777619u;
    }
    uint32_t now = HAL_GetTick();
    for (int i = 0; i < RELAY_CACHE; i++)
        if (relay_hash[i] == h && (now - relay_at[i]) < 2000)
            return true;
    relay_hash[relay_next] = h;
    relay_at[relay_next] = now;
    relay_next = (uint8_t)((relay_next + 1) % RELAY_CACHE);
    return false;
}

static void radio_tx(const uint8_t* data, size_t len)
{
    if (len == 0 || len > 255)
        return;
    if (radio_bench_tx_packet(data, (uint16_t)len, 100) != 0)
        tx_timeouts++;
    else
        tx_packets++;
    last_ok_ms = HAL_GetTick();
}

static bool apply_cfg(const CfgPayload* c)
{
    memset(&radio_cfg, 0, sizeof(radio_cfg));
    radio_cfg.mod = BENCH_MOD_FLRC;
    radio_cfg.cr = 1; /* 3/4 */
    radio_cfg.br_bps = (uint32_t)c->bitrate_kbps * 1000U;
    radio_cfg.txpow_dbm = c->tx_power_dbm;
    radio_cfg.freq_hz = c->frequency_hz;
    radio_cfg.bw_hz = 0;

    radio_bench_wakeup();
    if (radio_bench_apply_cfg(&radio_cfg) != 0)
    {
        send_event("radio cfg failed");
        return false;
    }
    radio_bench_rx_arm(255);
    last_init_ms = HAL_GetTick();
    last_ok_ms = last_init_ms;
    return true;
}

static void handle_hello(void)
{
    uint8_t p[8];
    p[0] = 1;
    p[1] = 0;
    p[2] = 1;
    p[3] = 0;
    p[4] = chip_major;
    p[5] = chip_minor;
    p[6] = 0x07; /* LF + HF + relay */
    p[7] = 0x00;
    send_frame(BR_HELLO_ACK, p, sizeof(p));
}

static void handle_cfg(const BridgeFrame* frame)
{
    CfgPayload next;
    if (!cfgDecode(frame->payload, frame->len, next) ||
        next.frequency_hz < 150000000UL || next.frequency_hz > 2500000000UL ||
        next.radio_payload < 32 || next.radio_payload > 255 ||
        (next.bitrate_kbps != 2600 && next.bitrate_kbps != 2080 &&
         next.bitrate_kbps != 1300 && next.bitrate_kbps != 650 &&
         next.bitrate_kbps != 325) ||
        next.tx_power_dbm < -18 || next.tx_power_dbm > 22)
    {
        uint8_t ack[10];
        cfgAckEncode(2, cfg, ack);
        send_frame(BR_CFG_ACK, ack, sizeof(ack));
        return;
    }
    cfg = next;
    bool ok = apply_cfg(&cfg);
    uint8_t ack[10];
    cfgAckEncode(ok ? 0 : 1, cfg, ack);
    send_frame(BR_CFG_ACK, ack, sizeof(ack));
}

static void handle_frame(const BridgeFrame* frame)
{
    switch (frame->kind)
    {
    case BR_HELLO:
        handle_hello();
        break;
    case BR_CFG:
        handle_cfg(frame);
        break;
    case BR_TX:
        radio_tx(frame->payload, frame->len);
        break;
    case BR_PING:
        send_frame(BR_PONG, 0, 0);
        send_stat();
        break;
    default:
        break;
    }
}

void bridge_start(void)
{
    if (active)
        return;
    active = true;
    decoder = BridgeDecoder();
    memset(&cfg, 0, sizeof(cfg));
    cfg.band = 2; /* us915 */
    cfg.frequency_hz = 915000000UL;
    cfg.bitrate_kbps = 1300;
    cfg.tx_power_dbm = 22;
    cfg.radio_payload = 255;
    cfg.relay = false;
    cfg.sub_ghz = true;
    memcpy(cfg.sync_word, "\x12\xAD\x10\x1B", 4);

    chip_major = radio_bench_chip_major;
    chip_minor = radio_bench_chip_minor;

    console_putln("OK BRIDGE 115200");
    (void)apply_cfg(&cfg);
}

bool bridge_active(void)
{
    return active;
}

void bridge_task(void)
{
    rb_evt_t evt;
    int c;

    while ((c = console_raw_get()) >= 0)
    {
        uint8_t byte = (uint8_t)c;
        if (!decoder.push(&byte, 1))
        {
            send_event("host frame overflow");
            continue;
        }
        BridgeFrame frame;
        while (decoder.next(frame))
            handle_frame(&frame);
    }

    while (radio_bench_poll_event(&evt))
    {
        switch (evt.type)
        {
        case RB_EVT_RX_OK:
        {
            size_t len = frame_length(radio_bench_rx_buf, evt.len);
            if (len)
            {
                uint8_t payload[6 + 255];
                int16_t rssi = (int16_t)(evt.rssi_half_dbm / 2);
                int8_t snr = (int8_t)(evt.snr_qdb / 4);
                payload[0] = (uint8_t)(rssi & 0xFF);
                payload[1] = (uint8_t)((rssi >> 8) & 0xFF);
                payload[2] = (uint8_t)snr;
                payload[3] = 1;
                payload[4] = (uint8_t)(len & 0xFF);
                payload[5] = (uint8_t)(len >> 8);
                memcpy(payload + 6, radio_bench_rx_buf, len);
                send_frame(BR_RX, payload, (uint16_t)(6 + len));
                rx_packets++;
                last_ok_ms = HAL_GetTick();

                if (cfg.relay && !relay_duplicate(radio_bench_rx_buf, len))
                    radio_tx(radio_bench_rx_buf, len);
            }
            break;
        }
        case RB_EVT_RX_CRC:
            crc_errors++;
            break;
        case RB_EVT_TX_DONE:
            radio_bench_rx_arm(255);
            last_ok_ms = HAL_GetTick();
            break;
        case RB_EVT_TX_TIMEOUT:
            tx_timeouts++;
            radio_bench_rx_arm(255);
            break;
        default:
            break;
        }
    }

    uint32_t now = HAL_GetTick();
    if ((now - last_ok_ms) > 15000 && (now - last_init_ms) > 60000)
    {
        resets++;
        send_event("watchdog reinit");
        (void)apply_cfg(&cfg);
    }
}
