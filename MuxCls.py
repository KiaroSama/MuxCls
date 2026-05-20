#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".webm", ".mov", ".avi"}

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"
APP_VERSION = "1.0.0"

LOGGER = logging.getLogger("MuxCls")
LOG_FILE: Optional[Path] = None


# ANSI colors. No external dependency required.
# Use bright variants so text stays readable on black terminal backgrounds.
ENABLE_COLORS = True


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[97m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[97m"


def color(text: object, code: str) -> str:
    if not ENABLE_COLORS:
        return str(text)
    return f"{code}{text}{C.RESET}"


def ok(text: object) -> str:
    return color(text, C.GREEN)


def warn(text: object) -> str:
    return color(text, C.YELLOW)


def err(text: object) -> str:
    return color(text, C.RED)


def info(text: object) -> str:
    return color(text, C.CYAN)


def dim(text: object) -> str:
    return color(text, C.GRAY)


def bold(text: object) -> str:
    return color(text, C.BOLD)


def enable_windows_ansi() -> None:
    # Enables ANSI escape handling on many Windows consoles.
    if os.name == "nt":
        os.system("")


def command_to_text(args: Sequence[object]) -> str:
    return subprocess.list2cmdline([str(arg) for arg in args])


def setup_logging() -> Optional[Path]:
    global LOG_FILE

    try:
        log_root = Path(__file__).resolve().parent / "Logs"
        log_root.mkdir(parents=True, exist_ok=True)
        LOG_FILE = log_root / f"muxcls_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

        LOGGER.setLevel(logging.DEBUG)
        LOGGER.handlers.clear()
        LOGGER.propagate = False

        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        LOGGER.addHandler(handler)
        LOGGER.info("MuxCls started")
        LOGGER.info("MuxCls version: %s", APP_VERSION)
        LOGGER.info("Python: %s", sys.version.replace("\n", " "))
        LOGGER.info("OS: %s", platform.platform())
        LOGGER.info("Log file: %s", LOG_FILE)
        LOGGER.info("Command line: %s", command_to_text(sys.argv))
        return LOG_FILE
    except OSError as exc:
        print(warn(f"Logging disabled: {exc}"))
        LOG_FILE = None
        return None


@dataclass
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str = ""
    language: str = ""
    title: str = ""
    channels: Optional[int] = None
    disposition_default: int = 0

    @classmethod
    def from_ffprobe(cls, raw: Dict[str, Any]) -> "StreamInfo":
        tags = raw.get("tags") or {}
        disposition = raw.get("disposition") or {}
        return cls(
            index=int(raw.get("index", -1)),
            codec_type=str(raw.get("codec_type", "")),
            codec_name=str(raw.get("codec_name", "")),
            language=str(tags.get("language", "") or "und"),
            title=str(tags.get("title", "") or ""),
            channels=raw.get("channels"),
            disposition_default=int(disposition.get("default", 0) or 0),
        )


@dataclass
class MediaFile:
    path: Path
    streams: List[StreamInfo]

    @property
    def video_streams(self) -> List[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "video"]

    @property
    def audio_streams(self) -> List[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "audio"]

    @property
    def subtitle_streams(self) -> List[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "subtitle"]

    @property
    def attachment_streams(self) -> List[StreamInfo]:
        return [s for s in self.streams if s.codec_type == "attachment"]


@dataclass
class SelectionRules:
    audio_mode: str
    audio_languages: List[str]
    audio_titles: List[str]
    audio_indexes: List[int]

    subtitle_mode: str
    subtitle_languages: List[str]
    subtitle_titles: List[str]
    subtitle_indexes: List[int]

    keep_attachments: bool
    keep_metadata: bool
    keep_chapters: bool
    overwrite: bool


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess:
    LOGGER.debug("Running command: %s", command_to_text(args))
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    LOGGER.debug("Command return code: %s", proc.returncode)
    if proc.stdout.strip():
        LOGGER.debug("Command stdout:\n%s", proc.stdout.strip())
    if proc.stderr.strip():
        LOGGER.debug("Command stderr:\n%s", proc.stderr.strip())
    return proc


def require_tool(binary: str) -> bool:
    found = shutil.which(binary)
    LOGGER.info("Tool check: %s -> %s", binary, found or "not found")
    return found is not None


def print_header(text: str) -> None:
    print()
    print(color("=" * 80, C.BLUE))
    print(color(text, C.BOLD + C.CYAN))
    print(color("=" * 80, C.BLUE))


def print_section(text: str) -> None:
    print()
    print(color("-" * 80, C.GRAY))
    print(color(text, C.BOLD + C.WHITE))
    print(color("-" * 80, C.GRAY))


EXIT_TOKENS = {"q", "quit", "exit"}


class MenuExit(Exception):
    pass


class MenuBack(Exception):
    pass


def prompt_label(prompt: str) -> str:
    return prompt.strip().rstrip(":").strip()


def option_suffix(default: Optional[str], allow_back: bool) -> str:
    default_part = f" [{default}]" if default else ""
    nav_parts: List[str] = []
    nav_parts.append("quit=exit")
    if allow_back:
        nav_parts.append("0=Back")
    return f"{default_part} {{{', '.join(nav_parts)}}}"


def option_list_suffix(default: Optional[str], allow_back: bool) -> str:
    parts: List[str] = []
    if default:
        parts.append(default)
    parts.append("quit=exit")
    if allow_back:
        parts.append("0=Back")
    return f" [{', '.join(parts)}]"


def read_menu_input(prompt: str, default: Optional[str] = None, allow_back: bool = True) -> str:
    while True:
        raw = input(f"{prompt_label(prompt)}{option_suffix(default, allow_back)}: ").strip()
        lowered = raw.lower()

        if lowered in EXIT_TOKENS:
            raise MenuExit

        if raw == "0":
            if allow_back:
                raise MenuBack
            print(warn("Back is not available here."))
            continue

        if not raw and default is not None:
            return default

        return raw


def ask_text(prompt: str, allow_back: bool = True) -> str:
    while True:
        raw = read_menu_input(prompt, allow_back=allow_back)
        if raw:
            return raw
        print(err("Value cannot be empty."))


def ask_path(prompt: str, must_exist: bool = False, allow_back: bool = True) -> Path:
    while True:
        raw = read_menu_input(prompt, allow_back=allow_back)
        if not raw:
            print(err("Path cannot be empty."))
            continue

        path = normalize_path_text(raw)

        if must_exist and not path.exists():
            print(err(f"Path does not exist: {path}"))
            continue

        return path


def normalize_path_text(raw: str) -> Path:
    return Path(raw.strip().strip('"').strip("'")).expanduser()


def input_path_from_args(args: Sequence[str]) -> Optional[Path]:
    if not args:
        return None

    # The launchers pass the dropped file or folder as the first argument.
    raw = args[0].strip()
    if not raw:
        return None

    return normalize_path_text(raw)


def ask_output_base_path(input_root: Path) -> Path:
    default_base = input_root.parent
    while True:
        raw = read_menu_input("Output folder path [Enter=input parent folder]", allow_back=True)
        if not raw:
            return default_base

        path = normalize_path_text(raw)
        if path.exists() and not path.is_dir():
            print(err(f"Output path exists but is not a folder: {path}"))
            continue
        return path


def ask_yes_no(prompt: str, default: bool = True, allow_back: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = read_menu_input(prompt, default=suffix, allow_back=allow_back).lower()
        if raw == suffix.lower():
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print(warn("Please enter y or n."))


def print_metadata_note() -> None:
    print("Keep metadata: True")
    print(dim("  Preserves supported source metadata such as titles, language tags, chapters, and stream labels."))


def ask_choice(prompt: str, valid: Iterable[str], default: str, allow_back: bool = True) -> str:
    valid_set = {v.lower() for v in valid}
    while True:
        raw = read_menu_input(prompt, default=default, allow_back=allow_back).lower()
        if raw in valid_set:
            return raw
        print(warn(f"Invalid choice. Valid options: {', '.join(sorted(valid_set))}"))


def parse_csv_text(raw: str) -> List[str]:
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def parse_csv_int(raw: str) -> List[int]:
    result: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            print(warn(f"Ignored invalid number: {part}"))
    return result


def format_elapsed_time(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def find_video_files(input_path: Path) -> List[Path]:
    files: List[Path] = []

    if input_path.is_file():
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            return [input_path]
        return []

    for path in input_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(path)

    return sorted(files, key=lambda p: str(p).lower())


def probe_file(path: Path) -> Optional[MediaFile]:
    args = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,channels:stream_tags=language,title:stream_disposition=default",
        "-of",
        "json",
        str(path),
    ]

    proc = run_command(args)

    if proc.returncode != 0:
        LOGGER.error("Probe failed for %s", path)
        print(err(f"[PROBE FAILED] {path}"))
        if proc.stderr.strip():
            print(proc.stderr.strip())
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        LOGGER.error("Probe returned invalid JSON for %s", path)
        print(err(f"[PROBE FAILED] Invalid JSON from ffprobe: {path}"))
        return None

    streams = [StreamInfo.from_ffprobe(s) for s in data.get("streams", [])]
    LOGGER.info(
        "Probe OK: %s | video=%s audio=%s subtitle=%s attachment=%s",
        path,
        sum(1 for s in streams if s.codec_type == "video"),
        sum(1 for s in streams if s.codec_type == "audio"),
        sum(1 for s in streams if s.codec_type == "subtitle"),
        sum(1 for s in streams if s.codec_type == "attachment"),
    )
    return MediaFile(path=path, streams=streams)


def scan_files(files: List[Path]) -> List[MediaFile]:
    result: List[MediaFile] = []
    LOGGER.info("Scanning %s file(s)", len(files))

    for i, file_path in enumerate(files, start=1):
        print(info(f"[{i}/{len(files)}] Scanning: {file_path.name}"))
        media = probe_file(file_path)
        if media:
            result.append(media)

    LOGGER.info("Scan complete: %s/%s file(s) probed successfully", len(result), len(files))
    return result


def format_stream(stream: StreamInfo) -> str:
    title = stream.title if stream.title else "-"
    lang = stream.language if stream.language else "und"
    codec = stream.codec_name if stream.codec_name else "-"
    channels = str(stream.channels) if stream.channels is not None else "-"
    default = "yes" if stream.disposition_default else "no"

    index_part = color(f"index={stream.index:<3}", C.WHITE)
    lang_part = color(f"lang={lang:<6}", C.GREEN if lang.lower() in {"jpn", "ja", "japanese"} else C.YELLOW)
    title_part = color(f"title={title:<25}", C.CYAN)
    codec_part = color(f"codec={codec:<10}", C.WHITE)
    default_part = color(f"default={default}", C.GREEN if default == "yes" else C.GRAY)

    if stream.codec_type == "audio":
        type_part = color("type=audio    ", C.BLUE)
        channels_part = color(f"channels={channels:<2}", C.WHITE)
        return f"{index_part} {type_part} {lang_part} {title_part} {codec_part} {channels_part} {default_part}"

    if stream.codec_type == "subtitle":
        type_part = color("type=subtitle ", C.BOLD + C.YELLOW)
        return f"{index_part} {type_part} {lang_part} {title_part} {codec_part} {default_part}"

    type_part = color(f"type={stream.codec_type:<9}", C.GRAY)
    return f"{index_part} {type_part} {lang_part} {title_part} {codec_part}"


def print_scan_report(media_files: List[MediaFile], root: Path) -> None:
    print_header("SCAN REPORT: AUDIO AND SUBTITLE STREAMS")

    for media in media_files:
        rel = display_path(root, media.path)

        print()
        print(color(f"File: {rel}", C.BOLD + C.WHITE))

        audio = media.audio_streams
        subtitles = media.subtitle_streams

        if audio:
            print(color("  Audio:", C.BLUE))
            for s in audio:
                print(f"    {format_stream(s)}")
        else:
            print(dim("  Audio: none"))

        if subtitles:
            print(color("  Subtitles:", C.BOLD + C.YELLOW))
            for s in subtitles:
                print(f"    {format_stream(s)}")
        else:
            print(dim("  Subtitles: none"))


def print_unique_summary(media_files: List[MediaFile]) -> None:
    audio_summary: Dict[Tuple[str, str, str], int] = {}
    subtitle_summary: Dict[Tuple[str, str, str], int] = {}

    for media in media_files:
        for s in media.audio_streams:
            key = (s.language.lower(), s.title.lower(), s.codec_name.lower())
            audio_summary[key] = audio_summary.get(key, 0) + 1

        for s in media.subtitle_streams:
            key = (s.language.lower(), s.title.lower(), s.codec_name.lower())
            subtitle_summary[key] = subtitle_summary.get(key, 0) + 1

    print_header("UNIQUE STREAM SUMMARY")

    print(color("Audio streams found:", C.BLUE))
    if audio_summary:
        for (lang, title, codec), count in sorted(audio_summary.items()):
            print(f"  count={count:<4} lang={lang or 'und':<6} title={title or '-':<30} codec={codec or '-'}")
    else:
        print(dim("  none"))

    print()
    print(color("Subtitle streams found:", C.BOLD + C.YELLOW))
    if subtitle_summary:
        for (lang, title, codec), count in sorted(subtitle_summary.items()):
            print(f"  count={count:<4} lang={lang or 'und':<6} title={title or '-':<30} codec={codec or '-'}")
    else:
        print(dim("  none"))


def format_index_list(indexes: List[int]) -> str:
    if not indexes:
        return "none"
    return ", ".join(str(index) for index in indexes)


def format_text_list(values: List[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)


def stream_indexes_for(media_files: List[MediaFile], codec_type: str) -> List[int]:
    return sorted({
        stream.index
        for media in media_files
        for stream in media.streams
        if stream.codec_type == codec_type
    })


def stream_languages_for(media_files: List[MediaFile], codec_type: str) -> List[str]:
    return sorted({
        (stream.language or "und").lower()
        for media in media_files
        for stream in media.streams
        if stream.codec_type == codec_type
    })


def ask_keep_indexes(
    label: str,
    available_indexes: List[int],
    exact_mode: str,
    all_mode: str,
    none_mode: str,
) -> Tuple[str, List[int]]:
    print()
    print(color(f"{label} stream selection", C.BOLD + C.WHITE))
    print(info(f"Available {label.lower()} stream indexes: {format_index_list(available_indexes)}"))

    if not available_indexes:
        print(warn(f"No {label.lower()} streams were found; selecting none."))
        return none_mode, []

    print("Enter indexes from the scan report to KEEP.")
    print("Examples: 1,2 | all | none")

    available_set = set(available_indexes)

    while True:
        raw = ask_text(f"{label} stream indexes to KEEP").lower()
        if not raw:
            print(warn("Please enter stream indexes, all, or none."))
            continue

        if raw in {"all", "a", "*"}:
            return all_mode, []

        if raw in {"none", "n", "no", "remove", "-"}:
            return none_mode, []

        indexes = parse_csv_int(raw)
        if not indexes:
            print(warn("Please enter stream indexes, all, or none."))
            continue

        unknown_indexes = sorted(set(indexes) - available_set)
        if unknown_indexes:
            print(warn(f"These indexes were not found in the scan: {format_index_list(unknown_indexes)}"))
            if not ask_yes_no("Keep these indexes anyway?", False):
                continue

        return exact_mode, indexes


def configure_rules_advanced(media_files: List[MediaFile]) -> SelectionRules:
    print_header("CONFIGURE OUTPUT RULES")

    audio_language_options = stream_languages_for(media_files, "audio")
    subtitle_language_options = stream_languages_for(media_files, "subtitle")

    print("Audio selection modes:")
    print(f"  1 = keep audio by language codes. Found: {format_text_list(audio_language_options)}")
    print("  2 = keep audio by title text, example: Japanese,Commentary")
    print("  3 = keep audio by exact stream indexes, example: 2,3")
    print("  4 = keep all audio")
    print("  5 = remove all audio")
    audio_mode = ask_choice("Choose audio mode", {"1", "2", "3", "4", "5"}, "1")

    audio_languages: List[str] = []
    audio_titles: List[str] = []
    audio_indexes: List[int] = []

    if audio_mode == "1":
        print(info(f"Audio languages found: {format_text_list(audio_language_options)}"))
        audio_languages = parse_csv_text(ask_text("Audio language codes to KEEP from the list above"))
    elif audio_mode == "2":
        audio_titles = parse_csv_text(ask_text("Audio title text to KEEP, example japanese,commentary"))
    elif audio_mode == "3":
        audio_indexes = parse_csv_int(ask_text("Audio stream indexes to KEEP, example 2,3"))

    print()
    print("Subtitle selection modes:")
    print("  1 = remove all subtitles")
    print(f"  2 = keep subtitles by language codes. Found: {format_text_list(subtitle_language_options)}")
    print("  3 = keep subtitles by title text, example: Signs,Full")
    print("  4 = keep subtitles by exact stream indexes, example: 3,4")
    print("  5 = keep all subtitles")
    subtitle_mode = ask_choice("Choose subtitle mode", {"1", "2", "3", "4", "5"}, "1")

    subtitle_languages: List[str] = []
    subtitle_titles: List[str] = []
    subtitle_indexes: List[int] = []

    if subtitle_mode == "2":
        print(info(f"Subtitle languages found: {format_text_list(subtitle_language_options)}"))
        subtitle_languages = parse_csv_text(ask_text("Subtitle language codes to KEEP from the list above"))
    elif subtitle_mode == "3":
        subtitle_titles = parse_csv_text(ask_text("Subtitle title text to KEEP, example signs,full"))
    elif subtitle_mode == "4":
        subtitle_indexes = parse_csv_int(ask_text("Subtitle stream indexes to KEEP, example 3,4"))

    print()
    if subtitle_mode == "1":
        keep_attachments = False
        print(warn("Subtitle mode is remove-all, so font attachments will also be removed."))
    else:
        keep_attachments = ask_yes_no("Keep MKV font attachments? Recommended if you keep ASS/SSA subtitles", True)

    print_metadata_note()
    keep_metadata = ask_yes_no("Keep input metadata?", True)
    keep_chapters = ask_yes_no("Keep chapters?", True)
    overwrite = ask_yes_no("Overwrite existing output files?", False)

    return SelectionRules(
        audio_mode=audio_mode,
        audio_languages=audio_languages,
        audio_titles=audio_titles,
        audio_indexes=audio_indexes,
        subtitle_mode=subtitle_mode,
        subtitle_languages=subtitle_languages,
        subtitle_titles=subtitle_titles,
        subtitle_indexes=subtitle_indexes,
        keep_attachments=keep_attachments,
        keep_metadata=keep_metadata,
        keep_chapters=keep_chapters,
        overwrite=overwrite,
    )


def configure_rules(media_files: List[MediaFile]) -> SelectionRules:
    print_header("CHOOSE STREAMS TO KEEP")
    print("Use the ffprobe stream indexes shown in the scan report above.")
    print("Selection styles:")
    print("  1 = choose exact stream indexes from the scan report")
    print("  2 = advanced rules by language, title, or index [default]")

    selection_style = ask_choice("Choose selection style", {"1", "2"}, "2")
    if selection_style == "2":
        LOGGER.info("Selection style: advanced")
        return configure_rules_advanced(media_files)

    LOGGER.info("Selection style: exact stream indexes")
    audio_mode, audio_indexes = ask_keep_indexes(
        "Audio",
        stream_indexes_for(media_files, "audio"),
        exact_mode="3",
        all_mode="4",
        none_mode="5",
    )

    subtitle_mode, subtitle_indexes = ask_keep_indexes(
        "Subtitle",
        stream_indexes_for(media_files, "subtitle"),
        exact_mode="4",
        all_mode="5",
        none_mode="1",
    )

    print()
    if subtitle_mode == "1":
        keep_attachments = False
        print(warn("Subtitle selection is none, so font attachments will also be removed."))
    else:
        keep_attachments = ask_yes_no("Keep MKV font attachments? Recommended if you keep ASS/SSA subtitles", True)

    print_metadata_note()
    keep_metadata = ask_yes_no("Keep input metadata?", True)
    keep_chapters = ask_yes_no("Keep chapters?", True)
    overwrite = ask_yes_no("Overwrite existing output files?", False)

    return SelectionRules(
        audio_mode=audio_mode,
        audio_languages=[],
        audio_titles=[],
        audio_indexes=audio_indexes,
        subtitle_mode=subtitle_mode,
        subtitle_languages=[],
        subtitle_titles=[],
        subtitle_indexes=subtitle_indexes,
        keep_attachments=keep_attachments,
        keep_metadata=keep_metadata,
        keep_chapters=keep_chapters,
        overwrite=overwrite,
    )


def text_matches_any(value: str, needles: List[str]) -> bool:
    haystack = (value or "").lower()
    return any(needle in haystack for needle in needles)


def selected_audio_streams(media: MediaFile, rules: SelectionRules) -> List[StreamInfo]:
    audio = media.audio_streams

    if rules.audio_mode == "1":
        return [s for s in audio if s.language.lower() in rules.audio_languages]

    if rules.audio_mode == "2":
        return [s for s in audio if text_matches_any(s.title, rules.audio_titles)]

    if rules.audio_mode == "3":
        return [s for s in audio if s.index in rules.audio_indexes]

    if rules.audio_mode == "4":
        return audio

    if rules.audio_mode == "5":
        return []

    return []


def selected_subtitle_streams(media: MediaFile, rules: SelectionRules) -> List[StreamInfo]:
    subtitles = media.subtitle_streams

    if rules.subtitle_mode == "1":
        return []

    if rules.subtitle_mode == "2":
        return [s for s in subtitles if s.language.lower() in rules.subtitle_languages]

    if rules.subtitle_mode == "3":
        return [s for s in subtitles if text_matches_any(s.title, rules.subtitle_titles)]

    if rules.subtitle_mode == "4":
        return [s for s in subtitles if s.index in rules.subtitle_indexes]

    if rules.subtitle_mode == "5":
        return subtitles

    return []


def build_ffmpeg_command(
    input_file: Path,
    output_file: Path,
    media: MediaFile,
    rules: SelectionRules,
) -> Tuple[List[str], List[StreamInfo], List[StreamInfo]]:
    audio_keep = selected_audio_streams(media, rules)
    subtitles_keep = selected_subtitle_streams(media, rules)

    cmd = [FFMPEG_BIN, "-hide_banner"]

    if rules.overwrite:
        cmd.append("-y")
    else:
        cmd.append("-n")

    cmd += ["-i", str(input_file)]

    # Always keep all video streams. This is safer for special files with multiple video streams,
    # such as cover art or alternate angles. Usually this is just one video stream.
    cmd += ["-map", "0:v?"]

    for s in audio_keep:
        cmd += ["-map", f"0:{s.index}"]

    for s in subtitles_keep:
        cmd += ["-map", f"0:{s.index}"]

    if rules.keep_attachments:
        cmd += ["-map", "0:t?"]

    if rules.keep_metadata:
        cmd += ["-map_metadata", "0"]
    else:
        cmd += ["-map_metadata", "-1"]

    if rules.keep_chapters:
        cmd += ["-map_chapters", "0"]
    else:
        cmd += ["-map_chapters", "-1"]

    cmd += ["-c", "copy"]

    # Make the first kept audio/subtitle default.
    if audio_keep:
        cmd += ["-disposition:a:0", "default"]

    if subtitles_keep:
        cmd += ["-disposition:s:0", "default"]

    cmd += [str(output_file)]

    return cmd, audio_keep, subtitles_keep


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def sanitize_filename_part(value: str, fallback: str = "Muxed") -> str:
    cleaned = "".join("-" if ch in INVALID_FILENAME_CHARS else ch for ch in value)
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned or fallback


def language_label(value: str) -> str:
    normalized = (value or "und").lower()
    labels = {
        "ja": "JA",
        "jpn": "JA",
        "japanese": "JA",
        "en": "EN",
        "eng": "EN",
        "english": "EN",
        "fa": "FA",
        "fas": "FA",
        "per": "FA",
        "persian": "FA",
    }
    return labels.get(normalized, normalized.upper())


def compact_labels(values: Sequence[str], max_items: int = 3) -> str:
    unique = []
    for value in values:
        label = language_label(value)
        if label not in unique:
            unique.append(label)
    if not unique:
        return ""
    if len(unique) > max_items:
        return "+".join(unique[:max_items]) + "+"
    return "+".join(unique)


def stream_rule_part(kind: str, mode: str, languages: List[str], titles: List[str], indexes: List[int]) -> str:
    if kind == "audio":
        if mode == "1" and languages:
            return f"{compact_labels(languages)} Audio"
        if mode == "2" and titles:
            return "Selected Audio"
        if mode == "3" and indexes:
            return "Audio " + "+".join(str(index) for index in indexes[:4])
        if mode == "4":
            return "All Audio"
        if mode == "5":
            return "No Audio"
        return "Audio"

    if mode == "1":
        return "No Subs"
    if mode == "2" and languages:
        return f"{compact_labels(languages)} Subs"
    if mode == "3" and titles:
        return "Selected Subs"
    if mode == "4" and indexes:
        return "Subs " + "+".join(str(index) for index in indexes[:4])
    if mode == "5":
        return "All Subs"
    return "Subs"


def selection_suffix(rules: SelectionRules) -> str:
    parts = [
        stream_rule_part("audio", rules.audio_mode, rules.audio_languages, rules.audio_titles, rules.audio_indexes),
        stream_rule_part("subtitle", rules.subtitle_mode, rules.subtitle_languages, rules.subtitle_titles, rules.subtitle_indexes),
    ]

    compact: List[str] = []
    for part in parts:
        if part and part not in compact:
            compact.append(part)

    suffix = " + ".join(compact) if compact else "Muxed"
    return f"[{sanitize_filename_part(suffix)}]"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    for counter in range(2, 10000):
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find available output path for: {path}")


def unique_directory_path(path: Path) -> Path:
    if not path.exists():
        return path

    for counter in range(2, 10000):
        candidate = path.with_name(f"{path.name} ({counter})")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find available output folder for: {path}")


def resolve_output_root(input_root: Path, output_base: Path, rules: SelectionRules) -> Path:
    if input_root.is_dir():
        folder_name = sanitize_filename_part(f"{input_root.name} {selection_suffix(rules)}")
        return unique_directory_path(output_base / folder_name)

    return output_base


def make_output_path(input_root: Path, output_root: Path, input_file: Path, rules: SelectionRules) -> Path:
    if input_root.is_file():
        suffix = selection_suffix(rules)
        filename = sanitize_filename_part(f"{input_file.stem} {suffix}") + input_file.suffix
        output_file = output_root / filename
        try:
            if output_file.resolve() == input_file.resolve():
                output_file = unique_path(output_file)
        except OSError:
            pass
        if output_file.exists() and not rules.overwrite:
            output_file = unique_path(output_file)
        return output_file
    else:
        rel = input_file.relative_to(input_root)

    return output_root / rel


def display_path(input_root: Path, input_file: Path) -> Path:
    if input_root.is_file():
        return Path(input_file.name)

    try:
        return input_file.relative_to(input_root)
    except ValueError:
        return input_file


def process_files(media_files: List[MediaFile], input_root: Path, output_root: Path, rules: SelectionRules) -> None:
    print_header("PROCESSING FILES")
    started_at = time.perf_counter()
    LOGGER.info("Processing started: input=%s output=%s files=%s", input_root, output_root, len(media_files))
    LOGGER.info("Rules: %s", rules)

    total = len(media_files)
    succeeded = 0
    skipped = 0
    failed = 0

    output_root.mkdir(parents=True, exist_ok=True)

    for i, media in enumerate(media_files, start=1):
        input_file = media.path
        output_file = make_output_path(input_root, output_root, input_file, rules)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        rel = display_path(input_root, input_file)

        if output_file.exists() and not rules.overwrite:
            print(warn(f"[{i}/{total}] SKIP exists: {rel}"))
            LOGGER.warning("Skip existing output: %s", output_file)
            skipped += 1
            continue

        cmd, audio_keep, subtitles_keep = build_ffmpeg_command(input_file, output_file, media, rules)
        LOGGER.info(
            "File %s/%s: %s -> %s | audio_keep=%s subtitle_keep=%s attachments=%s",
            i,
            total,
            input_file,
            output_file,
            [s.index for s in audio_keep],
            [s.index for s in subtitles_keep],
            rules.keep_attachments,
        )

        if not media.video_streams:
            print(warn(f"[{i}/{total}] WARNING: no video stream found: {rel}"))
            LOGGER.warning("No video stream found: %s", input_file)

        if rules.audio_mode != "5" and not audio_keep:
            print(warn(f"[{i}/{total}] WARNING: no matching audio selected: {rel}"))
            LOGGER.warning("No matching audio selected: %s", input_file)

        print(info(f"[{i}/{total}] Remuxing: {rel}"))
        print(dim(f"          audio kept: {len(audio_keep)} | subtitles kept: {len(subtitles_keep)} | attachments: {'yes' if rules.keep_attachments else 'no'}"))

        proc = run_command(cmd)

        if proc.returncode == 0:
            succeeded += 1
            LOGGER.info("Remux OK: %s", output_file)
            print(ok("          OK"))
        else:
            failed += 1
            LOGGER.error("Remux failed: %s | returncode=%s", input_file, proc.returncode)
            print(err("          FAILED"))
            if proc.stderr.strip():
                print(proc.stderr.strip())

    elapsed = time.perf_counter() - started_at
    print_header("DONE")
    print(color(f"Total:   {total}", C.WHITE))
    print(ok(f"OK:      {succeeded}"))
    print(warn(f"Skipped: {skipped}"))
    print(err(f"Failed:  {failed}") if failed else ok(f"Failed:  {failed}"))
    print(info(f"Output:  {output_root}"))
    print(info(f"Total time elapsed: {format_elapsed_time(elapsed)}"))
    LOGGER.info(
        "Processing done: total=%s ok=%s skipped=%s failed=%s elapsed=%s output=%s",
        total,
        succeeded,
        skipped,
        failed,
        format_elapsed_time(elapsed),
        output_root,
    )


def verify_output(root: Path) -> None:
    print_header("VERIFY OUTPUT FOLDER")

    files = find_video_files(root)
    if not files:
        print(warn("No video files found."))
        return

    media_files = scan_files(files)

    for media in media_files:
        rel = display_path(root, media.path)

        video_count = len(media.video_streams)
        audio_count = len(media.audio_streams)
        subtitle_count = len(media.subtitle_streams)
        attachment_count = len(media.attachment_streams)

        audio_langs = ",".join(s.language for s in media.audio_streams) or "-"
        subtitle_langs = ",".join(s.language for s in media.subtitle_streams) or "-"

        status_color = C.GREEN if video_count >= 1 and audio_count >= 1 else C.YELLOW
        print(color(
            f"{rel} | video={video_count} | audio={audio_count} [{audio_langs}] | "
            f"subs={subtitle_count} [{subtitle_langs}] | attachments={attachment_count}",
            status_color,
        ))


def main_menu() -> None:
    enable_windows_ansi()
    log_path = setup_logging()
    print_header("MUXCLS")
    print("This script uses ffmpeg -c copy. It does not re-encode video, audio, or subtitles.")
    if log_path:
        print(info(f"Log file: {log_path}"))

    if not require_tool(FFMPEG_BIN):
        LOGGER.error("Required tool missing: %s", FFMPEG_BIN)
        print(err("ERROR: ffmpeg was not found in PATH."))
        print("Install FFmpeg or add ffmpeg.exe to PATH, then run this script again.")
        if LOG_FILE:
            print(info(f"Log file: {LOG_FILE}"))
        sys.exit(1)

    if not require_tool(FFPROBE_BIN):
        LOGGER.error("Required tool missing: %s", FFPROBE_BIN)
        print(err("ERROR: ffprobe was not found in PATH."))
        print("Install FFmpeg or add ffprobe.exe to PATH, then run this script again.")
        if LOG_FILE:
            print(info(f"Log file: {LOG_FILE}"))
        sys.exit(1)

    input_root = input_path_from_args(sys.argv[1:])
    if input_root is not None:
        print(info(f"Input from launcher/drag-drop: {input_root}"))
        LOGGER.info("Input from args: %s", input_root)
        if not input_root.exists():
            LOGGER.warning("Input path from args does not exist: %s", input_root)
            print(err(f"Path does not exist: {input_root}"))
            input_root = None

    if input_root is None:
        input_root = ask_path(
            "Input file or folder path (drag/drop here, then press Enter)",
            must_exist=True,
            allow_back=False,
        )
    LOGGER.info("Input root: %s", input_root)

    files = find_video_files(input_root)
    if not files:
        LOGGER.warning("No supported video files found under %s", input_root)
        print(warn("No supported video files found."))
        print(f"Supported extensions: {', '.join(sorted(VIDEO_EXTENSIONS))}")
        sys.exit(1)

    print(ok(f"Found {len(files)} video file(s)."))
    LOGGER.info("Found %s video file(s)", len(files))

    media_files = scan_files(files)
    if not media_files:
        print(err("No files could be scanned successfully."))
        sys.exit(1)

    print_scan_report(media_files, input_root)
    print_unique_summary(media_files)

    while True:
        print()
        action = ask_choice(
            "Choose action: 1=process files, 2=scan only, 3=verify another folder",
            {"1", "2", "3"},
            "1",
            allow_back=False,
        )

        if action == "2":
            LOGGER.info("User selected scan only")
            print(ok("Scan only completed."))
            return

        if action == "3":
            try:
                verify_root = ask_path("File or folder to verify", must_exist=True)
            except MenuBack:
                continue
            LOGGER.info("User selected verify folder: %s", verify_root)
            verify_output(verify_root)
            return

        break

    while True:
        try:
            rules = configure_rules(media_files)

            output_base = ask_output_base_path(input_root)
            output_root = resolve_output_root(input_root, output_base, rules)

            LOGGER.info("Configured output base: %s", output_base)
            LOGGER.info("Resolved output root: %s", output_root)

            print_header("CONFIRM SETTINGS")
            print(f"Input:  {input_root}")
            print(f"Output base: {output_base}")
            print(f"Output root: {output_root}")
            print(f"Audio mode: {rules.audio_mode}")
            print(f"Audio languages: {rules.audio_languages}")
            print(f"Audio titles: {rules.audio_titles}")
            print(f"Audio indexes: {rules.audio_indexes}")
            print(f"Subtitle mode: {rules.subtitle_mode}")
            print(f"Subtitle languages: {rules.subtitle_languages}")
            print(f"Subtitle titles: {rules.subtitle_titles}")
            print(f"Subtitle indexes: {rules.subtitle_indexes}")
            print(f"Keep attachments: {rules.keep_attachments}")
            print(f"Keep metadata: {rules.keep_metadata}")
            print(f"Keep chapters: {rules.keep_chapters}")
            print(f"Overwrite: {rules.overwrite}")
            LOGGER.info("Confirmed rules: %s", rules)

            if not ask_yes_no("Start processing?", True):
                LOGGER.info("User cancelled before processing")
                print(warn("Cancelled."))
                return

            break
        except MenuBack:
            LOGGER.info("Back requested; returning to stream selection")
            print(warn("Back. Returning to stream selection."))

    process_files(media_files, input_root, output_root, rules)

    try:
        if ask_yes_no("Verify output folder now?", True):
            verify_output(output_root)
    except MenuBack:
        LOGGER.info("Back requested after processing; verification skipped")
        print(warn("Back. Verification skipped."))


if __name__ == "__main__":
    try:
        main_menu()
    except MenuExit:
        LOGGER.info("User selected exit")
        print(warn("Exited."))
        sys.exit(0)
    except MenuBack:
        LOGGER.info("Back requested at the first menu")
        print(warn("Back is not available here."))
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        LOGGER.info("Cancelled by keyboard interrupt")
        print(warn("Cancelled by user."))
        sys.exit(130)
    except Exception as exc:
        LOGGER.exception("Unhandled error")
        print(err(f"ERROR: {exc}"))
        if LOG_FILE:
            print(info(f"Log file: {LOG_FILE}"))
        sys.exit(1)
