# proton-cachyos + userspace ntsync (Android, arm64ec)

Patch series that turn two upstream trees into Android (bionic) builds with
GameNative's userspace ntsync. The workflows fetch each base at a pinned
commit, `git am` the series, and build with that tree's own scripts.

| | Base | Series | Workflow |
|---|---|---|---|
| Proton 11 | [The412Banner/proton-wine](https://github.com/The412Banner/proton-wine) `1233149d` (their Android port of proton-cachyos 11) | `p11/` | `build-cachyos11-ntsync.yml` |
| Proton 10 | [CachyOS/wine-cachyos](https://github.com/CachyOS/wine-cachyos) `603c2335` (`cachyos_10.0_20260426/main`) | `p10/` | `build-cachyos10-ntsync.yml` |

`p11/0003` to `0015` add a Material 3 style to the Wine desktop and to
programs (system colors, title bars, menus, fonts, icons, the `m3.msstyles`
visual style) and Files, a Material 3 file manager based on Winlator's wfm; the
color tables, fonts, icons and theme images come from the scripts in
`m3-tools/`, which also builds Files as a standalone `wfm.exe`.

A push that changes a series builds it and uploads the `.wcp`/`.wcp.xz` as
workflow artifacts. Publishing a prerelease is manual: Actions, pick the
workflow, Run workflow.

To work on a series locally:

```sh
git clone https://github.com/CachyOS/wine-cachyos && cd wine-cachyos
git checkout 603c2335ab4b26e57512ce19aca7c8ae95485daf
git am --whitespace=nowarn /path/to/cachyos-ntsync/p10/*.patch
# ...change, commit...
git format-patch --no-signature -o /path/to/cachyos-ntsync/p10 603c2335..HEAD
```

The Android patch files inside the series (`android/patches/...`) contain
trailing whitespace in their context lines; keep `--whitespace=nowarn` (or
the default) so `git am` does not strip it.
