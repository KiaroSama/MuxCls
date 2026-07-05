# Security Policy

## Supported versions

MuxCls is a small, actively maintained utility. Only the latest released version receives
fixes. Please make sure you are on the newest version (see the top of `README.md` and
`CHANGELOG.md`) before reporting an issue.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Instead, report privately using GitHub's **Report a vulnerability** feature under the
repository's **Security** tab (Security advisories). Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept.
- The MuxCls version, OS, Python version, and FFmpeg version.

You can expect an initial acknowledgement within a reasonable time. Please allow time for a
fix before any public disclosure.

## Scope and notes

- MuxCls runs `ffmpeg`, `ffprobe`, and `robocopy` from your system `PATH` and processes
  local files you point it at. It does not make network requests.
- Never include real secrets, tokens, or private media in a report. Redact local paths and
  any sensitive values from logs before sharing them.
