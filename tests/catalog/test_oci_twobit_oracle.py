"""Independent 2bit decoding checks packed bases and explicit N blocks."""

from __future__ import annotations

import struct

import pytest

from scripts.oci_twobit_oracle import TwoBitFormatError, decode_twobit


@pytest.mark.parametrize("endian", [">", "<"])
def test_twobit_decoder_recovers_packed_bases_and_n_blocks(endian: str) -> None:
    header = struct.pack(endian + "IIII", 0x1A412743, 0, 1, 0)
    index = b"\x01A" + struct.pack(endian + "I", 22)
    sequence = struct.pack(endian + "IIIIII", 4, 1, 1, 2, 0, 0) + b"\x9c"
    assert decode_twobit(header + index + sequence) == {"A": "ANNT"}
    with pytest.raises(TwoBitFormatError, match="truncated"):
        decode_twobit(header + index + sequence[:-1])
