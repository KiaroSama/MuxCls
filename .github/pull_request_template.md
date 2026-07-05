## Summary

Briefly describe what this change does and why.

## Checklist

- [ ] `python -m pytest tests` passes locally.
- [ ] `python -m py_compile MuxCls.py` and the `muxcls/` modules compile cleanly.
- [ ] The change was tested through the real entry point (`.\run.ps1` or `python MuxCls.py`).
- [ ] No secrets, real media, private paths, or local-only files (`Logs/`, `secrets.md`, `.ignoreme/`) are included.
- [ ] `README.md` and `CHANGELOG.md` are updated when behavior, options, or structure change.
- [ ] Behavior still uses FFmpeg stream copy only (no re-encoding).
