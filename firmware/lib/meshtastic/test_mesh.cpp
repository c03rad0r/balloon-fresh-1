// TDD entry point for L4 (meshtastic transport).
//
// RED FIRST (2026-10-14): this file was committed BEFORE any implementation, and
// `make -C firmware/lib test` was run and failed to compile because none of the
// headers it includes existed yet. That observed build failure is the RED.
//
// The wire format reproduced here is Meshtastic's, taken from public sources
// fetched and read during this task (see REPORT.md for the exact URLs and SHAs):
//   - meshtastic/firmware  src/mesh/RadioInterface.h   (16-byte PacketHeader, flag masks)
//   - meshtastic/firmware  src/mesh/Channels.{h,cpp}   (defaultpsk, PSK expansion, xor hash)
//   - meshtastic/firmware  src/mesh/CryptoEngine.cpp   (nonce construction)
//   - meshtastic/firmware  src/mesh/RadioInterface.cpp (rebroadcast delay window)
//   - meshtastic/meshtastic docs/development/reference/encryption-technical.mdx
//
// Everything that is NOT verified upstream is marked UNVERIFIED at its definition
// site and listed in REPORT.md. No radio was involved: this is a host test with a
// fake HAL that implements the frozen contract in firmware/lib/radio_core/radio_hal.h.

#include "harness.h"

#include "fake_radio_hal.h"
#include "mesh_aes.h"
#include "mesh_channel.h"
#include "mesh_crypto.h"
#include "mesh_flood.h"
#include "mesh_packet.h"
#include "mesh_tlv.h"
#include "mesh_transport.h"

#include <cstring>
#include <string>
#include <vector>

using namespace balloon::meshtastic;
using balloon::radio::Modulation;
using balloon::radio::Result;

// ---------------------------------------------------------------- helpers

static std::vector<uint8_t> hexbytes(const char *hex) {
  std::vector<uint8_t> v;
  for (size_t i = 0; hex[i] && hex[i + 1]; i += 2) {
    auto nib = [](char c) -> int {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      if (c >= 'A' && c <= 'F') return c - 'A' + 10;
      return 0;
    };
    v.push_back((uint8_t)((nib(hex[i]) << 4) | nib(hex[i + 1])));
  }
  return v;
}

static std::vector<uint8_t> bytes(const std::string &s) {
  return std::vector<uint8_t>(s.begin(), s.end());
}

static MeshPacket make_text_packet(const std::string &text) {
  MeshPacket p;
  p.to = kBroadcastNode;
  p.from = 0x0A0B0C0Du;
  p.id = 0x11223344u;
  p.set_hop_limit(3);
  p.set_hop_start(3);
  p.payload = bytes(text);
  return p;
}

// A fully-populated packet, used for the exact round-trip test.
static MeshPacket make_full_packet() {
  MeshPacket p;
  p.to = 0xDEADBEEFu;
  p.from = 0x00C0FFEEu;
  p.id = 0xDEAD1234u;
  p.set_hop_limit(5);
  p.set_hop_start(7);
  p.set_want_ack(true);
  p.set_via_mqtt(true);
  p.channel = 0x08;
  p.next_hop = 0x11;
  p.relay_node = 0x22;
  p.payload = bytes("hello mesh");
  p.has_position = true;
  p.position.lat_1e7 = 480123456;
  p.position.lon_1e7 = 113456789;
  p.position.alt_mm = 12345;
  p.has_telemetry = true;
  p.telemetry.battery_mv = 3987;
  p.telemetry.temp_cc = -1234;
  p.telemetry.sats = 9;
  p.telemetry.uptime_s = 65000;
  return p;
}

// ---------------------------------------------------------------- TLV codec

static void test_tlv() {
  CASE("TLV: full packet round-trips exactly");
  {
    MeshPacket in = make_full_packet();
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);
    CHECK(n > 0);

    MeshPacket out;
    CHECK_EQ((int)tlv_decode(buf, n, &out), (int)DecodeStatus::Ok);
    CHECK_EQ(out.to, in.to);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.hop_limit(), in.hop_limit());
    CHECK_EQ(out.hop_start(), in.hop_start());
    CHECK_EQ(out.want_ack(), in.want_ack());
    CHECK_EQ(out.via_mqtt(), in.via_mqtt());
    CHECK_EQ(out.channel, in.channel);
    CHECK_EQ(out.next_hop, in.next_hop);
    CHECK_EQ(out.relay_node, in.relay_node);
    CHECK_EQ(out.payload.size(), in.payload.size());
    CHECK(std::memcmp(out.payload.data(), in.payload.data(), in.payload.size()) == 0);
    CHECK(out.has_position);
    CHECK_EQ(out.position.lat_1e7, in.position.lat_1e7);
    CHECK_EQ(out.position.lon_1e7, in.position.lon_1e7);
    CHECK_EQ(out.position.alt_mm, in.position.alt_mm);
    CHECK(out.has_telemetry);
    CHECK_EQ(out.telemetry.battery_mv, in.telemetry.battery_mv);
    CHECK_EQ(out.telemetry.temp_cc, in.telemetry.temp_cc);
    CHECK_EQ(out.telemetry.sats, in.telemetry.sats);
    CHECK_EQ(out.telemetry.uptime_s, in.telemetry.uptime_s);

    // Encoding is deterministic: encode(decode(encode(x))) == encode(x).
    uint8_t buf2[512];
    size_t n2 = 0;
    CHECK_EQ((int)tlv_encode(out, buf2, sizeof(buf2), &n2), (int)EncodeStatus::Ok);
    CHECK_EQ(n, n2);
    CHECK(std::memcmp(buf, buf2, n) == 0);
  }

  CASE("TLV rule R1: unknown field id AND unknown wire type are SKIPPED");
  {
    // Build a valid packet, then splice in two foreign records:
    //   id 0xFA type 0x7F (both unknown) len 3 value 01 02 03   -> must be skipped
    //   id 0xFB type U8   (unknown id)     len 1 value 0x99     -> must be skipped
    MeshPacket in = make_text_packet("survives");
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);

    std::vector<uint8_t> spliced;
    uint8_t foreign1[] = {0xFA, 0x7F, 0x03, 0x01, 0x02, 0x03};
    uint8_t foreign2[] = {0xFB, (uint8_t)FieldType::U8, 0x01, 0x99};
    spliced.insert(spliced.end(), foreign1, foreign1 + sizeof(foreign1));
    spliced.insert(spliced.end(), buf, buf + n);
    spliced.insert(spliced.end(), foreign2, foreign2 + sizeof(foreign2));

    MeshPacket out;
    CHECK_EQ((int)tlv_decode(spliced.data(), spliced.size(), &out),
             (int)DecodeStatus::Ok);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.payload.size(), in.payload.size());
    CHECK(std::memcmp(out.payload.data(), in.payload.data(), in.payload.size()) == 0);

    // Counter-test for the skip rule: a foreign record whose declared length runs
    // past the end of the buffer must NOT be silently skipped - it desyncs the
    // stream and must be rejected.
    std::vector<uint8_t> overrun(spliced.begin(), spliced.end());
    overrun[2] = 0x40;  // claim a 64-byte value where only 3 bytes exist
    MeshPacket out2;
    CHECK_EQ((int)tlv_decode(overrun.data(), overrun.size(), &out2),
             (int)DecodeStatus::Truncated);
  }

  CASE("TLV rule R2/R3/R4/R5: oversize, truncation, id 0, duplicate -> REJECT");
  {
    MeshPacket in = make_text_packet("x");
    uint8_t buf[512];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, buf, sizeof(buf), &n), (int)EncodeStatus::Ok);

    // R2: a field whose declared length exceeds kTlvMaxValueLen (64).
    std::vector<uint8_t> big;
    big.push_back((uint8_t)FieldId::Payload);
    big.push_back((uint8_t)FieldType::Bytes);
    big.push_back(65);  // 65 > 64
    for (int i = 0; i < 65; ++i) big.push_back((uint8_t)i);
    MeshPacket o;
    CHECK_EQ((int)tlv_decode(big.data(), big.size(), &o), (int)DecodeStatus::Oversized);

    // R3: truncated trailing record.
    MeshPacket o2;
    CHECK_EQ((int)tlv_decode(buf, n - 1, &o2), (int)DecodeStatus::Truncated);

    // R4: field id 0 is reserved and invalid.
    uint8_t zero_id[] = {0x00, (uint8_t)FieldType::U8, 0x01, 0x00};
    MeshPacket o3;
    CHECK_EQ((int)tlv_decode(zero_id, sizeof(zero_id), &o3), (int)DecodeStatus::Malformed);

    // R5: the same mandatory field twice.
    uint8_t dup[512];
    size_t dn = 0;
    CHECK_EQ((int)tlv_encode(in, dup, sizeof(dup), &dn), (int)EncodeStatus::Ok);
    std::vector<uint8_t> dupvet(dup, dup + dn);
    for (size_t i = 0; i < n; ++i) dupvet.push_back(dup[i]);
    MeshPacket o4;
    CHECK_EQ((int)tlv_decode(dupvet.data(), dupvet.size(), &o4),
             (int)DecodeStatus::Duplicate);

    // Encoding side: a hop limit outside the 3-bit field is refused, not truncated.
    MeshPacket bad = make_text_packet("y");
    bad.set_hop_limit(8);
    uint8_t b2[64];
    size_t b2n = 0;
    CHECK_EQ((int)tlv_encode(bad, b2, sizeof(b2), &b2n), (int)EncodeStatus::BadValue);
  }

  CASE("TLV: a short output buffer is refused rather than overrun");
  {
    MeshPacket in = make_full_packet();
    uint8_t tiny[4];
    size_t n = 0;
    CHECK_EQ((int)tlv_encode(in, tiny, sizeof(tiny), &n), (int)EncodeStatus::NoSpace);
  }
}

// ---------------------------------------------------------------- channel

static void test_channel() {
  CASE("channel: the published default PSK alias 1 expands to the 16-byte default key");
  {
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);
    // Upstream src/mesh/Channels.h: defaultpsk = d4 f1 bb 3a 20 29 07 59 f0 bc ff ab cf 4e 69 01
    CHECK_EQ(k.length, 16u);
    const uint8_t want[] = {0xd4, 0xf1, 0xbb, 0x3a, 0x20, 0x29, 0x07, 0x59,
                            0xf0, 0xbc, 0xff, 0xab, 0xcf, 0x4e, 0x69, 0x01};
    CHECK(std::memcmp(k.bytes, want, 16) == 0);
    // The remaining 16 bytes of the 32-byte buffer must be zero padding, and the
    // effective length must stay 16 => AES-128, not AES-256.
    for (size_t i = 16; i < 32; ++i) CHECK_EQ(k.bytes[i], 0);
    CHECK_EQ(aes_bits_for(k), 128);
  }

  CASE("channel: alias 0 disables encryption, aliases 2..255 bump the last byte");
  {
    CryptoKey k;
    uint8_t zero = 0;
    CHECK_EQ((int)expand_psk(&zero, 1, &k), (int)PskStatus::Disabled);
    CHECK_EQ(k.length, 0u);

    uint8_t a2 = 2;
    CHECK_EQ((int)expand_psk(&a2, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(k.bytes[15], 0x02);  // 0x01 + 2 - 1
    CHECK_EQ(k.bytes[0], 0xd4);

    uint8_t a3 = 3;
    CHECK_EQ((int)expand_psk(&a3, 1, &k), (int)PskStatus::Ok);
    // Independently computed: defaultpsk with last byte 0x01+3-1 = 0x03
    CHECK_EQ(k.bytes[15], 0x03);
    CHECK_EQ(k.bytes[0], 0xd4);
    CHECK_EQ(k.bytes[14], 0x69);

    uint8_t a255 = 255;
    CHECK_EQ((int)expand_psk(&a255, 1, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.bytes[15], 0xff);
  }

  CASE("channel: 16-byte PSK is AES-128, 32-byte PSK is AES-256, short PSK pads");
  {
    std::vector<uint8_t> k16 = hexbytes("000102030405060708090a0b0c0d0e0f");
    CryptoKey k;
    CHECK_EQ((int)expand_psk(k16.data(), 16, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(aes_bits_for(k), 128);

    std::vector<uint8_t> k32 = hexbytes("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    CHECK_EQ((int)expand_psk(k32.data(), 32, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 32u);
    CHECK_EQ(aes_bits_for(k), 256);
    CHECK_EQ(k.bytes[31], 0x1f);

    // <16 bytes: zero-padded to 16 (upstream "User provided a too short AES128 key - padding")
    std::vector<uint8_t> short8 = hexbytes("0102030405060708");
    CHECK_EQ((int)expand_psk(short8.data(), 8, &k), (int)PskStatus::Ok);
    CHECK_EQ(k.length, 16u);
    CHECK_EQ(k.bytes[7], 0x08);
    for (size_t i = 8; i < 16; ++i) CHECK_EQ(k.bytes[i], 0);
  }

  CASE("channel hash: XOR of the name bytes with the XOR of the key bytes");
  {
    // docs/development/reference/encryption-technical.mdx:
    // "The one-byte channel hash in the packet header is the XOR of the channel
    //  name's bytes with the XOR of the key's bytes."
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);

    // Independently computed constants:
    //   xor("LongFast")   = 0x0a
    //   xor(defaultpsk)   = 0x02   => hash = 0x08
    //   xor(eventpsk)     = 0xc8   => hash = 0xc2
    CHECK_EQ(channel_hash("LongFast", k), 0x08);
    CHECK_EQ(channel_hash("MyChannel", k) != channel_hash("LongFast", k), true);

    CryptoKey ke;
    std::vector<uint8_t> ev = hexbytes(
        "384bbcc01dc022d181bf36b86121e1fb96b72e55bf74227e9d6afb48d64cb1a1");
    CHECK_EQ((int)expand_psk(ev.data(), 32, &ke), (int)PskStatus::Ok);
    CHECK_EQ(channel_hash("LongFast", ke), 0xc2);

    // Counter-test: the hash is deliberately weak (8 bits). Two distinct keys with
    // the same byte-XOR collide - prove that, so nobody mistakes it for a MAC.
    CryptoKey c1, c2;
    std::vector<uint8_t> x1 = hexbytes("0102030405060708090a0b0c0d0e0f10");
    std::vector<uint8_t> x2 = hexbytes("1002030405060708090a0b0c0d0e0f01");
    CHECK_EQ((int)expand_psk(x1.data(), 16, &c1), (int)PskStatus::Ok);
    CHECK_EQ((int)expand_psk(x2.data(), 16, &c2), (int)PskStatus::Ok);
    CHECK(channel_hash("LongFast", c1) == channel_hash("LongFast", c2));
    CHECK(std::memcmp(c1.bytes, c2.bytes, 16) != 0);
  }
}

// ---------------------------------------------------------------- crypto

static void test_crypto() {
  CASE("AES KAT: FIPS-197 C.1 (AES-128) and C.3 (AES-256) single blocks");
  {
    // These are the vectors printed in FIPS-197 itself, so they anchor the block
    // cipher independently of anything in this repo.
    std::vector<uint8_t> pt = hexbytes("00112233445566778899aabbccddeeff");

    std::vector<uint8_t> k128 = hexbytes("000102030405060708090a0b0c0d0e0f");
    std::vector<uint8_t> want128 = hexbytes("69c4e0d86a7b0430d8cdb78070b4c55a");
    AesKey ak;
    CHECK(aes_set_key(&ak, k128.data(), 16));
    uint8_t out[16];
    aes_encrypt_block(ak, pt.data(), out);
    CHECK(std::memcmp(out, want128.data(), 16) == 0);

    std::vector<uint8_t> k256 = hexbytes(
        "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    std::vector<uint8_t> want256 = hexbytes("8ea2b7ca516745bfeafc49904b496089");
    CHECK(aes_set_key(&ak, k256.data(), 32));
    aes_encrypt_block(ak, pt.data(), out);
    CHECK(std::memcmp(out, want256.data(), 16) == 0);

    // The S-box is generated, not copied: spot-check published values.
    const uint8_t *sb = aes_sbox();
    CHECK_EQ(sb[0x00], 0x63);
    CHECK_EQ(sb[0x01], 0x7c);
    CHECK_EQ(sb[0x53], 0xed);
    CHECK_EQ(sb[0xff], 0x16);

    // A bad key length is refused.
    CHECK(!aes_set_key(&ak, k128.data(), 20));
  }

  CASE("AES-CTR KAT: independent OpenSSL vector over 200 bytes (13 blocks)");
  {
    // Generated OUTSIDE this codebase with:
    //   openssl enc -aes-256-ctr -K <key> -iv <counter block>
    // key            = 000102...1f
    // counter block  = 44332211000000000d0c0b0a00000000
    //   = LE64(packet id 0x11223344) | LE32(from 0x0a0b0c0d) | LE32(block counter 0)
    // plaintext      = bytes 0x00..0xc7
    // See REPORT.md for the caveat about counter width.
    std::vector<uint8_t> key = hexbytes(
        "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
    std::vector<uint8_t> nonce = hexbytes("44332211000000000d0c0b0a00000000");
    std::vector<uint8_t> want = hexbytes(
        "0e6bbaabd915b7032f2e90ab62718fdf125f0ee781654c4442879f0ed4a7b661"
        "d96fa8ce6eddcc351d8e63b74d280183f8f217f3327a911d6abede5c2ee68359"
        "be19a89c544f2c5c3e5b8ba3b917e815b4725e1ccbb2b6322366471d16176ade"
        "108fa9d32087c72796a1915f067627e3d702b575ebe42d3f4c5d00cdee62b4e5"
        "d10772c1ae43fc7ea655fdf149cb14e93490fef4e1f7ca4d988cdef85771d640"
        "a19d6ac1dafe7ca13ca3568e819d1ff71bdfe2ef93d1c28645e44549aef24bae"
        "c30f6e95a2a38579");
    std::vector<uint8_t> pt(200);
    for (size_t i = 0; i < pt.size(); ++i) pt[i] = (uint8_t)i;

    AesCtr c;
    CHECK(aes_ctr_init(&c, key.data(), key.size(), nonce.data()));
    std::vector<uint8_t> buf = pt;
    aes_ctr_xor(&c, buf.data(), buf.size());
    CHECK_EQ(want.size(), buf.size());
    CHECK(std::memcmp(buf.data(), want.data(), buf.size()) == 0);

    // Decrypt is the same operation.
    AesCtr d;
    CHECK(aes_ctr_init(&d, key.data(), key.size(), nonce.data()));
    aes_ctr_xor(&d, buf.data(), buf.size());
    CHECK(std::memcmp(buf.data(), pt.data(), pt.size()) == 0);
  }

  CASE("sealed payload: round trip is bit-exact, wrong key is DETECTED not accepted");
  {
    CryptoKey k;
    uint8_t alias = 1;
    CHECK_EQ((int)expand_psk(&alias, 1, &k), (int)PskStatus::Ok);

    std::vector<uint8_t> plain = bytes("PICO BALLOON TELEMETRY FRAME 0123456789");
    std::vector<uint8_t> sealed;
    CHECK_EQ((int)seal_payload(k, 0x11223344u, 0x0a0b0c0du, plain.data(),
                               plain.size(), &sealed),
             (int)SealStatus::Ok);
    // AES-CTR adds no bytes to the container; the 4-byte CRC trailer is OURS
    // (see REPORT.md - upstream AES-CTR has no integrity check at all).
    CHECK_EQ(sealed.size(), plain.size() + 4);

    std::vector<uint8_t> opened;
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &opened),
             (int)SealStatus::Ok);
    CHECK_EQ(opened.size(), plain.size());
    CHECK(std::memcmp(opened.data(), plain.data(), plain.size()) == 0);

    // COUNTER-TEST 1: wrong key -> garbage -> must be reported, not returned.
    CryptoKey wrong;
    uint8_t a2 = 2;
    CHECK_EQ((int)expand_psk(&a2, 1, &wrong), (int)PskStatus::Ok);
    std::vector<uint8_t> garbage;
    CHECK_EQ((int)open_payload(wrong, 0x11223344u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 2: right key, wrong packet id -> wrong counter block -> caught.
    CHECK_EQ((int)open_payload(k, 0x11223345u, 0x0a0b0c0du, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 3: right key, wrong sender -> caught.
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0eu, sealed.data(),
                               sealed.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 4: one flipped ciphertext bit -> caught.
    std::vector<uint8_t> bitflip = sealed;
    bitflip[7] ^= 0x01;
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, bitflip.data(),
                               bitflip.size(), &garbage),
             (int)SealStatus::IntegrityFailure);

    // COUNTER-TEST 5: a container shorter than the trailer is refused.
    CHECK_EQ((int)open_payload(k, 0x11223344u, 0x0a0b0c0du, sealed.data(), 3,
                               &garbage),
             (int)SealStatus::TooShort);

    // A disabled key is a passthrough (upstream: 0 length == no crypto).
    CryptoKey none;
    uint8_t z = 0;
    CHECK_EQ((int)expand_psk(&z, 1, &none), (int)PskStatus::Disabled);
    std::vector<uint8_t> passthrough;
    CHECK_EQ((int)seal_payload(none, 1, 2, plain.data(), plain.size(),
                               &passthrough),
             (int)SealStatus::Ok);
    CHECK_EQ(passthrough.size(), plain.size());
    CHECK(std::memcmp(passthrough.data(), plain.data(), plain.size()) == 0);
  }
}

// ---------------------------------------------------------------- header

static void test_header() {
  CASE("header: 16-byte wire layout, flags packing, exact round trip");
  {
    CHECK_EQ(kHeaderLength, 16u);
    MeshPacket in = make_full_packet();
    uint8_t hdr[kHeaderLength];
    encode_header(in, hdr);

    // Little-endian 32-bit fields, upstream struct PacketHeader order.
    CHECK_EQ(hdr[0], 0xEF);
    CHECK_EQ(hdr[1], 0xBE);
    CHECK_EQ(hdr[2], 0xAD);
    CHECK_EQ(hdr[3], 0xDE);
    CHECK_EQ(hdr[4], 0xEE);
    CHECK_EQ(hdr[5], 0xFF);
    CHECK_EQ(hdr[6], 0xC0);
    CHECK_EQ(hdr[7], 0x00);
    CHECK_EQ(hdr[8], 0x34);
    CHECK_EQ(hdr[9], 0x12);
    CHECK_EQ(hdr[10], 0xAD);
    CHECK_EQ(hdr[11], 0xDE);
    // flags: hop_limit 5 | want_ack | via_mqtt | hop_start 7 << 5
    CHECK_EQ(hdr[12], (uint8_t)((5 & 0x07) | 0x08 | 0x10 | ((7 & 0x07) << 5)));
    CHECK_EQ(hdr[13], 0x08);
    CHECK_EQ(hdr[14], 0x11);
    CHECK_EQ(hdr[15], 0x22);

    MeshPacket out;
    CHECK_EQ((int)decode_header(hdr, kHeaderLength, &out), (int)DecodeStatus::Ok);
    CHECK_EQ(out.to, in.to);
    CHECK_EQ(out.from, in.from);
    CHECK_EQ(out.id, in.id);
    CHECK_EQ(out.hop_limit(), 5);
    CHECK_EQ(out.hop_start(), 7);
    CHECK_EQ(out.want_ack(), true);
    CHECK_EQ(out.via_mqtt(), true);
    CHECK_EQ(out.channel, 0x08);
    CHECK_EQ(out.next_hop, 0x11);
    CHECK_EQ(out.relay_node, 0x22);

    // A too-short buffer must be refused.
    MeshPacket o2;
    CHECK_EQ((int)decode_header(hdr, kHeaderLength - 1, &o2), (int)DecodeStatus::Truncated);
  }

  CASE("header: hop fields are 3 bits; an out-of-range value is refused on encode");
  {
    MeshPacket p;
    p.set_hop_limit(0);
    CHECK_EQ(p.hop_limit(), 0);
    p.set_hop_start(7);
    CHECK_EQ(p.hop_start(), 7);
    p.set_hop_limit(kMaxHopLimit);
    CHECK_EQ(p.hop_limit(), 7);
    CHECK_EQ(p.hop_start(), 7);
    p.set_hop_limit(0);
    CHECK_EQ(p.hop_start(), 7);  // hop_start is untouched

    // default hop limit per docs/configuration/radio/lora.mdx: "Default is 3"
    CHECK_EQ((int)kDefaultHopLimit, 3);
    // "This can't be greater than 7"
    CHECK_EQ((int)kMaxHopLimit, 7);

    // set_hop_limit clamps at 7 rather than wrapping into want_ack.
    MeshPacket q;
    q.set_hop_limit(9);
    CHECK_EQ(q.hop_limit(), 7);
    CHECK_EQ(q.want_ack(), false);
  }
}

// ---------------------------------------------------------------- flood

static void test_flood() {
  CASE("flood: rebroadcast only while hop limit remains, and decrement on relay");
  {
    MeshPacket p = make_text_packet("flood");
    p.set_hop_limit(3);
    p.set_hop_start(3);

    CHECK(should_rebroadcast(p, /*from_us=*/false));
    CHECK(!should_rebroadcast(p, /*from_us=*/true));  // never re-flood our own tx

    MeshPacket f = rebroadcast_copy(p);
    CHECK_EQ(f.hop_limit(), 2);
    CHECK_EQ(f.hop_start(), 3);  // hop_start records the ORIGINAL budget
    CHECK_EQ(f.id, p.id);
    CHECK_EQ(f.from, p.from);  // relays keep the original sender
    CHECK(f.channel == p.channel);

    // Walk the budget down to zero: the last hop is not rebroadcastable again.
    p.set_hop_limit(1);
    MeshPacket f1 = rebroadcast_copy(p);
    CHECK_EQ(f1.hop_limit(), 0);
    CHECK(!should_rebroadcast(f1, false));

    p.set_hop_limit(0);
    CHECK(!should_rebroadcast(p, false));
    MeshPacket f0 = rebroadcast_copy(p);
    CHECK_EQ(f0.hop_limit(), 0);  // no underflow
  }

  CASE("flood: hop limit 7 is the ceiling and `getHopsAway` is derived from hop_start");
  {
    MeshPacket p = make_text_packet("hops");
    p.set_hop_limit(5);
    p.set_hop_start(5);
    CHECK_EQ(hops_away(p), 0);
    MeshPacket r1 = rebroadcast_copy(p);
    CHECK_EQ(hops_away(r1), 1);
    MeshPacket r2 = rebroadcast_copy(r1);
    CHECK_EQ(hops_away(r2), 2);
  }

  CASE("flood: rebroadcast delay is deterministic under injected randomness");
  {
    FloodPolicy pol;  // slot_time_ms = 1000, cw_min = 3, cw_max = 8 (upstream CWmin/CWmax)
    CHECK_EQ(pol.slot_time_ms, 1000u);
    CHECK_EQ((int)pol.cw_min, 3);
    CHECK_EQ((int)pol.cw_max, 8);

    // Snr -> CWsize is map(snr, -20, 10, 3, 8), the upstream getCWsize().
    CHECK_EQ((int)cw_size_for_snr(-20), 3);
    CHECK_EQ((int)cw_size_for_snr(10), 8);
    CHECK_EQ((int)cw_size_for_snr(0), 6);

    // CLIENT (not ROUTER): delay = 2*CWmax*slot + random(0, 1<<CWsize)*slot
    ScriptedRandom rng({5, 6, 7});
    MeshPacket p = make_text_packet("d");
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/10, /*is_router=*/false, &rng),
             16000u + 5u * 1000u);
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/10, /*is_router=*/false, &rng),
             16000u + 6u * 1000u);
    // Different SNR -> different CWsize -> different window.
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/false, &rng),
             16000u + 7u * 1000u);

    // ROUTER: delay = random(0, 2*CWsize)*slot  (no CWmax offset)
    ScriptedRandom rng2({0, 15});
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/true, &rng2),
             0u);  // CWsize 6 -> random(0,12) -> 0
    CHECK_EQ(rebroadcast_delay_ms(pol, /*snr=*/0, /*is_router=*/true, &rng2),
             15000u);
  }

  CASE("flood: jitter stays inside the documented window for many draws");
  {
    // Exercised with a real generator: every CLIENT draw must land in
    // [2*CWmax*slot, 2*CWmax*slot + (1<<CWsize)*slot).
    XorshiftRandom rng(0x12345678u);
    FloodPolicy pol;
    const uint32_t lo = 2u * pol.cw_max * pol.slot_time_ms;
    for (int i = 0; i < 500; ++i) {
      uint32_t d = rebroadcast_delay_ms(pol, 10, false, &rng);
      uint32_t hi = lo + (1u << 8) * pol.slot_time_ms;
      CHECK(d >= lo);
      CHECK(d < hi);
      CHECK_EQ(d % pol.slot_time_ms, 0u);
    }
  }

  CASE("flood: duplicate suppression inside the window, allowed outside it");
  {
    DuplicateSuppressor sup(/*window_ms=*/30000);
    MeshPacket p = make_text_packet("dupe");
    CHECK(sup.should_relay(p, 1000));   // first time: relay
    CHECK(!sup.should_relay(p, 29999)); // inside window: suppressed
    CHECK(!sup.should_relay(p, 30999)); // exactly at the boundary: still suppressed
    CHECK(sup.should_relay(p, 31001));  // window elapsed: relay again

    // A different packet id, or a different sender, is NOT a duplicate.
    MeshPacket q = p;
    q.id = p.id + 1;
    CHECK(sup.should_relay(q, 1000));
    MeshPacket r = p;
    r.from = p.from + 1;
    CHECK(sup.should_relay(r, 1000));

    // Counter-test: suppression must key on (from,id) and not on the byte length.
    MeshPacket s = make_text_packet("dupe-different-length");
    CHECK(s.payload.size() != p.payload.size());
    CHECK(!sup.should_relay(s, 2000));

    sup.reset();
    CHECK(sup.should_relay(p, 2000));
  }

  CASE("flood: an overheard copy cancels a pending rebroadcast inside the window");
  {
    // This is the redundancy the brief asks for: we schedule a relay, then hear
    // somebody else relay the same (from,id) before our slot fires -> drop ours.
    DuplicateSuppressor sup(30000);
    MeshPacket p = make_text_packet("cancel me");
    CHECK(sup.should_relay(p, 0));       // we schedule a rebroadcast
    CHECK(sup.cancel_pending(p, 500));   // we hear a neighbour's copy
    CHECK(sup.pending_count() == 0);
    // After cancellation the packet is still in history: we do not relay it again.
    CHECK(!sup.should_relay(p, 600));
  }
}

// ---------------------------------------------------------------- transport

static void test_transport() {
  CASE("transport: acquire/release against the frozen HAL contract");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    ChannelConfig ch;
    std::strcpy(ch.name, "LongFast");
    ch.psk[0] = 1;
    ch.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom rng(7);
    MeshTransport t(&hal, ch, pol, &rng);

    CHECK(!t.acquired());
    CHECK_EQ((int)t.send(make_text_packet("nope"), 10, 100), (int)Result::NotAcquired);
    CHECK_EQ((int)t.receive(nullptr, 100), (int)Result::NotAcquired);

    CHECK_EQ((int)t.begin(100), (int)Result::Ok);
    CHECK(t.acquired());
    CHECK(hal.is_acquired());
    CHECK(hal.rx_continuous_set());

    // A second owner must be refused with Busy.
    CHECK_EQ((int)hal.acquire(1), (int)Result::Busy);

    // Configure + read-back verification (the HAL's read_config()).
    CHECK_EQ((int)t.apply_radio_config(906875000u, 11, 5, 22), (int)Result::Ok);
    ::balloon::radio::Config rb = {};
    CHECK_EQ((int)hal.read_config(&rb), (int)Result::Ok);
    CHECK_EQ((int)rb.modulation, (int)Modulation::Lora);
    CHECK_EQ(rb.frequency_hz, 906875000u);
    CHECK_EQ(rb.spreading_factor, 11);
    CHECK_EQ(rb.coding_rate, 5);
    CHECK_EQ(rb.tx_power_dbm, 22);

    CHECK_EQ((int)t.end(), (int)Result::Ok);
    CHECK(!t.acquired());
    CHECK(!hal.is_acquired());
  }

  CASE("transport: send -> receive loopback between two nodes over one medium");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    ChannelConfig ch;
    std::strcpy(ch.name, "LongFast");
    ch.psk[0] = 1;
    ch.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, ch, pol, &r1);
    MeshTransport b(&halB, ch, pol, &r2);

    CHECK_EQ((int)a.begin(100), (int)Result::Ok);
    CHECK_EQ((int)b.begin(100), (int)Result::Ok);

    // Channel hash on both ends: 0x08 for LongFast + default PSK.
    CHECK_EQ(a.channel_hash(), 0x08);
    CHECK_EQ(b.channel_hash(), a.channel_hash());

    MeshPacket out = make_text_packet("12 bytes txt");
    out.from = 0x0A0B0C0Du;
    out.id = 0x10002000u;
    std::vector<uint8_t> plain = out.payload;
    CHECK_EQ((int)a.send(out, 0, 100), (int)Result::Ok);
    CHECK_EQ(halA.sent_count(), 1u);

    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::Ok);
    CHECK_EQ(in.from, out.from);
    CHECK_EQ(in.id, out.id);
    CHECK_EQ(in.channel, 0x08);
    CHECK_EQ(in.hop_limit(), 3);
    CHECK_EQ(in.payload.size(), plain.size());
    CHECK(std::memcmp(in.payload.data(), plain.data(), plain.size()) == 0);
    // Nothing else pending.
    MeshPacket none;
    CHECK_EQ((int)b.receive(&none, 10), (int)Result::Ok);
    CHECK_EQ(none.payload.size(), 0u);
  }

  CASE("transport: a wrong-key receiver gets a decode failure, not a message");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    ChannelConfig good;
    std::strcpy(good.name, "LongFast");
    good.psk[0] = 1;
    good.psk_len = 1;
    ChannelConfig bad = good;
    bad.psk[0] = 2;  // same name, different key -> same hash, different keystream
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, good, pol, &r1);
    MeshTransport b(&halB, bad, pol, &r2);
    CHECK_EQ((int)a.begin(100), (int)Result::Ok);
    CHECK_EQ((int)b.begin(100), (int)Result::Ok);
    CHECK_EQ(a.channel_hash(), b.channel_hash());  // hash cannot tell them apart

    CHECK_EQ((int)a.send(make_text_packet("secret"), 0, 100), (int)Result::Ok);
    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::BadArgument);
    CHECK_EQ(in.payload.size(), 0u);
  }

  CASE("transport: a packet for another channel hash is filtered before decryption");
  {
    Medium medium;
    FakeRadioHal halA(&medium), halB(&medium);
    ChannelConfig other;
    std::strcpy(other.name, "SomeOtherChan");
    other.psk[0] = 1;
    other.psk_len = 1;
    ChannelConfig ours;
    std::strcpy(ours.name, "LongFast");
    ours.psk[0] = 1;
    ours.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom r1(1), r2(2);
    MeshTransport a(&halA, other, pol, &r1);
    MeshTransport b(&halB, ours, pol, &r2);
    CHECK_EQ((int)a.begin(100), (int)Result::Ok);
    CHECK_EQ((int)b.begin(100), (int)Result::Ok);
    CHECK(a.channel_hash() != b.channel_hash());

    CHECK_EQ((int)a.send(make_text_packet("not for you"), 0, 100), (int)Result::Ok);
    MeshPacket in;
    CHECK_EQ((int)b.receive(&in, 100), (int)Result::BadArgument);

    // And the classifier says WHY: wrong hash, rejected before any AES work.
    MeshPacket sniffed;
    CHECK_EQ((int)a.receive(&sniffed, 200), (int)Result::Ok);  // A hears itself
    CHECK_EQ((int)b.classify(sniffed, 0)->action, (int)RxAction::FilterChannelHash);
  }

  CASE("transport: rx classifier - deliver, hop-limit stop, duplicate suppression");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    ChannelConfig ch;
    std::strcpy(ch.name, "LongFast");
    ch.psk[0] = 1;
    ch.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom rng(3);
    MeshTransport t(&hal, ch, pol, &rng);
    CHECK_EQ((int)t.begin(100), (int)Result::Ok);

    MeshPacket p = make_text_packet("classify");
    p.id = 0xABCD;
    RxOutcome o = t.classify(p, 0);
    CHECK_EQ((int)o.action, (int)RxAction::Deliver);
    CHECK(o.deliver);
    CHECK(o.rebroadcast);

    // Second sighting of the same (from,id) -> suppressed.
    RxOutcome o2 = t.classify(p, 100);
    CHECK_EQ((int)o2.action, (int)RxAction::FilterDuplicate);
    CHECK(!o2.rebroadcast);
    CHECK(o2.deliver == false);

    // After the history window elapses it is relayed again.
    RxOutcome o3 = t.classify(p, 40000);
    CHECK_EQ((int)o3.action, (int)RxAction::Deliver);

    // hop_limit 0: we still deliver locally but never re-flood.
    MeshPacket last = make_text_packet("last hop");
    last.id = 0xABCE;
    last.set_hop_limit(0);
    RxOutcome o4 = t.classify(last, 0);
    CHECK_EQ((int)o4.action, (int)RxAction::Deliver);
    CHECK(o4.deliver);
    CHECK(!o4.rebroadcast);

    // We never rebroadcast something we originated.
    MeshPacket mine = make_text_packet("mine");
    mine.id = 0xABCF;
    mine.from = t.node_num();
    RxOutcome o5 = t.classify(mine, 0);
    CHECK(!o5.rebroadcast);
  }

  CASE("transport: oversized payload is refused before it reaches the radio");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    ChannelConfig ch;
    std::strcpy(ch.name, "LongFast");
    ch.psk[0] = 1;
    ch.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom rng(4);
    MeshTransport t(&hal, ch, pol, &rng);
    CHECK_EQ((int)t.begin(100), (int)Result::Ok);

    MeshPacket p = make_text_packet(std::string(300, 'A'));  // 300 > 239
    CHECK_EQ((int)t.send(p, 0, 100), (int)Result::BadArgument);
    CHECK_EQ(hal.sent_count(), 0u);

    MeshPacket ok = make_text_packet(std::string(235, 'B'));
    CHECK_EQ((int)t.send(ok, 0, 100), (int)Result::Ok);
    CHECK_EQ(hal.sent_count(), 1u);
    CHECK(hal.last_sent_size() <= kMaxLoraPayload);
  }

  CASE("transport: HAL error propagation (BusError, Timeout) is not swallowed");
  {
    Medium medium;
    FakeRadioHal hal(&medium);
    ChannelConfig ch;
    std::strcpy(ch.name, "LongFast");
    ch.psk[0] = 1;
    ch.psk_len = 1;
    FloodPolicy pol;
    XorshiftRandom rng(5);
    MeshTransport t(&hal, ch, pol, &rng);
    CHECK_EQ((int)t.begin(100), (int)Result::Ok);

    hal.set_bus_error(true);
    CHECK_EQ((int)t.send(make_text_packet("boom"), 0, 100), (int)Result::BusError);
    hal.set_bus_error(false);

    hal.set_rx_continuous(false);  // radio stops listening
    MeshPacket in;
    CHECK_EQ((int)t.receive(&in, 100), (int)Result::Timeout);

    hal.set_ready(false);
    CHECK_EQ((int)t.acquire_only_for_test_fail(), (int)Result::Timeout);
  }
}

// ---------------------------------------------------------------- main

void run_tests() {
  test_tlv();
  test_channel();
  test_crypto();
  test_header();
  test_flood();
  test_transport();
}

TEST_MAIN()
