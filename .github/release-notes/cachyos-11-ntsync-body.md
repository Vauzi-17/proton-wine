Test build. Install into a fresh arm64ec container.

proton-cachyos 11 (Wine 11, CachyOS/wine-cachyos `b5f2dc7b`, release `cachyos-11.0-20260703-slr`) for Android, from [The412Banner's bionic port](https://github.com/The412Banner/proton-wine/tree/wip/proton_11.0-cachyos) at `1233149d`, plus userspace ntsync from [GameNative/ntsync-android](https://github.com/GameNative/ntsync-android).

The412Banner's port includes their Android stack: esync (re-added for Wine 11), DirectAudio, the FEX unixlib loader, XInput and EA network fixes, and their XP-style desktop.

## ntsync

The userspace ntsync patches are the ones from the GE-Proton 11.0-5 ntsync build; they produce the same code on this tree. wineserver chooses the backend once at startup:

1. `/dev/ntsync`, if it opens and a test object can be created on it
2. otherwise userspace ntsync, in a shared memory region under `$TMPDIR` (or `$NTSYNC_SHM`)
3. otherwise esync if `WINEESYNC=1`, else server-side synchronization

**Unlike the 11.0-5 ntsync build, esync can stay on.** There, `WINEESYNC=1` (Winlator's default) started esync in wineserver and still selected ntsync, and a prefix hung on startup (reproduced natively: `wineboot` never finished). Here ntsync takes precedence in wineserver and in every process.

This build also fixes a lifetime bug in the userspace backend (also present in the 11.0-5 ntsync build): closing the last handle to an object while another thread waited on it failed that wait, and an abandoned mutex was not reported. Clients now keep the object alive while they use it.

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

- Not tested on an Android device. If a game misbehaves, compare with `PROTON_NO_NTSYNC=1`.
- This tree has no x86_64 build here, only arm64ec.
