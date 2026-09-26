Test build. Install into a fresh arm64ec container.

proton-cachyos 10 (Wine 10, [CachyOS/wine-cachyos](https://github.com/CachyOS/wine-cachyos) `cachyos_10.0_20260426/main`) for Android, with userspace ntsync from [GameNative/ntsync-android](https://github.com/GameNative/ntsync-android).

This is a new Android port of proton-cachyos 10:

- **Android stack:** GameNative's Proton 10 patch set with The412Banner's bionic fixes (SD-card boot, drive-root copy guard, C.UTF-8 locale, EA network fixes, XInput), regenerated for the CachyOS tree.
- **ARM64EC:** bylaws' ARM64EC/FEX patches are not applied on top, because CachyOS already carries newer versions of them in-tree.
- **Small fixes:** `WINE_FAST_YIELD`, `WINEVMEMMAXSIZE`, the font-handle cap, and the RtlIsEcCode bounds check (Denuvo / NFS Heat).
- **Not included:** DirectAudio, the GE game fixes, and the FEX unixlib load-by-name loader (GameNative's own Proton 10 doesn't use it either).

## ntsync

CachyOS 10 already has in-process ntsync (Elizabeth Figura's series). This build adds a userspace backend for devices without `/dev/ntsync`, the same code as in the GE-Proton 10.0-34 ntsync build. wineserver chooses once at startup:

1. `/dev/ntsync`, if it opens and a test object can be created on it
2. otherwise userspace ntsync, in a shared memory region under `$TMPDIR` (or `$NTSYNC_SHM`)
3. otherwise esync/fsync, else server-side synchronization

esync and fsync switch off automatically in wineserver and every process while ntsync is active, so the esync setting doesn't need to be turned off.

## Environment variables

- `PROTON_NO_NTSYNC=1`: disable ntsync (`WINE_DISABLE_FAST_SYNC=1` and `WINENTSYNC=0` do the same)
- `PROTON_NO_KERNEL_NTSYNC=1`: use userspace ntsync even when `/dev/ntsync` works
- `NTSYNC_SHM=/path/file.shm`: shared region path, if processes don't share a `TMPDIR`

## Files

- `proton-cachyos-10.0-ntsync-arm64ec.wcp`: GameNative / Bannerlator / WinNative
- `proton-cachyos-wine-10.0-ntsync-arm64ec.wcp.xz`: Winlator CMOD & Ludashi

`versionName` is `10.0-20260426-arm64ec`.

## Testing

The same source (without the Android-only patches) was built natively for x86_64 Linux without `/dev/ntsync`, so the userspace backend was in use, with fsync off as on Android:

- Wine's `ntdll` and `kernel32` tests for `sync`, `thread`, `process` and `om` give the same results with userspace ntsync as with server-side synchronization; the `sync` tests also with `WINEESYNC=1`.
- A focused test (events, semaphores, mutexes, wait-all, message-queue waits, alertable APCs, named objects across processes, `WAIT_ABANDONED` after the owner exits) passes.
- Event ping-pong: 38 µs per round trip with userspace ntsync, 42 µs with esync, 63 µs with server-side synchronization.

## Known limitations

- Not tested on an Android device. The ARM64EC layer comes from CachyOS rather than GameNative's patches, which makes this build the riskier of the two. If a game misbehaves, compare with `PROTON_NO_NTSYNC=1` first, then with the GE-Proton 10.0-34 ntsync build.
