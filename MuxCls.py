#!/usr/bin/env python3

"""
MuxCls

What it does:
- Scans a folder recursively for video files.
- Shows audio and subtitle streams with index, language, title, codec, channels.
- Lets you choose which audio and subtitle streams to keep.
- Saves processed files into a new output folder with the same folder structure and file names.
- Uses FFmpeg stream copy only: no re-encoding, no quality loss.

Requirements:
- ffmpeg and ffprobe must be installed and available in PATH.

Recommended usage:
    python MuxCls.py

This file is a thin entry point. The implementation lives in the ``muxcls`` package,
split by responsibility (constants, colors, logging, models, text/UI helpers, prompts,
media probing, mux logic, output paths, reporting, selection, processing, and the app
menu). Behavior is identical to the original single-file version.
"""

from __future__ import annotations

import os
import sys

# Ensure the package next to this launcher is importable even when the current
# working directory is elsewhere (drag-and-drop / launcher scenarios).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from muxcls.app import main


if __name__ == "__main__":
    main()
