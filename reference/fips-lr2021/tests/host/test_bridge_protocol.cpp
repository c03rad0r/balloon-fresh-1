// Host-side check of the C++ bridge protocol against the Rust wire format.
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

#include "../../firmware/rp2040-bridge/src/bridge_protocol.h"

int main() {
  BridgeFrame frame;
  uint8_t out[64];
  size_t n = bridgeEncode(BR_TX, (const uint8_t*)"hello", 5, out, sizeof(out));
  assert(n == 12);

  BridgeDecoder dec;
  assert(dec.push(out, 3));
  assert(!dec.next(frame));
  assert(dec.push(out + 3, n - 3));
  assert(dec.next(frame));
  assert(frame.kind == BR_TX);
  assert(frame.len == 5);
  assert(memcmp(frame.payload, "hello", 5) == 0);

  // Leading garbage resynchronizes.
  uint8_t garbage[3] = {0x00, 0x11, 0x22};
  BridgeDecoder dec2;
  dec2.push(garbage, 3);
  dec2.push(out, n);
  assert(dec2.next(frame));
  assert(frame.kind == BR_TX);

  CfgPayload cfg;
  cfg.frequency_hz = 915000000;
  cfg.bitrate_kbps = 1300;
  cfg.tx_power_dbm = 22;
  cfg.radio_payload = 255;
  cfg.relay = true;
  cfg.sub_ghz = true;
  uint8_t payload[15];
  payload[0] = cfg.band;
  payload[1] = (uint8_t)(cfg.frequency_hz);
  payload[2] = (uint8_t)(cfg.frequency_hz >> 8);
  payload[3] = (uint8_t)(cfg.frequency_hz >> 16);
  payload[4] = (uint8_t)(cfg.frequency_hz >> 24);
  payload[5] = (uint8_t)(cfg.bitrate_kbps);
  payload[6] = (uint8_t)(cfg.bitrate_kbps >> 8);
  payload[7] = (uint8_t)cfg.tx_power_dbm;
  memcpy(payload + 8, cfg.sync_word, 4);
  payload[12] = (uint8_t)cfg.radio_payload;
  payload[13] = (uint8_t)(cfg.radio_payload >> 8);
  payload[14] = 0x03;

  CfgPayload parsed;
  assert(cfgDecode(payload, sizeof(payload), parsed));
  assert(parsed.frequency_hz == 915000000);
  assert(parsed.bitrate_kbps == 1300);
  assert(parsed.radio_payload == 255);
  assert(parsed.relay);
  assert(parsed.sub_ghz);

  uint8_t ack[10];
  cfgAckEncode(0, parsed, ack);
  assert(ack[0] == 0);
  assert(ack[1] == (uint8_t)(915000000 & 0xFF));

  printf("bridge protocol host tests passed\n");
  return 0;
}
