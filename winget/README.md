# winget package manifests

These are the [winget](https://learn.microsoft.com/windows/package-manager/) manifests for
`omniV1.DayZServerControlCenter`. Once accepted into the community repo, anyone can install the
desktop app with:

```powershell
winget install omniV1.DayZServerControlCenter
```

The package is a portable app: winget downloads the release `.zip`, extracts it, and registers a
`DayZServerControlCenter` command alias. Nothing runs during install.

## Files

The three manifests live in `manifests/` (kept in their own folder so `winget validate` only sees
YAML, not this README):

| File | Manifest type |
|---|---|
| `manifests/omniV1.DayZServerControlCenter.yaml` | version (points at the default locale) |
| `manifests/omniV1.DayZServerControlCenter.locale.en-US.yaml` | metadata (name, description, license, tags) |
| `manifests/omniV1.DayZServerControlCenter.installer.yaml` | the zip download URL + SHA-256 + nested portable exe |

## Updating for a new release

Each new version needs its `PackageVersion`, the release `InstallerUrl`, and the `InstallerSha256`
updated (the SHA-256 is printed by `build_control_center_exe.ps1` and is in the release's `.sha256`
asset). The easiest way is [`wingetcreate`](https://github.com/microsoft/winget-create):

```powershell
winget install Microsoft.WingetCreate
wingetcreate update omniV1.DayZServerControlCenter `
  --version 1.6.2 `
  --urls https://github.com/omniV1/DayZServer-Expansion-Configs/releases/download/v1.6.2/DayZServerControlCenter-1.6.2-windows.zip `
  --submit
```

`wingetcreate` downloads the zip, computes the hash, regenerates the manifests, validates them, and
opens the PR to `microsoft/winget-pkgs` for you.

## Submitting manually (first time)

1. Validate locally:

   ```powershell
   winget validate --manifest winget\manifests
   ```

2. Test the install against a local manifest (run from an elevated prompt; enable local manifests
   once with `winget settings --enable LocalManifestFiles`):

   ```powershell
   winget install --manifest winget\manifests
   ```

3. Fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs), copy the three files from
   `winget/manifests/` to `manifests/o/omniV1/DayZServerControlCenter/1.6.2/` in your fork, and open a
   PR. Automated validation runs on the PR; a maintainer reviews and merges.

## Notes

- The release zip must stay published at the exact `InstallerUrl` — winget hashes that URL. Don't
  delete or re-upload the asset for a version that's already in the repo.
- Signing is not required for winget, but a signed exe reduces SmartScreen friction for everyone
  (see the build script's `-CertThumbprint` option). If you start signing, just rebuild and update
  the `InstallerSha256` for the new release as usual.
