"""Small independent UCSC 2bit decoder for a fixed sequence oracle."""

from __future__ import annotations

import struct


class TwoBitFormatError(ValueError):
    """A 2bit output is malformed or outside this bounded oracle profile."""


def decode_twobit(data: bytes) -> dict[str, str]:
    if len(data) < 16 or len(data) > 16 * 1024 * 1024:
        raise TwoBitFormatError("2bit file is empty or exceeds the fixture oracle limit")
    if data[:4] == b"\x1a\x41\x27\x43":
        endian = ">"
    elif data[:4] == b"\x43\x27\x41\x1a":
        endian = "<"
    else:
        raise TwoBitFormatError("unsupported 2bit signature")
    signature, version, count, reserved = struct.unpack_from(endian + "IIII", data)
    if signature != 0x1A412743 or version != 0 or reserved != 0 or count > 128:
        raise TwoBitFormatError("unsupported 2bit header")

    def word(offset: int) -> int:
        if offset < 0 or offset + 4 > len(data):
            raise TwoBitFormatError("2bit field exceeds file bounds")
        return struct.unpack_from(endian + "I", data, offset)[0]

    index: list[tuple[str, int]] = []
    cursor = 16
    for _ in range(count):
        if cursor >= len(data):
            raise TwoBitFormatError("2bit index exceeds file bounds")
        name_size = data[cursor]
        cursor += 1
        if not name_size or cursor + name_size + 4 > len(data):
            raise TwoBitFormatError("2bit sequence name exceeds file bounds")
        try:
            name = data[cursor:cursor + name_size].decode("ascii")
        except UnicodeError as error:
            raise TwoBitFormatError("2bit sequence name is not ASCII") from error
        cursor += name_size
        offset = word(cursor)
        cursor += 4
        if offset < cursor or any(prior == name for prior, _ in index):
            raise TwoBitFormatError("2bit index has duplicate name or invalid offset")
        index.append((name, offset))
    sequences: dict[str, str] = {}
    for name, offset in index:
        size = word(offset)
        if size > 1_000_000:
            raise TwoBitFormatError("2bit fixture sequence exceeds size bound")
        position = offset + 4
        n_count = word(position)
        position += 4
        if n_count > size or position + 8 * n_count > len(data):
            raise TwoBitFormatError("2bit N block count is invalid")
        starts = [word(position + 4 * i) for i in range(n_count)]
        position += 4 * n_count
        lengths = [word(position + 4 * i) for i in range(n_count)]
        position += 4 * n_count
        mask_count = word(position)
        position += 4
        if mask_count != 0:
            raise TwoBitFormatError("fixture oracle requires unmasked uppercase bases")
        if word(position) != 0:
            raise TwoBitFormatError("2bit sequence reserved field is nonzero")
        position += 4
        packed = data[position:position + (size + 3) // 4]
        if len(packed) != (size + 3) // 4:
            raise TwoBitFormatError("packed bases are truncated")
        bases = ["TCAG"[(packed[i // 4] >> (6 - 2 * (i % 4))) & 3] for i in range(size)]
        for start, length in zip(starts, lengths, strict=True):
            if start + length > size:
                raise TwoBitFormatError("2bit N block exceeds sequence length")
            bases[start:start + length] = ["N"] * length
        sequences[name] = "".join(bases)
    return sequences
