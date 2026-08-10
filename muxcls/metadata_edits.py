"""Editing the metadata of the streams an output will keep.

A self-contained step inside rule configuration: which languages and indexes are
still on the table once the keep-rules are applied, and the prompt that turns the
user's answers into `StreamMetadataEdit` entries. It changes only what the output
records about a stream - the source files are never touched.

It lives apart from `selection.py` because it answers a different question. That
module decides which streams survive; this one decides what the survivors are
called.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from .colors import dim, info, ok, warn
from .models import MediaFile, SelectionRules, StreamInfo, StreamMetadataEdit
from .muxlogic import selected_audio_streams, selected_subtitle_streams
from .prompts import MenuBack, ask_csv_int_required, ask_language_code, ask_language_codes_required, ask_numbered_menu, ask_text, ask_yes_no
from .reporting import format_metadata_edit, format_metadata_edits
from .textutil import format_index_list, format_prompt_label, format_text_list, is_unknown_language, normalize_language_code


def kept_streams_for_metadata(
    media_files: List[MediaFile],
    codec_type: str,
    current_rules: Optional[SelectionRules],
) -> List[StreamInfo]:
    if current_rules is None:
        return [
            stream
            for media in media_files
            for stream in media.streams
            if stream.codec_type == codec_type
        ]

    kept: List[StreamInfo] = []
    for media in media_files:
        if codec_type == "audio":
            kept.extend(selected_audio_streams(media, current_rules))
        elif codec_type == "subtitle":
            kept.extend(selected_subtitle_streams(media, current_rules))
    return kept


def kept_languages_for_metadata(
    media_files: List[MediaFile],
    codec_type: str,
    current_rules: Optional[SelectionRules],
) -> List[str]:
    return sorted({
        normalize_language_code(stream.language)
        for stream in kept_streams_for_metadata(media_files, codec_type, current_rules)
    })


def kept_indexes_for_metadata(
    media_files: List[MediaFile],
    codec_type: str,
    current_rules: Optional[SelectionRules],
) -> List[int]:
    return sorted({
        stream.index
        for stream in kept_streams_for_metadata(media_files, codec_type, current_rules)
    })


def ask_metadata_edits(
    media_files: List[MediaFile],
    initial_edits: Optional[Sequence[StreamMetadataEdit]] = None,
    current_rules: Optional[SelectionRules] = None,
) -> List[StreamMetadataEdit]:
    current_edits = list(initial_edits or [])
    audio_languages_available = kept_languages_for_metadata(media_files, "audio", current_rules)
    subtitle_languages_available = kept_languages_for_metadata(media_files, "subtitle", current_rules)
    unknown_audio_found = any(is_unknown_language(value) for value in audio_languages_available)
    unknown_subtitle_found = any(is_unknown_language(value) for value in subtitle_languages_available)
    default_action = "1" if unknown_audio_found else "2" if unknown_subtitle_found else "8"

    while True:
        print()
        print("Edit Output Metadata:")
        print(dim("  Edits apply only to output audio/subtitle streams that are kept. Input files are not changed."))
        if current_edits:
            print(info(f"  Current edits: {format_metadata_edits(current_edits)}"))

        edit_enabled = ask_yes_no("Edit output stream metadata?", bool(current_edits))
        if not edit_enabled:
            return []

        while True:
            if current_edits:
                print(info(f"Current metadata edits: {format_metadata_edits(current_edits)}"))

            try:
                action = ask_numbered_menu(
                    "Metadata edit actions",
                    (
                        ("1", "set audio language by current language"),
                        ("2", "set subtitle language by current language"),
                        ("3", "set audio language by exact stream indexes"),
                        ("4", "set subtitle language by exact stream indexes"),
                        ("5", "set audio title by exact stream indexes"),
                        ("6", "set subtitle title by exact stream indexes"),
                        ("7", "clear metadata edits"),
                        ("8", "done"),
                    ),
                    default_action if not current_edits else "8",
                    "Choose metadata edit",
                    leading_blank=True,
                )
            except MenuBack:
                print(warn("Back. Returning to metadata edit question."))
                break

            if action == "8":
                return current_edits

            if action == "7":
                current_edits = []
                print(warn("Metadata edits cleared."))
                continue

            try:
                if action in {"1", "2"}:
                    codec_type = "audio" if action == "1" else "subtitle"
                    available_languages = audio_languages_available if codec_type == "audio" else subtitle_languages_available
                    if not available_languages:
                        print(warn(f"No kept {codec_type} streams are available for metadata editing."))
                        continue
                    print(format_prompt_label(f"Current {codec_type} languages found: {format_text_list(available_languages)}"))
                    current_languages = ask_language_codes_required(
                        f"Current {codec_type} language code(s) to edit from the list above, (example: *uknown,jpn)"
                    )
                    new_language = ask_language_code(f"New {codec_type} language code, (example: jpn)")
                    current_edits.append(StreamMetadataEdit(
                        codec_type=codec_type,
                        match_languages=current_languages,
                        language=new_language,
                    ))
                    print(ok(f"Added metadata edit: {format_metadata_edit(current_edits[-1])}"))
                    continue

                codec_type = "audio" if action in {"3", "5"} else "subtitle"
                available_indexes = kept_indexes_for_metadata(media_files, codec_type, current_rules)
                if not available_indexes:
                    print(warn(f"No kept {codec_type} streams are available for metadata editing."))
                    continue
                print(format_prompt_label(f"Current {codec_type} indexes found: {format_index_list(available_indexes)}"))
                indexes = ask_csv_int_required(
                    f"{codec_type.capitalize()} stream indexes to edit from the list above, (example: 2,3)",
                    available_indexes,
                )

                if action in {"3", "4"}:
                    new_language = ask_language_code(f"New {codec_type} language code, (example: jpn)")
                    current_edits.append(StreamMetadataEdit(
                        codec_type=codec_type,
                        match_indexes=indexes,
                        language=new_language,
                    ))
                else:
                    new_title = ask_text(f"New {codec_type} title")
                    current_edits.append(StreamMetadataEdit(
                        codec_type=codec_type,
                        match_indexes=indexes,
                        title=new_title,
                    ))

                print(ok(f"Added metadata edit: {format_metadata_edit(current_edits[-1])}"))
            except MenuBack:
                print(warn("Back. Returning to metadata edit actions."))
