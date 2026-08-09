from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .constants import APP_VERSION
from .colors import warn

LOGGER = logging.getLogger("MuxCls")


LOG_FILE: Optional[Path] = None


# Set MUXCLS_DEBUG=1 to record command lines and captured output for every
# command. The default INFO level keeps a run of a few hundred files readable.
DEBUG_ENV_VAR = "MUXCLS_DEBUG"


# Captured stdout/stderr is only useful up to a point; a full FFmpeg dump can be
# thousands of lines and buries the entries that matter.
MAX_CAPTURED_OUTPUT_CHARS = 2000


def debug_enabled() -> bool:
    return os.environ.get(DEBUG_ENV_VAR, "").strip().lower() not in {"", "0", "false", "no"}


def command_to_text(args: Sequence[object]) -> str:
    return subprocess.list2cmdline([str(arg) for arg in args])


def truncate_output(text: str, limit: int = MAX_CAPTURED_OUTPUT_CHARS) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + f"... [{len(stripped) - limit} more characters]"


def log_command_output(label: str, returncode: int, stdout: str, stderr: str) -> None:
    """Record captured output only when it can explain something: a failure, or
    an explicit debug run. Successful commands stay a single line."""
    failed = returncode != 0
    if not failed and not debug_enabled():
        return

    level = logging.ERROR if failed else logging.DEBUG
    if stdout.strip():
        LOGGER.log(level, "%s stdout: %s", label, truncate_output(stdout))
    if stderr.strip():
        LOGGER.log(level, "%s stderr: %s", label, truncate_output(stderr))


def setup_logging() -> Optional[Path]:
    global LOG_FILE

    try:
        # This module lives in the muxcls package, so the project root (where the
        # Logs folder belongs) is the parent of the package directory.
        log_root = Path(__file__).resolve().parent.parent / "Logs"
        log_root.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        LOG_FILE = log_root / f"muxcls_{started}_UTC.log"

        level = logging.DEBUG if debug_enabled() else logging.INFO
        LOGGER.setLevel(level)
        LOGGER.handlers.clear()
        LOGGER.propagate = False

        formatter = logging.Formatter(
            "[%(asctime)s UTC] [%(levelname)s] [%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        formatter.converter = time.gmtime
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)

        LOGGER.info(
            "MuxCls %s started | python=%s | os=%s | log=%s",
            APP_VERSION,
            sys.version.split()[0],
            platform.platform(),
            LOG_FILE,
        )
        LOGGER.debug("Command line: %s", command_to_text(sys.argv))
        return LOG_FILE
    except OSError as exc:
        print(warn(f"Logging disabled: {exc}"))
        LOG_FILE = None
        return None
