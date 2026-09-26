# proton-cachyos 11 + userspace ntsync: full notes

The release notes are a short version of this page.

proton-cachyos 11 (Wine 11, CachyOS/wine-cachyos `b5f2dc7b`, release `cachyos-11.0-20260703-slr`) for Android, from [The412Banner's bionic port](https://github.com/The412Banner/proton-wine/tree/wip/proton_11.0-cachyos) at `1233149d`, plus userspace ntsync from [GameNative/ntsync-android](https://github.com/GameNative/ntsync-android).

The412Banner's port includes their Android stack: esync (re-added for Wine 11), DirectAudio, the FEX unixlib loader, XInput and EA network fixes, and their XP-style desktop.

## ntsync

The userspace ntsync patches are the ones from the GE-Proton 11.0-5 ntsync build; they produce the same code on this tree. wineserver chooses the backend once at startup:

1. `/dev/ntsync`, if it opens and a test object can be created on it
2. otherwise userspace ntsync, in a shared memory region under `$TMPDIR` (or `$NTSYNC_SHM`)
3. otherwise esync if `WINEESYNC=1`, else server-side synchronization

**Unlike the 11.0-5 ntsync build, esync can stay on.** There, `WINEESYNC=1` (Winlator's default) started esync in wineserver and still selected ntsync, and a prefix hung on startup (reproduced natively: `wineboot` never finished). Here ntsync takes precedence in wineserver and in every process.

This build also fixes a lifetime bug in the userspace backend (also present in the 11.0-5 ntsync build): closing the last handle to an object while another thread waited on it failed that wait, and an abandoned mutex was not reported. Clients now keep the object alive while they use it.

## Desktop: Material 3 style (new default)

The Wine desktop (explorer) gets a Material 3 look in place of The412Banner's XP style: a flat taskbar with a launcher button, pill shaped task buttons and a two line clock; a launcher sheet (user, built-in programs, start menu shortcuts, places) instead of the start menu; and a background of translucent circles in place of the app's default wallpaper.

- **Desktop settings** (the palette button of the launcher, or right click the desktop, Display Properties): style (Material 3, Windows XP, Classic), color (purple, blue, teal, green, orange, pink), brightness (auto follows the app's light or dark theme, light, dark), clock, taskbar rows and background. Changes apply at once.
- `WINE_TASKBAR_STYLE=xp` or `classic` brings back the other styles.
- Fonts: Roboto and Material Symbols (Apache 2.0). Roboto is also copied into `C:\windows\Fonts` for window titles.
- The launcher's rounded corners are painted with what is behind it (the desktop, then the windows under it). Winlator's X server has no shape extension, so the window region used before showed up as a white square around the sheet.

### Programs in Material 3 (wfm, winecfg, dialogs, ...)

With the Material 3 style, programs follow the desktop's color and brightness:

- **Colors**: window, menu, selection and button colors come from the Material 3 scheme (switch "Material colors in programs"). The app's own colors (Winlator's light or dark theme) are restored when it is off or another style is chosen.
- **Title bars**: flat title bars in the scheme's surface color, title in Roboto Medium, thin caption glyphs; the close button turns red when pressed.
- **Buttons and controls** (switch "Material buttons and controls"): a new visual style, `m3.msstyles`, with tonal pill buttons (the default button has an accent outline), Material check boxes and radio buttons, outlined edit and combo boxes with chevrons, thin scroll bar thumbs, tabs with an accent indicator, rounded group boxes and tab pages, header and toolbar hover states, tree view chevrons, slider handles and dark tooltips. Twelve color schemes (six colors, light and dark) share one set of images: uxtheme recolors them when it loads them.
- Changing the color or brightness in the settings updates programs that are already running (Wine cached the system colors per process; running programs now reload them).

- **Menus**: taller items, rounded hover, no embossed gray text, clean check marks and arrows, shortcuts on the right; the menu bar has the color of the title bar.
- **Font** (switch "Roboto font in programs", on by default): Roboto for dialogs, menus, status bars and message boxes. Roboto is about 3% wider than Tahoma at the same size, so a tight label may lose a letter; the switch brings Tahoma back.
- **Icons**: Material folder, drive, computer and documents icons in file dialogs and other shell views.

### Files: a Material 3 file manager

`files.exe`, opened from the launcher's Files tile, the Drives chip and the folder chips: Winlator File Manager (wfm by BrunoSX, MIT) redone in Material 3. A top app bar (up, breadcrumbs with folder menus, a path field, refresh, search, more), an action bar (copy, cut, paste, delete, new folder, new file, list or grid), a navigation drawer, rounded rows and tiles with Material icons (program and shortcut icons stay their own), an empty folder state, keyboard shortcuts (Del, F2, F5, Backspace, Ctrl+C/X/V/A), and the desktop's color and brightness. ISO, BIN/CUE images load without libcdio. English, Portuguese, Russian and Indonesian.

**Files is the default file manager** (switch "Files as the file manager", on by default, Material 3 style only):

- Winlator starts `C:\windows\wfm.exe` when a container opens without a shortcut. When the desktop starts, that file is replaced by a copy of Files and Winlator's own is kept as `C:\windows\wfm-winlator.exe`. Turning the switch off or choosing another style puts Winlator's back.
- Winlator writes its `wfm.exe` again when the app or the prefix is updated; it is replaced again at the next start.
- Folders that programs open through the shell (`explorer.exe <folder>`) open in Files.
- Winlator's File Manager menu entries (the 7-Zip "Open Archive / Extract" items in `HKCU\Software\Winlator\WFM\ContextMenu`) and the CD drive (X:) ISO loading work in Files as in wfm.

Files can still be built as a standalone `wfm.exe` for other Wine builds (`m3-tools/build-wfm.sh`).

**Use a new container.** Winlator turns off Wine's prefix updates, so a container made with an earlier build doesn't get `files.exe` or `C:\windows\resources\themes\m3\m3.msstyles`: without them the file manager stays wfm and the controls keep the previous theme.

Programs that draw their own controls or colors keep their look.

## Environment variables

- `PROTON_NO_NTSYNC=1`: disable ntsync; esync is used if `WINEESYNC=1`
- `PROTON_NO_KERNEL_NTSYNC=1`: use userspace ntsync even when `/dev/ntsync` works
- `NTSYNC_SHM=/path/file.shm`: shared region path, if processes don't share a `TMPDIR`

## Files

- `proton-cachyos-11.0-ntsync-arm64ec.wcp`: GameNative / Bannerlator / WinNative
- `proton-cachyos-wine-11.0-ntsync-arm64ec.wcp.xz`: Winlator CMOD & Ludashi

`versionName` is `11.0-20260703-arm64ec` like The412Banner's build of this tree; the Proton `versionCode` is 2 so both can be installed side by side.

## Testing

The same source was built natively for x86_64 Linux without `/dev/ntsync` (userspace backend, fsync off as on Android):

- Wine's `ntdll` and `kernel32` tests for `sync`, `thread`, `process` and `om` give the same results with userspace ntsync as with server-side synchronization; the `sync` tests also with `WINEESYNC=1`.
- A focused test (events, semaphores, mutexes, wait-all, message-queue waits, alertable APCs, named objects across processes, `WAIT_ABANDONED` after the owner exits) passes in every mode.
- Event ping-pong: 34-39 µs per round trip with userspace ntsync, 62 µs with server-side synchronization.

## Known limitations

- The Material 3 desktop was tested in a native build under Xvfb (1280x720, light and dark, one and two taskbar rows); the programs part (wfm, Files, winecfg, notepad, file dialogs, switching colors while they run) the same way, and the wfm replacement with Winlator's own `winhandler.exe` and `wfm.exe`. On a device, the taskbar, launcher and settings page of an earlier build have been seen; this build's title bars, controls, menus and Files have not.
- The launcher's corners show a window under them as it was when the launcher opened; a game drawing with Vulkan or OpenGL may show as black there.
- Running programs keep their fonts until they restart, and the shell icons change for new programs only.

- Not tested on an Android device. If a game misbehaves, compare with `PROTON_NO_NTSYNC=1`.
- This tree has no x86_64 build here, only arm64ec.
