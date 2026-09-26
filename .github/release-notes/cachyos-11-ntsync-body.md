Test build of proton-cachyos 11 for Android (arm64ec) with userspace ntsync and a Material 3 desktop. **Install into a new container.**

## What's new

- **ntsync**: `/dev/ntsync` when the device has it, otherwise userspace ntsync. Works with esync on.
- **Material 3 desktop**: taskbar, launcher and a settings page (color, light/dark, taskbar).
- **Material 3 programs**: title bars, buttons, scroll bars, menus, Roboto font and icons.
- **Files**: a Material 3 file manager that replaces Winlator's `wfm.exe` (the original is kept as `wfm-winlator.exe`; switch in settings).

## Downloads

- `proton-cachyos-wine-11.0-ntsync-arm64ec.wcp.xz`: Winlator CMOD & Ludashi
- `proton-cachyos-11.0-ntsync-arm64ec.wcp`: GameNative / Bannerlator / WinNative

## Notes

- An older container won't get Files or the Material controls: create a new one.
- `WINE_TASKBAR_STYLE=xp` or `classic` brings back the old desktop; try `PROTON_NO_NTSYNC=1` if a game misbehaves.

Based on [The412Banner's proton-cachyos 11 port](https://github.com/The412Banner/proton-wine/tree/wip/proton_11.0-cachyos) and [GameNative/ntsync-android](https://github.com/GameNative/ntsync-android). [Full notes](https://github.com/Vauzi-17/proton-wine/blob/claude/proton-10-ntsync-compile-20dq12/cachyos-ntsync/NOTES-p11.md).
