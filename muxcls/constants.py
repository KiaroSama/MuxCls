from __future__ import annotations

import os

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".webm", ".mov", ".avi"}


FFMPEG_BIN = "ffmpeg"


FFPROBE_BIN = "ffprobe"


ROBOCOPY_BIN = "robocopy"


# Robocopy only exists on Windows; every other platform copies with the stdlib.
IS_WINDOWS = os.name == "nt"


APP_VERSION = "1.4.0"


# Probing a single file is a metadata read, so it should never take minutes.
PROBE_TIMEOUT_SECONDS = 120.0


# How long a child process gets to exit after terminate() before it is killed.
PROCESS_KILL_GRACE_SECONDS = 5.0


# How often the progress line is refreshed while a child process runs.
PROGRESS_POLL_SECONDS = 0.2


# Returned when a command is stopped because it exceeded its timeout.
TIMEOUT_RETURNCODE = 124


COPY_CHUNK_BYTES = 4 * 1024 * 1024


AUDIO_BY_LANGUAGE = "1"


AUDIO_BY_TITLE = "2"


AUDIO_BY_INDEX = "3"


AUDIO_ALL = "4"


AUDIO_NONE = "5"


SUBTITLE_ALL = "1"


SUBTITLE_BY_LANGUAGE = "2"


SUBTITLE_BY_TITLE = "3"


SUBTITLE_BY_INDEX = "4"


SUBTITLE_NONE = "5"


EXIT_TOKENS = {"q", "quit", "exit"}


UNKNOWN_LANGUAGE_DISPLAY = "*uknown"


UNKNOWN_LANGUAGE_INPUTS = {"", "und", "unk", "unknown", "undefined", "uknown", "*uknown"}


INVALID_FILENAME_CHARS = '<>:"/\\|?*'
