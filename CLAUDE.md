# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Video-Audio-TTS Synchronizer** is a Python-based tool that converts subtitle files (SRT) into synchronized audio using Text-to-Speech (TTS), with automatic speed adjustment and video processing with optional freeze frames.

**Key USP**: Intelligent speed adaptation (180-240 WPM) to fit audio within available subtitle duration, with multi-platform support (macOS/Linux/Windows) and automatic fallback mechanisms.

## Quick Commands

### Running the Main Script

```bash
# Interactive mode (recommended for beginners)
python3 create_video_tts_from_srt.py

# Basic processing
python3 create_video_tts_from_srt.py video.srt video.mp4

# Test mode (process only N subtitles)
python3 create_video_tts_from_srt.py video.srt video.mp4 --test 50

# Only generate audio without video processing
python3 create_video_tts_from_srt.py video.srt video.mp4 --solo-audio

# Remove large gaps (>15 min) from final video
python3 create_video_tts_from_srt.py video.srt video.mp4 --remove-breaks

# YouTube integration
python3 create_video_tts_from_srt.py --youtube VIDEO_ID --lang es

# Resume interrupted processing
python3 create_video_tts_from_srt.py --continue temp_video_xyz123
```

### Running Tests

```bash
# Platform-agnostic tests
python3 tests/test_multiplatform_tts.py
python3 tests/test_checkpoint_system.py
python3 tests/test_colors_platform.py
python3 tests/test_unique_filename.py

# Linux-specific tests
python3 tests/linux/test_gtts.py
python3 tests/linux/test_tts_fallback.py
python3 tests/linux/test_tts_offline.py

# Windows-specific tests
python3 tests/windows/test_windows_tts.py
```

## Architecture & Core Concepts

### Main Entry Point
- **File**: `create_video_tts_from_srt.py` (2395 lines)
- **Purpose**: Single monolithic script handling all orchestration
- **Structure**: Mix of procedural code and helper classes

### Key Classes

#### 1. **TTSEngine** (lines 219-600)
Handles platform-specific TTS generation with automatic fallback:
- **macOS**: Uses native `say` command → converts AIFF to WAV via ffmpeg
- **Linux**: gTTS (Google TTS) primary → espeak-ng (offline) fallback
- **Windows**: edge-tts (online) → SAPI/pyttsx3 (offline) fallback
- **Features**: Retry logic (3 attempts), exponential backoff, permanent failure detection

**Key Methods**:
- `_detect_method()`: Platform detection
- `generate_audio()`: Main generation with rate (WPM) support
- `get_tts_name()`: Returns TTS name for output filename

#### 2. **Subtitle** (Dataclass, line 171)
Represents a single subtitle with metadata:
- `consecutive_id`: Renumbered ID (1, 2, 3...)
- `original_id`: Original ID from SRT
- `start_seconds`, `end_seconds`: Computed float timestamps
- `duration`: Calculated duration
- `text`: Subtitle text

#### 3. **AudioSegment** (Dataclass, line 182)
Represents generated audio for a subtitle:
- `subtitle_id`: Reference to subtitle
- `audio_file`: Path to WAV file
- `rate`: Used WPM (180, 200, 220, or 240)
- `needs_freeze`, `freeze_duration`: Freeze frame metadata
- `was_truncated`: Flag for truncated audio

#### 4. **ErrorLogger** (lines 125-169)
Accumulates and displays processing errors/warnings at end.

### Data Flow

```
SRT File
  ↓
[Parse & Validate] → Renumber IDs, compute timestamps
  ↓
[Learning Phase] → First 10 subtitles: test rates 180/200/220/240
  ↓
[Generate TTS] → Create audio files (WAV) with optimal rate
  ↓
[Process Video] → Extract segments, add freeze frames if needed
  ↓
[Build Master Audio] → Concatenate all audio with silence gaps
  ↓
[Merge] → Combine processed video + master audio
  ↓
[Remove Breaks] → (Optional) Remove gaps >15 min
  ↓
Output: .mkv file with TTS
```

### Multi-Platform Strategy

**Automatic Detection**:
1. Detect OS (macOS/Windows/Linux)
2. Select primary TTS engine
3. Implement fallback mechanism
4. Track which TTS was actually used for output naming

**Naming Convention**: `{video}_{tts}_{os}_{freeze}.mkv`
- Example: `video_gtts_Linux_freeze.mkv`
- Indicates TTS method, OS, and whether freeze frames were used

### Key Algorithms

#### Intelligent Speed Adaptation (Learning Phase)
**Lines 1000-1300 (approx)**:
- Tests 4 rates (180, 200, 220, 240 WPM) on first 10 subtitles
- Tracks success/failure ratio
- Selects fastest rate that "fits" most of the time
- Falls back to slower rates or marks for freeze/truncate

**Criteria for "fits"**:
- Audio duration ≤ available time window
- Available time = start of next subtitle - start of current

#### Checkpoint System (lines 1044-1074)
- Saves `checkpoint.json` in temp folder after each subtitle
- Tracks: last processed subtitle ID, total count, absolute file paths
- Allows resuming interrupted processing with `--continue FOLDER`
- Critical for long videos (hours of processing)

#### Master Audio Construction (lines 1500-1700 approx)
- Builds single WAV/AAC by concatenating individual audios
- Inserts silence gaps to align with SRT timestamps
- Accounts for freeze frame duration in timing
- Uses ffmpeg `concat` filter for efficient merging

### Important Configuration Points

#### Optional Parameters Structure
```python
--test N                 # Process first N subtitles
--solo-audio            # Skip video processing
--no-freeze             # Truncate long audio instead of freeze
--remove-breaks         # Post-process to remove >15min gaps
--only-remove-breaks    # Only remove gaps, skip TTS generation
--youtube ID            # Download from YouTube
--lang CODE             # Subtitle language preference
--fix-rate RATE         # Force constant speed (180-240)
--continue FOLDER       # Resume from checkpoint
```

#### Interactive Mode Features
- Last configuration caching (JSON file)
- Video file suggestion based on SRT name
- File existence checks with visual markers
- Parameter confirmation before processing

### Output Files

**During Processing**:
- `{video}_working.srt`: Renumbered subtitles
- `{video}_debug.srt`: Subtitles with TTS metadata (rate, offsets, freeze flags)
- `temp_{name}_{code}/`: Temporary folder with audio files and checkpoint
  - `checkpoint.json`: Processing state
  - Individual `.wav` files per subtitle

**Final Output**:
- `{video}_{tts}_{os}_{freeze}.mkv`: Main output video
- Optional: `{video}_{tts}_{os}_{freeze}_sin_pausas.mkv` (with `--remove-breaks`)

## Known Patterns & Conventions

### Error Handling
- ErrorLogger class accumulates errors, prints summary at end
- Subprocess failures logged with context (step name, command, stderr)
- gTTS failures tracked separately with permanent fallback after repeated failures

### Path Handling
- Uses `pathlib.Path` for cross-platform compatibility
- Absolute paths stored in checkpoint.json to survive directory changes
- Temporary files use UUID + timestamp suffixes to prevent collisions

### Audio Format Standards
- **Input**: MP3 (from gTTS), AIFF (from macOS say)
- **Processing**: WAV files (pydub compatible)
- **Final**: AAC 192k bitrate (ffmpeg merge)
- **Conversion**: Always via ffmpeg for consistency

### Color Output
- ANSI codes disabled on Windows to prevent artifacts
- Unix/macOS/Linux use full color palette for progress/error visualization

## Testing Infrastructure

### Test Organization
- **tests/**: General platform-agnostic tests
- **tests/linux/**: Linux-specific (gTTS, espeak-ng)
- **tests/windows/**: Windows-specific (edge-tts, SAPI)

### Test Patterns
- Mock subprocess calls to avoid actual TTS generation
- Platform detection testing
- Checkpoint system validation
- Error recovery scenarios

## Common Development Tasks

### Adding a New TTS Engine
1. Add detection logic in `TTSEngine._detect_method()`
2. Implement `_generate_with_{engine_name}()` method
3. Handle platform-specific path issues
4. Add fallback chain in `generate_audio()`
5. Update `get_tts_name()` for output naming
6. Add platform-specific tests in `tests/{platform}/`

### Modifying Speed Adaptation Algorithm
- Core logic: lines ~1000-1300
- First 10 subtitles = learning phase (always tests all 4 rates)
- After 10 = optimized phase (uses best rate, falls back if needed)
- Track statistics in local dictionaries for rate success ratios

### Debugging Long Processing
1. Use `--test 50` to process subset
2. Check `temp_*/checkpoint.json` for state
3. Review `{video}_debug.srt` for rate/offset decisions
4. ffmpeg errors printed to stderr (captured by ErrorLogger)

## Roadmap Context

**Completed**:
- Core TTS generation with speed adaptation
- Multi-platform support with fallbacks
- Checkpoint/resume system
- YouTube integration (yt-dlp)
- Freeze frame processing
- Audio synchronization

**In Development**:
- Automated subtitle translation
- Web interface

**Planned** (see README.md lines 702-1074):
- Comprehensive pytest suite
- Interactive parameter UI improvements
- Multi-voice speaker support
- Whisper integration for subtitle extraction
- Output format conversion presets
- GUI (PyQt6/Tkinter)

## Git Strategy
- Commits should NOT include `.claude/` directory (per project instructions)
- Claude should NOT appear as co-author in commits
- Focus commit messages on functional changes, not process ("feat:", "fix:", "test:")
