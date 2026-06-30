# decode_v25

Decode proprietary `.V25` call-recording files to standard WAV.

`.V25` files are **block-structured IMA/DVI 4-bit ADPCM** (the IMA-in-WAV block
layout, without the RIFF/WAVE container): mono, 8000 Hz, low-nibble-first,
256-byte blocks. Each block begins with a 4-byte header (int16 predictor seed,
step index, reserved byte) and the predictor resets at every block boundary. A
short metadata trailer (filename / phone / date / time) is appended after the
audio and is stripped automatically before decoding.

Playing the raw bytes sounds like constant pops/clicks because they are ADPCM
*delta* codes, not PCM samples — they must be run through the ADPCM decoder.
With the per-block resets applied, the output needs no filtering or
normalization: it lands in a healthy dynamic range on its own.

## Requirements

- Python 3.8+
- numpy (see `requirements.txt`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Command line:

```bash
python decode_v25.py <input.V25> <output.wav>

# options
python decode_v25.py input.V25 out.wav -r 8000        # sample rate (Hz)
python decode_v25.py input.V25 out.wav -b 256         # IMA block size (bytes)
```

As a library:

```python
from decode_v25 import decode_v25

decode_v25("Samples/V25-7690-5527-D017.V25", "decoded/D017.wav")
```

Output is mono, 16-bit PCM WAV.

## Verifying output

A correct decode produces intelligible telephone speech with a crest factor
around 20 dB and essentially no rail-clipping. On the sample files:

| file                     | duration | crest factor | rail-clip |
| ------------------------ | -------- | ------------ | --------- |
| V25-7690-5527-D017       | 93.9 s   | 20.5 dB      | 0.003%    |
| V25-7702-5527-D078       | 920.7 s  | 21.4 dB      | 0.002%    |

The decode was independently cross-checked against ffmpeg's `adpcm_ima_wav`
decoder, which agrees within rounding (~20.8 dB crest, ~0% clipping).

## Notes

- `sample_rate` only affects playback pitch/speed; the samples themselves are
  rate-agnostic. 8000 Hz matches the source material.
- `block_align` defaults to 256, correct for this material. It is exposed in
  case a future file uses a different block size.
