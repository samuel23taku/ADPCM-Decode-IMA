#!/usr/bin/env python3
"""
decode_v25.py - Decode a proprietary ".V25" call-recording file to WAV.

Format: block-structured IMA/DVI 4-bit ADPCM (the IMA-in-WAV block layout,
without the RIFF/WAVE wrapper). Mono, 8000 Hz, low-nibble-first. The stream is
divided into 256-byte blocks; each block starts with a 4-byte header
(int16 LE predictor seed, 1-byte step index, 1 reserved byte) followed by 252
bytes of nibbles = 505 samples. The predictor and step index reset from the
header at every block boundary. A small metadata trailer (filename / phone /
date / time) is appended after the audio and is stripped before decoding.

A naive "play the bytes as PCM" read sounds like constant pops/clicks because
the bytes are ADPCM *delta* codes, not samples - they must be run through the
ADPCM predictor to reconstruct the waveform. With the per-block resets applied,
the output needs no high-pass or normalization: it sits in a healthy dynamic
range on its own (~20 dB crest factor, ~0% clipping).

Verify: open the WAV and you should hear intelligible telephone speech; a
spectrogram shows formant bands in ~300-3400 Hz with clean silent gaps.

Dependency: numpy. (`wave` is the Python standard-library module.)
"""

from __future__ import annotations
import wave
import numpy as np

# Standard IMA/DVI ADPCM step-size table (index 0..88).
_STEP_TABLE = np.array([
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230,
    253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963,
    1060, 1166, 1282, 1411, 1552, 1707, 1884, 2078, 2294, 2532, 2796, 3088, 3408,
    3762, 4150, 4575, 5043, 5557, 6122, 6743, 7425, 8173, 8995, 9899, 10894,
    11984, 13183, 14493, 15931, 17501, 19228, 21115, 23184, 25471, 27983, 30752,
    32767], dtype=np.int32)

# Step-index adjustment per 4-bit code.
_INDEX_TABLE = np.array(
    [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8], dtype=np.int32)


def _strip_trailer(data: bytes) -> bytes:
    """Return the audio bytes with the trailing metadata block removed.

    The trailer is a run of printable-ASCII / 0x00 / 0xFE bytes at the end of
    the file, anchored by the ".V25" marker. If no marker is found the whole
    file is treated as audio.
    """
    tail = data[-2048:]
    marker = tail.rfind(b".V25")
    if marker < 0:
        return data
    abs_marker = len(data) - len(tail) + marker
    meta = set(range(0x20, 0x7F)) | {0x00, 0xFE}
    start = abs_marker
    while start > 0 and data[start - 1] in meta:
        start -= 1
    return data[:start]


def _decode_blocks(data: bytes, block_align: int) -> np.ndarray:
    """Decode block-structured IMA ADPCM bytes to int16 PCM."""
    step_tbl = _STEP_TABLE
    idx_tbl = _INDEX_TABLE
    nblocks = len(data) // block_align
    samples_per_block = (block_align - 4) * 2 + 1
    out = np.empty(nblocks * samples_per_block, dtype=np.int16)
    w = 0
    for start in range(0, nblocks * block_align, block_align):
        # Block header: int16 LE predictor seed, byte step index, reserved byte.
        predictor = int.from_bytes(data[start:start + 2], "little", signed=True)
        index = min(data[start + 2], 88)
        out[w] = predictor
        w += 1
        for byte in data[start + 4:start + block_align]:
            for code in (byte & 0x0F, (byte >> 4) & 0x0F):  # low nibble first
                step = int(step_tbl[index])
                diff = step >> 3                            # diff = step*(code+0.5)/8
                if code & 4:
                    diff += step
                if code & 2:
                    diff += step >> 1
                if code & 1:
                    diff += step >> 2
                predictor += -diff if code & 8 else diff    # bit 3 = sign
                predictor = min(32767, max(-32768, predictor))
                index = min(88, max(0, index + int(idx_tbl[code])))
                out[w] = predictor
                w += 1
    return out


def decode_v25(input_path: str,
               output_path: str,
               sample_rate: int = 8000,
               block_align: int = 256) -> None:
    """Decode a ".V25" file to a mono 16-bit PCM WAV.

    Args:
        input_path:  path to the ".V25" file.
        output_path: path of the WAV file to write.
        sample_rate: playback rate in Hz (8000 matches the source material; a
                     wrong value only changes pitch/speed).
        block_align: IMA block size in bytes (256 for this material).
    """
    audio_bytes = _strip_trailer(open(input_path, "rb").read())
    pcm = _decode_blocks(audio_bytes, block_align)
    with wave.open(output_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.astype("<i2").tobytes())


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Decode a .V25 (blocked IMA ADPCM) file to WAV.")
    p.add_argument("input", help="path to the .V25 file")
    p.add_argument("output", help="output WAV path")
    p.add_argument("-r", "--rate", type=int, default=8000, help="sample rate in Hz (default 8000)")
    p.add_argument("-b", "--block-align", type=int, default=256,
                   help="IMA block size in bytes (default 256)")
    a = p.parse_args()
    decode_v25(a.input, a.output, sample_rate=a.rate, block_align=a.block_align)
    print(f"Decoded {a.input} -> {a.output}  ({a.rate} Hz, mono, 16-bit)")
