# Contributing to MuxCls

Thanks for your interest in improving MuxCls. This is a cross-platform, Python 3 FFmpeg
helper that remuxes media with stream copy (`ffmpeg -c copy`) - it never re-encodes.

## Getting started

1. Fork and clone the repository.
2. Make sure `ffmpeg` and `ffprobe` are available in `PATH` (`ffmpeg -version`).
3. Install the test dependencies:

   ```powershell
   python -m pip install -r requirements-dev.txt
   ```

4. Run the app from the project folder:

   ```powershell
   .\run.ps1
   ```

## Project layout

The application logic lives in the `muxcls/` package, split by responsibility
(see the "Project Structure" table in `README.md`). `MuxCls.py` is a thin entry point.

## Making changes

- Keep the code style consistent with the existing modules.
- Preserve the stream-copy design: do not add re-encoding to the core workflow.
- Update `README.md` and `CHANGELOG.md` when you change behavior, options, or structure.
- Keep the core logic separate from the interactive/console layer where practical.

## Testing

Run the full suite before opening a pull request:

```powershell
python -m pytest tests -v
```

- Unit tests are fast and require no external tools.
- End-to-end tests in `tests/test_processing_e2e.py` require `ffmpeg`/`ffprobe`; they skip
  automatically if unavailable. The robocopy overwrite tests additionally require Windows.
- Add or update tests for any behavior you change or fix.
- For changes the automated suite cannot judge (console output, menu flow, progress
  display), walk the matching section of `docs/MANUAL_QA.html` and record the result there.

CI also lints, typechecks and measures coverage. Run the same three locally
before opening a pull request:

```powershell
python -m ruff check muxcls tests MuxCls.py
python -m mypy muxcls MuxCls.py --ignore-missing-imports
python -m pytest tests --cov=muxcls --cov-report=term-missing
```

The coverage number is reported, not enforced - the missing-line list is the
useful part, since it names the paths nothing exercises.

CI (`.github/workflows/tests.yml`) runs the suite on `windows-latest` and
`ubuntu-latest` across Python 3.11-3.13 for every push and pull request, and
lints/typechecks once on the primary combination. A second workflow
(`.github/workflows/codeql.yml`) runs CodeQL analysis.

## What not to commit

- Secrets, tokens, or credentials.
- Real or copyrighted media files.
- Local-only files: `Logs/`, `secrets.md`, `.ignoreme/`, generated `graphify-out/`.

## License

By contributing, you agree that your contributions are licensed under the project's MIT
License, and you preserve the existing copyright and attribution notices.
