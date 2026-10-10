# GameNative Proton 11.0-2 + GE-Proton11-7 + userspace ntsync + Material 3

The base is GameNative's `proton_11.0-2` at `555aa70f` (their release
`proton-11.0-2-20260928`): Valve's Proton 11.0 Wine with GameNative's Android
port (bionic, arm64ec) and ntsync on `/dev/ntsync` or, without it, in
userspace through ntsync-android. `build-gn11-ntsync.yml` fetches that commit,
applies the two directories below and builds with the tree's own scripts, as
GameNative's workflow does.

## `ge-proton11-7/`

GE-Proton11-7's Wine patches (GloriousEggroll/proton-ge-custom `c191f35`),
unchanged, in the order of GE's `protonprep-valve-staging.sh`, listed in
`series`. The workflow applies them with `patch -Np1` like GE and stops on
the first one that fails. All of them apply to this base at fuzz 2 or less;
the fuzzed hunks were checked by hand.

Not carried:

- wine-staging and the Wine-Wayland (EM-11) stack: GE applies them to Valve's
  bleeding-edge Wine (`46b29104`), not to the Proton 11.0 branch this base is
  on, and this Android build has no Wayland driver.
- `layered-overlay-wine`: needs the X shape extension, which this build and
  Winlator's X server don't have.
- `nascar25-protector`: hooks a SIGSYS handler that only GE's Wine-Wayland
  stack adds; it doesn't apply here.
- `ws2_32-validate-connect-address`, `win32u-limit-extra-swapchain-image-to-doom`
  and the two three-image present-mode hotfixes: written against code this
  base doesn't have; they don't apply.
- `0001-decouple-wineopenxr-...`: there is no wineopenxr in this tree.
- `0001-fshack-Implement-AMD-FSR-...`: applies only with offsets of over two
  thousand lines in `win32u/vulkan.c`, so not trusted.
- `83-nv_low_latency_wine` (NVIDIA only), `ge-video-rework` (needs Wine's
  ffmpeg media backend; this build uses GStreamer) and `proton-ds5-haptic`
  (Linux hidraw): don't apply or don't fit Android.

## `gn11.0-2/`

Applied with `git am` on top of the GE patches.

- `0001`: Wine MR 12262, "ntdll: Ignore attempts to set reserved CPSR bits"
  (Jacek Caban, upstream `7fb24b70`, Wine bug 60405). Restoring a thread
  context keeps the host's CPSR bits, such as SSBS, instead of overwriting
  them with the Windows context. Backported by hand where this older
  `signal_arm64.c` differs.
- `0002`: two GE hotfixes change lines next to hunks of GameNative's ntdll
  loader patches, which are regenerated with a three-way merge (same
  changes). A build-time Android patch that doesn't apply now fails the
  build instead of being skipped.
- `0003`: userspace ntsync objects stay alive while a client uses them, so a
  wait no longer fails when another thread closes the last handle and an
  abandoned mutex is reported. Same fix as in the proton-cachyos 11 and
  GE-Proton 11.0-5 builds. The esync fix of those builds isn't needed: this
  tree has no esync, and wineserver turns fsync off while ntsync is in use.
- `0004`: The412Banner's XP desktop, which the Material 3 desktop builds on.
- `0005`-`0021`: the Material 3 desktop, programs, visual style, menus,
  fonts, icons, Files and pill buttons: `ge-ntsync/ge11.0-5/0003`-`0019`,
  unchanged.

A push that changes these directories builds and uploads the
`.wcp`/`.wcp.xz`. Publishing a prerelease is Actions, this workflow, Run
workflow, or a push whose commit message has `[release]`.
