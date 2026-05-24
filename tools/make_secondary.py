#!/usr/bin/env python3
"""
Converts an OSSC primary firmware image (magic "OSSC") into a secondary
firmware image (magic "OSS2") by patching byte 3 of the header and
recomputing the header CRC. The data section is left untouched.

The resulting image is flashed by the OSSC bootloader to SECONDARY_FW_ADDR
(0x00080000) instead of the primary slot (0x00000000), leaving the primary
firmware intact. See firmware.c:109 for the bootloader logic.

Usage:
    tools/make_secondary.py <input.bin> [output.bin]

If output is omitted, "-sec" is inserted before the extension.
"""
import struct
import sys
from pathlib import Path

FW_HDR_LEN = 26
HDR_CRC_OFFSET = 508

_CRC_TABLE = []
for n in range(256):
    c = n
    for _ in range(8):
        c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
    _CRC_TABLE.append(c)


def crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF


def main(argv):
    if len(argv) < 2 or len(argv) > 3:
        print(__doc__, file=sys.stderr)
        return 1

    src = Path(argv[1])
    dst = Path(argv[2]) if len(argv) == 3 else src.with_name(src.stem + "-sec" + src.suffix)

    data = bytearray(src.read_bytes())
    if data[:4] != b"OSSC":
        print(f"error: expected magic 'OSSC' at start of {src}, got {bytes(data[:4])!r}", file=sys.stderr)
        return 2

    data[3] = ord("2")
    new_crc = crc32(bytes(data[:FW_HDR_LEN]))
    data[HDR_CRC_OFFSET:HDR_CRC_OFFSET + 4] = struct.pack(">I", new_crc)

    dst.write_bytes(bytes(data))

    suffix = bytes(data[6:14]).rstrip(b"\x00").decode("ascii", errors="replace")
    print(f"wrote {dst} ({len(data)} bytes)")
    print(f"  magic    : OSS2 -> target flash 0x00080000 (secondary slot)")
    print(f"  version  : {data[4]}.{data[5]}{('-' + suffix) if suffix else ''}")
    print(f"  hdr_crc  : 0x{new_crc:08x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
