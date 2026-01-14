# IR Tester 🎸

<div align="center">
  <img src="packaging/assets/icons/ir-tester.svg" width="128" alt="IR Tester Icon">
  <br><br>
  <img src="frontend.png" width="800" alt="IR Tester Interface">
  <br>
  <em>Modern interface with real-time frequency visualization</em>
</div>

<br>

Desktop application for Linux to test Impulse Responses (IR) of guitar cabinets and amplifiers with DI (Direct Input) files.

## Features

- ✅ **Graphic Equalizer**: 10-band EQ for shaping tone in real-time
- ✅ **Smart Addition**: Simultaneous selection of files and folders (single button)
- ✅ **Frequency Graph**: Spectral visualization (20Hz-20kHz) of selected IR
- ✅ **Instant Convolution**: Real-time processing between IR and DI
- ✅ **A/B Mix**:
    - Dry/Wet Mix Slider (0% to 100%)
    - **Quick Toggle**: D/W button for immediate comparison (Dry vs Last Wet)
- ✅ **Export with Normalization**: Export selected IRs with optional volume normalization
    - **Peak**: Normalize to 0 dB peak
    - **RMS**: Normalize to target loudness level (consistent perceived volume)
- ✅ **Efficient Management**: Batch export and smart removal (files/folders)
- ✅ **Dark Interface**: Modern theme built with Qt Stylesheets (QSS)
- ✅ **Complete Controls**: Play, Pause, Loop, Rewind/Forward and Volume

## Installation

### Prerequisites

- Python 3.9+
- PipeWire or PulseAudio (for audio playback on Linux)

### Installing dependencies

```bash
cd ir_tester
pip install -r requirements.txt
```

Or install manually:

```bash
pip install PyQt6 numpy scipy soundfile sounddevice
```

### System dependencies (if needed)

On Ubuntu/Debian:
```bash
sudo apt install libportaudio2 python3-pyqt6
```

On Fedora:
```bash
sudo dnf install portaudio python3-pyqt6
```

On Arch Linux:
```bash
sudo pacman -S portaudio python-pyqt6
```

## Usage

Run the application:

```bash
python main.py
```

### How to use:

1. **Add files**: Click "**Add**" on any panel to select multiple files or entire folders simultaneously.

3. **Test combinations**: Select an IR from the left list and a DI from the right list. Convolution will be processed and played automatically.

4. **Playback controls**:
   - ▶️/⏸️ - Play/Pause
   - ⏹️ - Stop
   - ⏮️ - Rewind 5 seconds
   - ⏭️ - Forward 5 seconds

5. **Adjustments**:
   - **Volume**: Adjusts output level
   - **Mix (Dry/Wet)**: 0% = original sound (DI), 100% = processed sound (convolution)
   - **Equalizer 🎚️**: 10-band equalizer for shaping final tone. Has **Toggle (ON/OFF)** and **Reset (Flat)** buttons.

6. **Exporting IRs**:
   - Check the IRs you want to export in the list
   - Click "**Export**" button
   - Choose normalization options:
     - **No normalization**: Simple file copy
     - **Peak (0 dB)**: Scales each IR so the maximum peak reaches 0 dB
     - **RMS**: Scales each IR to a target RMS level for consistent perceived loudness (recommended: -18 dB to -12 dB)
   - Select destination folder

   > 💡 **Note**: Normalization is a linear operation that only adjusts volume - it does **not** alter the tonal character or frequency response of your IRs.

## Supported formats

### Impulse Responses (IR)
- WAV (recommended)
- AIFF
- FLAC

### Direct Input (DI)
- WAV (recommended)
- AIFF
- FLAC
- MP3

## Tips

- Typical cabinet IRs are between 50ms and 500ms in duration
- For best results, use high quality DI files (44.1kHz or 48kHz, 24-bit)
- Mix control is useful for quickly comparing dry and processed sound
- Convolution preserves the IR decay, so the resulting audio may be slightly longer than the original DI

## Troubleshooting

### No audio
- Check if PulseAudio or PipeWire is running
- Try: `systemctl --user restart pipewire pipewire-pulse`

### Error loading files
- Check if the file is not corrupted
- Try converting to WAV using ffmpeg: `ffmpeg -i input.mp3 output.wav`

## License

MIT License
