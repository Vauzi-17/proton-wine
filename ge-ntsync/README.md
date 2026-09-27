# GE-Proton 11.0-5 + userspace ntsync + Material 3

`ge11.0-5/` is a patch series on top of this repository's `ge11.5-ntsync`
branch (`bbce88a9`): The412Banner's GE-Proton 11.0-5 Android port (bionic,
arm64ec) with GameNative's userspace ntsync, the tree of the
`GE-proton-11.0-5-ntsync-*` releases. `build-ge11-ntsync.yml` applies it with
`git am` and builds it with that tree's scripts.

- `0001`: the ntsync fixes of the proton-cachyos 11 series. ntsync wins over
  esync, so Winlator's default `WINEESYNC=1` no longer hangs the prefix at a
  black desktop, and objects stay alive while a client waits on them. Its
  patches produce the same `server/inproc_sync.c`, esync and ntdll sync code
  as `cachyos-ntsync/p11/0001`-`0002` do there; the build fails if they did
  not land.
- `0002`: The412Banner's XP desktop (taskbar, start menu, window frames,
  `winexp.msstyles`), as carried by their proton_11.0-2 (v7) stack. The
  Material 3 desktop builds on it; the explorer, uxtheme and comctl32 files
  come out identical to proton-cachyos 11.
- `0003`-`0017`: `cachyos-ntsync/p11/0003`-`0017`, unchanged: the Material 3
  desktop, programs, visual style, menus, fonts, icons and Files.
- `0018`: uxtheme lets a theme shrink image corners instead of cutting them
  when a control is smaller than the sizing margins (`[WineSizing]
  ScaleCorners = true`); other themes draw as before.
- `0019`: pill push buttons at any height (34 pixel images, SizingMargins 16,
  ScaleCorners), and the focused push button shows the accent ring of the
  default button instead of a dotted rectangle.

After all the build-time Android patches, the Material 3 files are the same
as in the proton-cachyos 11 build.

A push that changes the series builds it and uploads the `.wcp`/`.wcp.xz`;
publishing a prerelease is Actions, this workflow, Run workflow.
