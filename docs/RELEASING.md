# Releasing Local AI

The project produces two independent artifacts:

- `Local-AI-Windows-Setup-X.Y.Z.exe` — native Windows x64-compatible system
  installer targeting `C:\Program Files\Local AI`.
- `Local-AI-WSL-Setup-X.Y.Z.run` — self-extracting WSL x86-64 system installer
  targeting `/opt/local-ai` with a systemd system service.

Both contain the compiled frontend/backend, Python runtime and dependencies,
SQLite support, and an official llama.cpp CPU fallback. Model weights are not
bundled.

## One-time repository setup

1. Put the project in a GitHub repository. The current local directory must be
   initialized and pushed before its workflows can run.
2. Protect release tags and require the source verification workflow.
3. For trusted Windows releases, acquire an Authenticode code-signing
   certificate and add these Actions secrets:
   - `WINDOWS_SIGNING_CERT_BASE64`: base64-encoded PFX bytes.
   - `WINDOWS_SIGNING_CERT_PASSWORD`: PFX password.

The Windows workflow signs and RFC 3161 timestamps both the inner application
and final installer, then verifies the final Authenticode signature. When the
secrets are absent, manual/development builds still succeed but are unsigned
and can produce a SmartScreen warning.

## Publish

```bash
git tag v1.2.0
git push origin v1.2.0
```

`.github/workflows/release.yml` then calls the native Windows and WSL builders,
downloads their artifacts, checks their per-file hashes, creates
`SHA256SUMS.txt`, and publishes the GitHub Release. The tag version is validated
and stamped into each frozen application during the build.

## Release checks

- Download both artifacts from the draft/release page, not the Actions working
  directories.
- On a clean Windows VM, verify the signature and administrator elevation,
  confirm installation under `C:\Program Files\Local AI`, confirm private data
  under `%LOCALAPPDATA%\Local AI`, test the startup task, scan a model, start/stop
  llama.cpp, and uninstall while preserving the ProgramData folder.
- On a clean supported WSL distribution, verify `SHA256SUMS.txt`, run the `.run`
  file, confirm `/api/health`, restart WSL, confirm automatic startup, and run
  `./Local-AI-WSL-Setup-X.Y.Z.run --uninstall`. `/var/lib/local-ai` data and
  models must remain.
- Confirm both light and dark themes, narrow and desktop layouts, file/folder
  indexing, streaming chat, Settings, and Cloud handoff preview/copy.

The CI smoke tests do not replace clean-machine validation for Windows signing,
GPU-specific llama.cpp downloads, WSL startup integration, or OS security UI.
