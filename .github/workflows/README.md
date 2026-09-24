# GE-Proton 10.0-34 + userspace ntsync

`build-proton.yml` builds one arm64ec (bionic, API 28, 16 KB pages) layer:

- Base: The412Banner's GE-Proton 10.0-34 layer (`proton_10.34-GE` @ `af34ea7a`): Valve Proton 10.0,
  GameNative's Android patches, GE-Proton10-34 game fixes, DirectAudio, FEX unixlib loader and more.
- ntsync: Elizabeth Figura's in-process synchronization series from CachyOS/wine-cachyos
  (`cachyos_10.0_20260426/main`), cherry-picked into the source tree.
- Userspace ntsync: GameNative/ntsync-android (pinned by `NTSYNC_ANDROID_REF`), linked statically
  into `ntdll.so` and `wineserver` as a second backend for devices without `/dev/ntsync`.

## Build order

1. autogen (regenerates the server protocol, spec files and configure), wine-tools
2. `--build-sysvshm`, then `--build-ntsync-android`: configure needs `libntsync_android.a` in
   `$deps/lib` to define `HAVE_NTSYNC_ANDROID`
3. `--configure` (fails if the library was not detected), Android patches, GE patches
4. `--build`, `--install` (fails if `wineserver`/`ntdll.so` lack the userspace code)
5. 16 KB alignment check, pinned prefixPack, `.wcp` (zstd) + `.wcp.xz` packaging

## Release

Every push to the branch (and every manual run) publishes a prerelease tagged
`GE-proton-10.0-34-ntsync-YYYYMMDD-<run>`, with notes from
`.github/release-notes/ge-10.0-34-ntsync-body.md`. Add `[skip ci]` to a commit message to skip it.
