# Portable LVGL C toolchain

The compressed `win-x64` payload is bundled under `assets/toolchains/` and the
expanded `runtime/toolchain/win-x64/` cache is intentionally ignored by Git.
Native rendering verifies and extracts the local ZIP lazily; no network access
or machine-wide compiler installation is required.

Pre-extract and verify the bundled payload manually when desired:

```powershell
.\scripts\install_toolchain.cmd
python scripts\compiler_self_test.py
```

Install an unpublished/local package:

```powershell
.\scripts\install_toolchain.cmd -ArchivePath .\dist\lvgl-ui-toolchain-win-x64-16.1.0-r1.zip
```

The ZIP must have a sibling `.sha256` file. Installation validates the archive,
every payload file, required compiler programs, and a compile/run smoke test.
It does not modify the machine-wide `PATH`.
