# Final Report — BORE scheduler on CachyOS linux 7.1-rc

**Objective:** Determine if `linux-cachyos-bore` (configured for stable 7.0.10) can be safely ported to a BORE config for the 7.1 release-candidate kernel, using `linux-cachyos-rc` (already 7.1) as reference.

**Strategy:** red_team_validation. Workers: architect (port design), red_team (failure hunting), arbiter (ground-truth + synthesis + validation).

## Determination
Yes, BORE-on-7.1 is achievable and safe — but **not** by finishing the hand-edit of the bore dir. The safe path is to drive the already-7.1 `linux-cachyos-rc` dir with `_cpusched=bore`.

## Key validated facts
1. **BORE is not in the config file.** It is applied by PKGBUILD `prepare()` via `scripts/config -e SCHED_BORE`. Both base configs carry identical `# CONFIG_SCHED_BORE is not set`; a scheduler/LTO/CACHY/LOCALVERSION diff of the two configs returns zero lines. The two configs differ ONLY by 7.0.10->7.1 version/policy churn (~200 lines: new 7.1 symbols; 7.1 drops legacy HAMRADIO/ATM/ISDN/mISDN gates).
2. The hand-edited bore PKGBUILD (hardcoded second `source=()` at lines 252-261) has **four** build-breaking defects:
   - CRITICAL: 9 sources vs 3 b2sums -> makepkg integrity error before prepare().
   - CRITICAL: the 7.1 bore patch fails on the 7.0.10 tarball (fork.c #3, fair.c #11/#16 FAILED; proven by `patch --dry-run`).
   - HIGH: NVIDIA patches given as `file://` never match the `${_patchsource}/misc/nvidia/*` router -> applied to the kernel tree -> "can't find file to patch".
   - HIGH: `dkms-clang.patch` already present in the release tarball -> "Reversed (or previously applied)" -> non-zero exit under set -e.
3. Root cause = version skew the user must manage by hand (7.1 patches vs 7.0.10 tarball).

## Recommendation — Strategy B (validated with `makepkg --printsrcinfo`)
On `/home/jangmanj/.cache/cachyos-km/pkgbuilds/linux-cachyos-rc/`:
- GCC flavor (closest to the bore package): `_cpusched=bore` (line 23) + `_use_llvm_lto=none` (line 95) -> 3 sources, pkgbase `linux-cachyos-rc-gcc`, pkgver 7.1.rc4. Run `updpkgsums` then `makepkg -s`.
- ThinLTO flavor: `_cpusched=bore` only -> 4 sources, pkgbase `linux-cachyos-rc`. Needs `updpkgsums` (4th sum for bore patch).
Why safer: tarball and bore patch are both pulled from CachyOS's 7.1 branch (a matched, upstream-tested set), eliminating the version-mismatch class that broke the hand-edit. One functional edit vs ~11 for porting the bore dir; no config swap; no manual patch staging.

## Remaining risk
- 7.1-rc + clang/ThinLTO is the heavier combo; GCC/no-LTO most closely reproduces the known-good bore build.
- Package is named `linux-cachyos-rc[-gcc]`, not `linux-cachyos-bore` (suffix hardcoded in rc PKGBUILD lines 168-174). Cosmetic; rename only if desired.
- cachyos-kernel-manager may regenerate these cache dirs; the manual `makepkg` build is independent of km.
