# protondb-tuner — ARC Raiders  (appId 1808500)

🟢 **Playable** — 93% of the last 694 reports run. Anti-cheat is currently accepted on Linux.

> Anti-cheat acceptance is publisher-set and can flip on a patch date — a *recency-windowed* read, not a config you can force. (Status is inferred from online-play + EAC-runtime reports; the structured anti-cheat field is often empty.)

## Suggested configuration for your system
_Profile: NVIDIA · wayland · cachyos · hybrid laptop · priority: **parity**_

_Auto-detected host: GPU NVIDIA, INTEL (primary NVIDIA, hybrid) · open kmod 595.71.05 · wayland/KDE · CachyOS Linux · kernel 7.0.9-1-cachyos · ntsync yes._

**Foundation — maximize native parity (do these first):**
- **Runtime:** proton-cachyos (or GE-Proton, e.g. GE-Proton10-25) under Steam Linux Runtime 3 ("sniper").  On your GPU, GE-class builds run best in the data (ge 96%@115rpts, official 88%@161rpts, experimental 83%@108rpts).
  - ✓ **Installed on this host:** `proton-cachyos-11.0-20260506-slr-x86_64_v3` — select it in the game's Properties → Compatibility dropdown.
- **Anti-cheat:** add no flag. This title's EAC is dev-enabled and loads automatically; a bypass would risk a ban and gain nothing.
- _PROTON_USE_EAC_LINUX=1_ / _PROTON_EAC_RUNTIME=1_ — Usually unnecessary: the anti-cheat runtime is provided automatically by modern Proton for this title (most working reports set no anti-cheat flag).

**Recommended — low-risk fidelity / performance gains, attested on your hardware**
- `PROTON_ENABLE_WAYLAND=1` ·_game-specific_ — WHY: Makes Proton render through a native Wayland surface instead of going through XWayland. Can lower latency, improve frame pacing, and enable HDR without gamescope — but it is experimental and currently breaks the Steam overlay and Steam Input on many titles. (how: better latency/pacing and HDR on a Wayland session. why: also needed by some setups to avoid XWayland quirks. Directly relevant on this Wayland/KDE box, with the overlay/input caveat.) _(risk: low; risk relaxed: 67 NVIDIA reports at 97% runs-rate)_
- `PROTON_USE_NTSYNC=1` ·_game-specific_ — HOW: Tells Proton to use NTSYNC for Wine thread synchronization instead of esync/fsync. NTSYNC is an in-kernel driver (CONFIG_NTSYNC, exposed as /dev/ntsync) that implements Windows NT synchronization primitives directly in the Linux kernel — mainlined in kernel 6.14 (also available as a patch on 6.12/6.13). Because the NT sync semantics live in the kernel rather than being emulated with eventfds/futexes, it is more accurate and lower-overhead than esync/fsync, improving CPU-bound performance, frame pacing, and compatibility. PROTON_NO_NTSYNC=1 forces the fsync fallback for the rare game that misbehaves with it. _(risk: low)_
- `PROTON_DLSS_UPGRADE=1` ·_game-specific_ — HOW: Auto-downloads and swaps in newer NVIDIA DLSS runtime DLLs (nvngx_dlss.dll for super-resolution, nvngx_dlssg.dll for frame generation, nvngx_dlssd.dll for ray reconstruction) in place of the ones a game shipped. =1 pulls the latest; a version string like "310.2" pins a specific DLSS branch. Newer DLSS runtimes typically give sharper, less-ghosty upscaling than the version baked into the game. _(risk: low; reports using it log more performance faults (Δ +0.22))_
- `game-performance` ·_game-specific_ — HOW: CachyOS's own performance wrapper (ships in CachyOS-Settings as /usr/bin/game-performance). Prepended before %command%, it asks power-profiles-daemon to switch to the 'performance' power profile for the duration of the game — raising platform power limits and putting the CPU governor in performance mode — then restoring the previous profile on exit. It is a SEPARATE tool from Feral GameMode (gamemoderun): CachyOS documentation explicitly recommends using game-performance INSTEAD of GameMode on CachyOS, and the two should not be stacked. _(risk: low)_
- `-useallavailablecores` ·_game-specific_ — HOW: An Unreal Engine argument telling the engine to spread work across all CPU cores instead of defaulting to fewer. On CPU-bound UE titles it can reduce single-core bottleneck stutter and lift average FPS. _(risk: low)_
- `PROTON_NVIDIA_LIBS_NO_32BIT=1` ·_game-specific_ — WHY: A proton-cachyos option that restricts the bundled NVIDIA userspace libraries (nvcuda, nvenc, nvml, nvoptix) to their 64-bit builds only, skipping the 32-bit versions. Used together with PROTON_NVIDIA_LIBS=1. It exists because, on RTX 4000/5000-series GPUs, having the 32-bit NVIDIA libraries active for 32-bit games has caused crashes and degraded performance; dropping them to 64-bit-only resolves that. (Workaround for a specific regression: the 32-bit NVIDIA library path misbehaves with 32-bit titles on newer RTX (Ada/Blackwell) cards. It is NOT a generic speed knob — set it to dodge that crash/perf bug. NOTE OF ORIGIN: this is a proton-cachyos (and similar custom-build) variable, NOT documented in stock Valve Proton; scope advice to CachyOS/custom Proton. Directly relevant on this RTX 4090 + CachyOS box.) _(risk: low; reports using it log more performance faults (Δ +0.48))_
- `PROTON_ENABLE_NVAPI=1` ·_standard on NVIDIA_ — WHY: Turns on Proton's NVAPI bridge (dxvk-nvapi), exposing NVIDIA's proprietary GPU API to Windows games. This is what lets DLSS, NVIDIA Reflex, and (on supported titles) DLSS Frame Generation be offered inside the game. Typically paired with DXVK's dxgi.nvapiHack=False so the game sees a genuine NVIDIA adapter. NOTE on DXVK_ENABLE_NVAPI: that is a REAL but separate variable used by dxvk-nvapi when running DXVK OUTSIDE Proton (it forces NVAPI init regardless of reported PCI vendor ID); under Proton the controlling variable is PROTON_ENABLE_NVAPI, so DXVK_ENABLE_NVAPI is folded here as an alias and should not be the primary recommendation for Steam/Proton launchOptions. (how: unlocks DLSS upscaling and Reflex, which visibly improve image quality and latency. why-ish: some games only expose those options when NVAPI is present, so it can also be a 'make the menu option appear' gate.) _(risk: low)_

**Optional / advanced — weigh the trade before adding**
- `-dx11` — WHY: Forces a game that supports multiple renderers to use its Direct3D 11 path. Under Proton this routes through DXVK, which is the most mature and stable translation layer — often more reliable than a game's DX12 path on Linux. (why: frequently chosen because the game's DX12/Vulkan path is buggy under Proton and DX11/DXVK 'just works'. how: can also be steadier frame times.) _(risk: medium; associated with WORSE outcomes (verdict Δ -0.14) — often a troubleshooting attempt, not a fix)_
- `mangohud` / `MANGOHUD=1` — HOW: A Vulkan/OpenGL overlay that draws FPS, frame-time graph, CPU/GPU load, temperatures and clocks on top of the running game, and can log those metrics for benchmarking. It measures; it does not change game behavior. _(risk: low)_  — elective (no effect on how the game runs).
- `gamescope` — WHY: A micro-compositor that runs the game inside its own nested Wayland session, then composites the result into your desktop. Common args: -W/-H set the game's internal render resolution, -w/-h the output window size, -f fullscreen, -r FPS cap, -F fsr or --fsr-upscaling to upscale a low internal resolution with AMD FSR 1.0, and -e for Steam integration. It decouples render resolution from display resolution and gives a stable fullscreen surface. (why: also a workaround layer — it fixes broken alt-tab/fullscreen behavior, forces a resolution a game refuses to honor, and enables HDR or integer scaling without native game support. The FSR-upscaling use is the 'how' (perf via lower internal res).) _(risk: medium)_
- `PROTON_ENABLE_NTSYNC=1` — HOW: Tells Proton to use NTSYNC for Wine thread synchronization instead of esync/fsync. NTSYNC is an in-kernel driver (CONFIG_NTSYNC, exposed as /dev/ntsync) that implements Windows NT synchronization primitives directly in the Linux kernel — mainlined in kernel 6.14 (also available as a patch on 6.12/6.13). Because the NT sync semantics live in the kernel rather than being emulated with eventfds/futexes, it is more accurate and lower-overhead than esync/fsync, improving CPU-bound performance, frame pacing, and compatibility. PROTON_NO_NTSYNC=1 forces the fsync fallback for the rare game that misbehaves with it. _(risk: low)_  — thin evidence (n=3) — surfaced but not strongly attested.
- `VKD3D_DISABLE_EXTENSIONS=VK_KHR_present_wait` — WHY: Tells VKD3D-Proton not to use specific Vulkan extensions, comma-separated. The headline use is VKD3D_DISABLE_EXTENSIONS=VK_NV_low_latency2, which turns off the NVIDIA low-latency/Reflex extension path. (Canonical 'why' workaround: on NVIDIA, the VK_NV_low_latency2 path (used by Reflex and DLSS Frame Generation) has triggered crashes, non-monotonic-frame-ID stutter, and hitching in some D3D12 titles (e.g. the ARC Raiders frame-gen stutter report, vkd3d-proton issue #2794). Disabling the extension stops VKD3D from exercising the buggy path. It exists to dodge a known driver/extension regression, not to gain performance.) _(risk: medium)_  — thin evidence (n=4) — surfaced but not strongly attested.
- `DXVK_ENABLE_NVAPI=1` — WHY: Turns on Proton's NVAPI bridge (dxvk-nvapi), exposing NVIDIA's proprietary GPU API to Windows games. This is what lets DLSS, NVIDIA Reflex, and (on supported titles) DLSS Frame Generation be offered inside the game. Typically paired with DXVK's dxgi.nvapiHack=False so the game sees a genuine NVIDIA adapter. NOTE on DXVK_ENABLE_NVAPI: that is a REAL but separate variable used by dxvk-nvapi when running DXVK OUTSIDE Proton (it forces NVAPI init regardless of reported PCI vendor ID); under Proton the controlling variable is PROTON_ENABLE_NVAPI, so DXVK_ENABLE_NVAPI is folded here as an alias and should not be the primary recommendation for Steam/Proton launchOptions. (how: unlocks DLSS upscaling and Reflex, which visibly improve image quality and latency. why-ish: some games only expose those options when NVAPI is present, so it can also be a 'make the menu option appear' gate.) _(risk: low)_  — thin evidence (n=4) — surfaced but not strongly attested.
- `ENABLE_HDR_WSI=1` / `PROTON_ENABLE_HDR=1` / `DXVK_HDR=1` — WHY: Enables High Dynamic Range output for a game under Proton. In practice this is a small cluster set together: PROTON_ENABLE_HDR=1 (Proton side), DXVK_HDR=1 (the DXVK/D3D layer emits an HDR swapchain), and on some setups ENABLE_HDR_WSI=1 (routes HDR through the vk-hdr-layer). Usually combined with PROTON_ENABLE_WAYLAND=1. The result is wider color/brightness on an HDR display. (how: visibly better image on HDR hardware. why: it also has hard external requirements — an HDR-capable display, a Wayland compositor with the color-management protocol (KDE Plasma 6 qualifies), and on NVIDIA historically the vk-hdr-layer + ENABLE_HDR_WSI for drivers BEFORE 595.58.03. This box runs driver 595.71.05 (newer than that cutoff) on KDE/Wayland, so the extra vk-hdr-layer/ENABLE_HDR_WSI step is likely unnecessary and PROTON_ENABLE_HDR + DXVK_HDR should suffice. Do NOT set ENABLE_HDR_WSI together with gamescope HDR (they conflict).) _(risk: low)_  — conditional — only worthwhile with an HDR-capable display and HDR enabled in your compositor (KDE Plasma 6 qualifies); not applied automatically.
- `MANGOHUD=0` — HOW: A Vulkan/OpenGL overlay that draws FPS, frame-time graph, CPU/GPU load, temperatures and clocks on top of the running game, and can log those metrics for benchmarking. It measures; it does not change game behavior. _(risk: medium; associated with WORSE outcomes (verdict Δ -0.59) — often a troubleshooting attempt, not a fix)_  — thin evidence (n=3) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `-dx12` — WHY: Forces the Direct3D 12 renderer, which under Proton goes through VKD3D-Proton. Picks up DX12-only features (ray tracing, better multithreading) but exercises a less mature layer than DXVK, so it can stutter or crash where DX11 wouldn't. (how: unlocks DX12 features/perf. why: sometimes required because a game's DX11 path is broken or absent.) _(risk: medium; reports using it log more performance faults (Δ +0.26))_
- `PROTON_XESS_UPGRADE=1` — HOW: Downloads and injects newer Intel XeSS / XeSS 2 upscaler runtime DLLs (libxess.dll) in place of the version a game shipped, keeping the upscaler current. The sibling of PROTON_DLSS_UPGRADE (DLSS) and PROTON_FSR4_UPGRADE (FSR). A GE-Proton / proton-cachyos feature. _(risk: low)_  — thin evidence (n=2) — surfaced but not strongly attested.
- `__GL_THREADED_OPTIMIZATIONS=1` — HOW: NVIDIA's OpenGL threaded-optimization toggle. =1 forces the driver to offload OpenGL call processing onto a separate CPU thread, which can help CPU-bound OpenGL workloads. The driver enables this automatically under some conditions and self-disables when it isn't helping; the variable forces it on (or off with 0). _(risk: low)_  — thin evidence (n=3) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `VKD3D_CONFIG=dxr,dxr12` / `VKD3D_CONFIG=upload_hvv` — WHY: The master tuning variable for VKD3D-Proton (the Direct3D 12 -> Vulkan layer). A comma/semicolon list of tokens. Key ones: 'dxr' force-enables DirectX Raytracing (including DXR 1.1) even where VKD3D considers it unsafe; 'dxr12' enables experimental DXR 1.2; 'nodxr' disables ray tracing; 'no_upload_hvv' stops using host-visible VRAM for the upload heap (fixes VRAM-pressure stutter/regressions on some configs); 'force_static_cbv' is an NVIDIA-only speed hack; 'single_queue' disables async compute/transfer queues to work around driver bugs. (why: most tokens are workarounds for a specific driver/game bug (no_upload_hvv, single_queue, skip_application_workarounds) — the user wouldn't set them without a known issue. 'dxr'/'dxr12' are the 'how' (unlock ray-traced visuals). Per-token semantics differ; the recommender should map the exact token.) _(risk: medium; reports using it log more performance faults (Δ +0.88))_  — thin evidence (n=2) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `PROTON_NO_STEAMINPUT=1` — WHY: Disables Steam Input handling for the game. Steam Input remaps controllers through Steam's own layer; some games do their own controller handling and conflict with it, producing doubled/ghost inputs, an unrecognized pad, or broken glyphs. Turning it off lets the game talk to the controller directly. (Workaround for Steam-Input-vs-native-controller conflicts. Also note: PROTON_ENABLE_WAYLAND currently breaks Steam Input anyway, so the two interact on this Wayland box.) _(risk: low)_  — thin evidence (n=2) — surfaced but not strongly attested.
- `PROTON_NO_WM_DECORATION=1` — WHY: Tells Proton not to request window-manager decorations (title bar/borders) for the game window. Fixes borderless-fullscreen problems and a class of input bugs where mouse clicks pass through to the desktop behind the game. (Workaround for windowing/input quirks (borderless-fullscreen misbehavior, click-through) — particularly under tiling/Wayland compositors. Relevant on this KDE/Wayland box.) _(risk: low)_  — thin evidence (n=2) — surfaced but not strongly attested.
- `PROTON_ENABLE_NVAPI=0` — WHY: Turns on Proton's NVAPI bridge (dxvk-nvapi), exposing NVIDIA's proprietary GPU API to Windows games. This is what lets DLSS, NVIDIA Reflex, and (on supported titles) DLSS Frame Generation be offered inside the game. Typically paired with DXVK's dxgi.nvapiHack=False so the game sees a genuine NVIDIA adapter. NOTE on DXVK_ENABLE_NVAPI: that is a REAL but separate variable used by dxvk-nvapi when running DXVK OUTSIDE Proton (it forces NVAPI init regardless of reported PCI vendor ID); under Proton the controlling variable is PROTON_ENABLE_NVAPI, so DXVK_ENABLE_NVAPI is folded here as an alias and should not be the primary recommendation for Steam/Proton launchOptions. (how: unlocks DLSS upscaling and Reflex, which visibly improve image quality and latency. why-ish: some games only expose those options when NVAPI is present, so it can also be a 'make the menu option appear' gate.) _(risk: medium; associated with WORSE outcomes (verdict Δ -0.43) — often a troubleshooting attempt, not a fix; reports using it log more performance faults (Δ +0.38))_  — thin evidence (n=2) — surfaced but not strongly attested.
- `OBS_VKCAPTURE=1` — WHY: Wrapper from the obs-vkcapture project. Prepended before %command%, it injects a Vulkan/OpenGL capture layer so OBS Studio can grab the game's framebuffer directly (low-overhead game capture) instead of capturing the whole screen. (Exists to make OBS game-capture work under Proton; nothing to do with the game's own quality — present only when the user records/streams.) _(risk: low)_  — thin evidence (n=2) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `DXVK_CONFIG=<custom>` — WHY: Inline or file-based DXVK tuning. DXVK_CONFIG takes semicolon-separated key=value pairs (e.g. 'dxgi.nvapiHack = False; dxgi.syncInterval = 0'); DXVK_CONFIG_FILE points at a dxvk.conf. Notable keys: dxgi.nvapiHack=False (let games see a real NVIDIA GPU so DLSS/NVAPI works), dxgi.syncInterval (vsync), dxgi.hideAmdGpu / dxgi.hideNvidiaGpu (device reporting). (why: specific keys are workarounds — dxgi.nvapiHack=False is required alongside PROTON_ENABLE_NVAPI for DLSS to be offered; others paper over device-detection quirks.) _(risk: medium; reports using it log more performance faults (Δ +0.38))_  — thin evidence (n=2) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `PROTON_HIDE_NVIDIA_GPU=0` — WHY: Makes Proton report NVIDIA GPUs as AMD. Some games branch on Windows-only NVIDIA driver behavior that doesn't exist under Proton and break when they detect an NVIDIA card; spoofing AMD sidesteps that code path. Distinct from DXVK's dxgi.nvapiHack, which only changes what Direct3D reports. (Workaround for games that depend on Windows-only NVIDIA functionality and misbehave on the Linux NVIDIA driver.) _(risk: high; associated with WORSE outcomes (verdict Δ -0.18) — often a troubleshooting attempt, not a fix)_  — higher parity risk — apply only if you specifically need it. thin evidence (n=4) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `prime-run` — WHY: A tiny wrapper script from nvidia-prime that exports the PRIME render-offload variables (__NV_PRIME_RENDER_OFFLOAD=1, __GLX_VENDOR_LIBRARY_NAME=nvidia, __VK_LAYER_NV_optimus=NVIDIA_only) so the wrapped program renders on the discrete NVIDIA GPU instead of the integrated one. (External constraint: on a muxless hybrid laptop the display is wired to the iGPU, so by default a game can run on the weak Intel GPU. prime-run exists to route rendering to the dGPU — a user wouldn't know why it's prepended without knowing the laptop is hybrid. Directly relevant to this Intel+RTX4090 machine.) _(risk: low; reports using it log more performance faults (Δ +0.38))_  — thin evidence (n=2) — surfaced but not strongly attested.
- `__NV_PRIME_RENDER_OFFLOAD=1` — WHY: The underlying NVIDIA variable that prime-run sets. =1 loads the VK_LAYER_NV_optimus Vulkan layer so the NVIDIA dGPU is enumerated first; pairing with __GLX_VENDOR_LIBRARY_NAME=nvidia routes GLX, and __VK_LAYER_NV_optimus=NVIDIA_only hides the iGPU from Vulkan entirely. (Same hybrid-GPU offload constraint as prime-run, written out explicitly instead of via the wrapper.) _(risk: low; reports using it log more performance faults (Δ +0.38))_  — thin evidence (n=2) — surfaced but not strongly attested.
- `WINE_FULLSCREEN_FSR=1` — HOW: Proton's own built-in AMD FSR 1.0 spatial upscaler (the 'FShack'): when a game renders at a lower-than-native resolution, Proton upscales the final image to the output resolution and applies sharpening. WINE_FULLSCREEN_FSR_STRENGTH sets the sharpening amount (0-5, 0 = sharpest, default 2). This is a vendor-agnostic spatial upscale applied at the Wine/Proton layer — distinct from gamescope's FSR and from in-engine FSR2/3/4. _(risk: medium; reports using it log more performance faults (Δ +0.22))_  — thin evidence (n=3) — surfaced but not strongly attested.
- `PROTON_NO_FSYNC=1` — WHY: Disables fsync, the futex-based synchronization that's even lower-overhead than esync on supported kernels. Enabled by default when the kernel supports it; this reverts to esync (or no accelerated sync). (Workaround/diagnostic: setting it isolates whether a crash or perf regression is fsync-related. A few titles need it off.) _(risk: high; associated with WORSE outcomes (verdict Δ -0.13) — often a troubleshooting attempt, not a fix)_  — higher parity risk — apply only if you specifically need it. elective (no effect on how the game runs).
- `PROTON_NO_ESYNC=1` — WHY: Disables esync, the eventfd-based in-process synchronization that lowers Wine's threading overhead. Esync is on by default and generally helps CPU-bound games; this turns it off. (Workaround: a few games crash or misbehave with esync's many file descriptors / sync semantics; disabling it restores stability. Note WINEESYNC can override this.) _(risk: high; associated with WORSE outcomes (verdict Δ -0.13) — often a troubleshooting attempt, not a fix)_  — higher parity risk — apply only if you specifically need it. elective (no effect on how the game runs).
- `PROTON_USE_WINED3D=1` — WHY: Forces Proton to translate Direct3D 9/10/11 through the old OpenGL-based WineD3D path instead of the Vulkan-based DXVK. Almost never desirable for performance — DXVK is faster and more compatible — it exists for the rare game DXVK can't render and for systems without a usable Vulkan driver. (Fallback for DXVK incompatibility or missing Vulkan support; not a tuning choice.) _(risk: high; associated with WORSE outcomes (verdict Δ -0.26) — often a troubleshooting attempt, not a fix)_  — higher parity risk — apply only if you specifically need it. elective (no effect on how the game runs).
- `DXVK_FRAME_RATE=<num>` — HOW: Caps the frame rate of D3D9/10/11 titles running through DXVK. 0 means uncapped. The per-config equivalents dxgi.maxFrameRate / d3d9.maxFrameRate do the same from dxvk.conf. _(risk: low)_  — thin evidence (n=3) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `WINEDLLOVERRIDES=<custom>` — WHY: Tells Wine/Proton how to load specific DLLs: 'n' native (the file shipped next to the game), 'b' built-in (Wine's own), 'n,b' native-then-builtin, or '' to disable. Most commonly used for modding — dinput8=n,b, winmm=n,b, version=n,b let ASI loaders / mod frameworks that hook those DLLs run under Proton — and occasionally to force or disable a renderer DLL (e.g. d3d11/dxgi). (Modding/loader constraint: many mod loaders work by shipping a proxy DLL (dinput8/winmm/version) that Windows loads automatically but Wine ignores unless told to prefer native. The override exists to make that loader load.) _(risk: medium)_
- `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1` — WHY: NVIDIA driver shader-cache controls. __GL_SHADER_DISK_CACHE=1 enables the on-disk cache; __GL_SHADER_DISK_CACHE_SIZE sets its size in bytes (e.g. 10737418240 for 10 GB); __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 stops the driver pruning it. Raising/uncapping the size keeps compiled shaders around so later sessions don't re-stutter — important for shader-heavy modern titles whose cache the driver would otherwise evict. (Workaround for the NVIDIA driver pruning the shader cache too aggressively, which reintroduces compile stutter ('cold cache') in big games. Enlarging/skip-cleanup stops the eviction.) _(risk: medium; associated with WORSE outcomes (verdict Δ -0.43) — often a troubleshooting attempt, not a fix)_  — thin evidence (n=2) — surfaced but not strongly attested.
- `PROTON_LOG=<custom>` — WHY: Dumps a Proton/Wine debug log to $PROTON_LOG_DIR/steam-$APPID.log (home directory by default). Set to a string to append WINEDEBUG channels. Purely for diagnosing why a game fails to launch or crashes. (Diagnostic only — produces logs; never improves the game.) _(risk: medium; associated with WORSE outcomes (verdict Δ -0.18) — often a troubleshooting attempt, not a fix)_  — thin evidence (n=4) — surfaced but not strongly attested. elective (no effect on how the game runs).
- `gamemoderun` — HOW: Feral Interactive's GameMode launcher. Prepended before %command%, it asks the gamemoded daemon to apply temporary host tweaks while the game runs: switch the CPU governor to performance, raise process priority/niceness and I/O priority, and (optionally) pin the GPU to its high-performance power profile, reverting everything on exit. _(risk: low)_  — alternative to game-performance — CachyOS recommends game-performance; don't stack them.

**Data-only signals (no annotation yet; top 8 of 24)**
_Parameters other players tie to this game that the knowledge base does not yet describe — shown for completeness, meaning unverified, ranked by relevance._
- `WAYLANDDRV_PRIMARY_MONITOR=DP-1` — 7 reports, runs-rate 100%, risk medium
- `PROTON_NVIDIA_LIBS=1` — 6 reports, runs-rate 100%, risk medium
- `PULSE_LATENCY_MSEC=<num>` — 11 reports, runs-rate 91%, risk medium
- `PROTON_LOCAL_SHADER_CACHE=1` — 5 reports, runs-rate 80%, risk high
- `SteamDeck=1` — 13 reports, runs-rate 92%, risk medium
- `SDL_VIDEO_DRIVER=x11` — 3 reports, runs-rate 100%, risk medium
- `__GL__THREADED_OPTIMIZATIONS=1` — 2 reports, runs-rate 100%, risk medium
- `PROTON_NVIDIA_NVOPTIX=1` — 2 reports, runs-rate 100%, risk medium
- …and 16 more (see the full catalog below).

**Assembled launch options (Recommended tier):**
```
PROTON_DLSS_UPGRADE=1 PROTON_ENABLE_NVAPI=1 PROTON_ENABLE_WAYLAND=1 PROTON_NVIDIA_LIBS_NO_32BIT=1 PROTON_USE_NTSYNC=1 game-performance %command% -useallavailablecores
```

**⚠️ Do NOT use for this title:**
- `shell-hack:generic` — BYPASS on an online title: risks an ACCOUNT BAN and enables nothing — this game's anti-cheat is accepted on Linux, so never bypass it.

## Validation against your known-good config
- **Runtime `proton-cachyos-slr`** → matched KB record `proton_variant_cachyos` (a GE-class build) — consistent with the Foundation recommendation. ✓

| Your parameter | In game data? | runs-rate | tier the skill assigns |
|---|---|---|---|
| `PROTON_DLSS_UPGRADE=1` | yes (24r) | 96% | recommended |
| `PROTON_ENABLE_NVAPI=1` | yes (20r) | 95% | recommended |
| `PROTON_NVIDIA_LIBS_NO_32BIT=1` | yes (5r) | 100% | recommended |
| `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1` | yes (2r) | 50% | optional |
| `game-performance` | yes (33r) | 94% | recommended |
| `mangohud` | yes (58r) | 93% | optional |

**Evidence-backed additions your current config is missing:**
- `PROTON_ENABLE_WAYLAND=1` — runs-rate 95% (119 reports); WHY: Makes Proton render through a native Wayland surface instead of going through XWayland. Can lower latency, improve frame pacing, and enable HDR without gamescope — but it is experimental and currently breaks the Steam overlay and Steam Input on many titles. (how: better latency/pacing and HDR on a Wayland session. why: also needed by some setups to avoid XWayland quirks. Directly relevant on this Wayland/KDE box, with the overlay/input caveat.)
- `PROTON_USE_NTSYNC=1` — runs-rate 98% (53 reports); HOW: Tells Proton to use NTSYNC for Wine thread synchronization instead of esync/fsync. NTSYNC is an in-kernel driver (CONFIG_NTSYNC, exposed as /dev/ntsync) that implements Windows NT synchronization primitives directly in the Linux kernel — mainlined in kernel 6.14 (also available as a patch on 6.12/6.13). Because the NT sync semantics live in the kernel rather than being emulated with eventfds/futexes, it is more accurate and lower-overhead than esync/fsync, improving CPU-bound performance, frame pacing, and compatibility. PROTON_NO_NTSYNC=1 forces the fsync fallback for the rare game that misbehaves with it.
- `-useallavailablecores` — runs-rate 95% (19 reports); HOW: An Unreal Engine argument telling the engine to spread work across all CPU cores instead of defaulting to fewer. On CPU-bound UE titles it can reduce single-core bottleneck stutter and lift average FPS.

## Full parameter catalog (relevance-ranked)
_Every parameter the data ties to this game, most game-specific first. Hardware/stale tags show whether it applies to you._

| # | Parameter | How/Why | Category | Axes | Risk | Applies | Evidence |
|--:|---|---|---|---|---|---|---|
| 1 | `PROTON_ENABLE_WAYLAND=1` | WHY | display-wayland | perf+,nati~ | low | ✓ | 119r·rec39%·×7.8·95% |
| 2 | `Proton build = GE-Proton (recent builds)` | WHY | proton-runtime-selection | nati+,visu+ | low | ✓ | 221r·rec34%·×14.5·95% |
| 3 | `PROTON_USE_NTSYNC=1` | HOW | wine-sync | perf+,nati+ | low | ✓ | 53r·rec17%·×7.4·98% |
| 4 | `PROTON_FSR4_UPGRADE=1` | HOW | upscaling | visu+,perf~ | low | ✗ amd-only | 33r·rec11%·×7.8·91% |
| 5 | `PROTON_USE_EAC_LINUX=1` | WHY | anti-cheat-or-drm | nati+ | low | ✓ | 28r·rec10%·×10.0·93% |
| 6 | `PROTON_DLSS_UPGRADE=1` | HOW | upscaling | visu+ | low | ✓ | 24r·rec9%·×8.3·96% |
| 7 | `variant:notListed` | — | unannotated | — | medium | ✓ | 145r·rec15%·×2.8·92% |
| 8 | `game-performance` | HOW | cpu-scheduling | perf+ | low | ✓ | 33r·rec9%·×3.1·94% |
| 9 | `variant:experimental` | WHY | proton-runtime-selection | nati+ | low | ✓ | 232r·rec23%·×1.6·85% |
| 10 | `-dx11` | WHY | dxvk-rendering | nati+,perf~ | medium | ✓ | 28r·rec5%·×3.9·79% |
| 11 | `variant:ge` | WHY | proton-runtime-selection | nati+,visu+ | low | ✓ | 226r·rec25%·×1.4·96% |
| 12 | `-useallavailablecores` | HOW | cpu-scheduling | perf+ | low | ✓ | 19r·rec6%·×3.1·95% |
| 13 | `ENABLE_LAYER_MESA_ANTI_LAG=1` | HOW | amd-mesa | perf+ | low | ✗ mesa-only | 10r·rec4%·×6.0·100% |
| 14 | `notes_version=Proton-hotfix` | WHY | proton-runtime-selection | nati+ | medium | ✓ | 30r·rec2%·×6.5·77% |
| 15 | `PROTON_FSR4_RDNA3_UPGRADE=1` | HOW | upscaling | visu+,perf~ | medium | ✗ amd-only | 9r·rec3%·×6.6·100% |
| 16 | `mangohud` | HOW | monitoring-overlay | perf~ | low | ✓ | 58r·rec17%·×1.2·93% |
| 17 | `gamescope` | WHY | upscaling | perf+,visu~,nati+ | medium | ✓ | 26r·rec9%·×1.6·85% |
| 18 | `WAYLANDDRV_PRIMARY_MONITOR=DP-1` | — | unannotated | — | medium | ✓ | 7r·rec2%·×6.8·100% |
| 19 | `notes_version=Proton-experimental` | WHY | proton-runtime-selection | nati+ | medium | ✓ | 39r·rec5%·×2.1·77% |
| 20 | `notes_version=Proton-10.0` | HOW | proton-runtime-selection | nati+ | low | ✓ | 15r·rec2%·×5.1·93% |
| 21 | `PROTON_NVIDIA_LIBS=1` | — | unannotated | — | medium | ✓ | 6r·rec2%·×5.1·100% |
| 22 | `PULSE_LATENCY_MSEC=<num>` | — | unannotated | — | medium | ✓ | 11r·rec4%·×2.3·91% |
| 23 | `PROTON_NVIDIA_LIBS_NO_32BIT=1` | WHY | nvidia-feature | perf~,nati+ | low | ✓ | 5r·rec2%·×4.8·100% |
| 24 | `PROTON_LOCAL_SHADER_CACHE=1` | — | unannotated | — | high | ✓ | 5r·rec2%·×4.1·80% |
| 25 | `shell-hack:generic` | WHY | anti-cheat-or-drm | nati+ | high | ✓ | 14r·rec4%·×1.5·100% |
| 26 | `PROTON_ENABLE_NTSYNC=1` | HOW | wine-sync | perf+,nati+ | low | ✓ | 3r·rec1%·×3.4·100% |
| 27 | `VKD3D_DISABLE_EXTENSIONS=VK_KHR_present_wait` | WHY | vkd3d-d3d12 | nati+,perf~ | medium | ✓ | 4r·rec0%·×4.1·100% |
| 28 | `SteamDeck=1` | — | unannotated | — | medium | ✓ | 13r·rec3%·×1.5·92% |
| 29 | `SDL_VIDEO_DRIVER=x11` | — | unannotated | — | medium | ✓ | 3r·rec0%·×3.6·100% |
| 30 | `DXVK_ENABLE_NVAPI=1` | WHY | nvidia-feature | visu+,perf+ | low | ✓ | 4r·rec2%·×2.3·100% |
| 31 | `ENABLE_HDR_WSI=1` | WHY | display-wayland | visu+ | low | ✓ | 6r·rec1%·×2.3·100% |
| 32 | `PROTON_ENABLE_HDR=1` | WHY | display-wayland | visu+ | low | ✓ | 8r·rec3%·×1.6·100% |
| 33 | `DXVK_STATE_CACHE=1` | HOW | shader-cache-stutter | perf+ | medium | stale | 3r·rec1%·×2.8·67% |
| 34 | `MANGOHUD=0` | HOW | monitoring-overlay | perf~ | medium | ✓ | 3r·rec1%·×2.9·33% |
| 35 | `-dx12` | WHY | vkd3d-d3d12 | visu+,perf~ | medium | ✓ | 8r·rec3%·×1.4·100% |
| 36 | `PROTON_XESS_UPGRADE=1` | HOW | upscaling | visu+ | low | ✓ | 2r·rec1%·×2.8·100% |
| 37 | `DXVK_HDR=1` | WHY | display-wayland | visu+ | low | ✓ | 5r·rec1%·×2.0·100% |
| 38 | `__GL__THREADED_OPTIMIZATIONS=1` | — | unannotated | — | medium | ✓ | 2r·rec1%·×2.9·100% |
| 39 | `__GL_THREADED_OPTIMIZATIONS=1` | HOW | nvidia-feature | perf~ | low | ✓ | 3r·rec1%·×2.0·100% |
| 40 | `PROTON_NVIDIA_NVOPTIX=1` | — | unannotated | — | medium | ✓ | 2r·rec1%·×2.9·100% |
| 41 | `VKD3D_CONFIG=dxr,dxr12` | WHY | vkd3d-d3d12 | visu~,perf~,nati~ | medium | ✓ | 2r·rec1%·×2.9·100% |
| 42 | `PROTON_FSR4_UPGRADE=4.0.3` | HOW | upscaling | visu+,perf~ | low | ✗ amd-only | 2r·rec1%·×3.0·100% |
| 43 | `PROTON_NO_STEAMINPUT=1` | WHY | launcher-or-ux | nati+ | low | ✓ | 2r·rec1%·×2.6·100% |
| 44 | `MANGOHUD=1` | HOW | monitoring-overlay | perf~ | low | ✓ | 13r·rec5%·×1.2·100% |
| 45 | `SDL_VIDEODRIVER=wayland,windows,x11` | — | unannotated | — | medium | ✓ | 2r·rec1%·×2.6·100% |
| 46 | `SDL_VIDEODRIVER=windows` | — | unannotated | — | high | ✓ | 3r·rec0%·×2.6·67% |
| 47 | `-vulcan` | — | unannotated | — | medium | ✓ | 2r·rec0%·×2.9·100% |
| 48 | `VKD3D_CONFIG=upload_hvv` | WHY | vkd3d-d3d12 | visu~,perf~,nati~ | medium | ✓ | 2r·rec1%·×2.8·100% |
| 49 | `DXVK_FORCE_SINGLETHREADED=1` | — | unannotated | — | medium | ✓ | 2r·rec1%·×3.0·100% |
| 50 | `LSFG_PROCESS=arc` | — | unannotated | — | medium | ✓ | 2r·rec1%·×2.9·100% |
| 51 | `PROTON_NO_WM_DECORATION=1` | WHY | display-wayland | nati+ | low | ✓ | 2r·rec1%·×2.1·100% |
| 52 | `LD_PRELOAD` | — | unannotated | — | medium | ✓ | 10r·rec2%·×1.2·90% |
| 53 | `PROTON_LOCAL_SHADER_CACHE=0` | — | unannotated | — | medium | ✓ | 2r·rec1%·×3.0·100% |
| 54 | `PROTON_PREFER_SDL=1` | — | unannotated | — | high | ✓ | 3r·rec0%·×2.9·33% |
| 55 | `RADV_PERFTEST=transfer_queue` | HOW | amd-mesa | perf+ | low | stale | 2r·rec1%·×2.9·100% |
| 56 | `MESA_VK_WSI_PRESENT_MODE=immediate` | WHY | display-wayland | perf~ | low | ✗ mesa-only | 2r·rec1%·×2.5·100% |
| 57 | `PROTON_FORCE_NVAPI=1` | — | unannotated | — | medium | ✓ | 2r·rec1%·×2.4·100% |
| 58 | `notes_version=Proton-11.0` | HOW | proton-runtime-selection | nati+ | low | ✓ | 2r·rec0%·×2.6·100% |
| 59 | `PROTON_ENABLE_NVAPI=0` | WHY | nvidia-feature | visu+,perf+ | medium | ✓ | 2r·rec1%·×1.9·50% |
| 60 | `-` | — | unannotated | — | high | ✓ | 2r·rec0%·×2.4·50% |
| 61 | `SDL_VIDEODRIVER=wayland` | — | unannotated | — | medium | ✓ | 2r·rec1%·×1.8·100% |
| 62 | `OBS_VKCAPTURE=1` | WHY | monitoring-overlay | perf~ | low | ✓ | 2r·rec0%·×1.7·100% |
| 63 | `SDL_VIDEO_DRIVER=wayland` | — | unannotated | — | medium | ✓ | 2r·rec0%·×2.0·100% |
| 64 | `PROTON_ENABLE_NVAPI=1` | WHY | nvidia-feature | visu+,perf+ | low | ✓ | 20r·rec6%·×1.0·95% |
| 65 | `PROTON_EAC_RUNTIME=1` | WHY | anti-cheat-or-drm | nati+ | medium | ✓ | 2r·rec0%·×2.1·0% |
| 66 | `PROTON_ENABLE_NGX_UPDATER=1` | — | unannotated | — | high | ✓ | 2r·rec1%·×1.3·50% |
| 67 | `RADV_PERFTEST=gpl` | HOW | amd-mesa | perf+ | low | stale | 3r·rec1%·×1.1·100% |
| 68 | `DXVK_CONFIG=<custom>` | WHY | dxvk-rendering | visu~,nati~ | medium | ✓ | 2r·rec1%·×1.1·100% |
| 69 | `-high` | — | unannotated | — | medium | ✓ | 4r·rec2%·×1.0·100% |
| 70 | `notes_version=Proton-9.0` | HOW | proton-runtime-selection | nati+ | medium | ✓ | 5r·rec0%·×1.1·0% |
| 71 | `MANGOHUD_CONFIG=<custom>` | — | unannotated | — | medium | ✓ | 2r·rec1%·×0.6·100% |
| 72 | `PROTON_HIDE_NVIDIA_GPU=0` | WHY | nvidia-feature | nati~ | high | ✓ | 4r·rec2%·×0.6·75% |
| 73 | `prime-run` | WHY | gpu-offload-hybrid | perf+,nati+ | low | ✓ | 2r·rec1%·×0.7·100% |
| 74 | `__NV_PRIME_RENDER_OFFLOAD=1` | WHY | gpu-offload-hybrid | perf+,nati+ | low | ✓ | 2r·rec1%·×0.7·100% |
| 75 | `__GLX_VENDOR_LIBRARY_NAME=nvidia` | — | unannotated | — | medium | ✓ | 2r·rec1%·×0.7·100% |
| 76 | `WINE_FULLSCREEN_FSR=1` | HOW | upscaling | perf+,visu~ | medium | ✓ | 3r·rec1%·×0.8·100% |
| 77 | `PROTON_NO_FSYNC=1` | WHY | wine-sync | perf-,nati~ | high | ✓ | 5r·rec2%·×0.8·80% |
| 78 | `PROTON_NO_ESYNC=1` | WHY | wine-sync | perf-,nati~ | high | ✓ | 5r·rec2%·×0.5·80% |
| 79 | `DXVK_ASYNC=1` | HOW | shader-cache-stutter | perf+,visu- | low | stale | 18r·rec7%·×1.0·94% |
| 80 | `PROTON_USE_WINED3D=1` | WHY | wine-compat-workaround | perf-,nati~ | high | ✓ | 6r·rec2%·×0.4·67% |
| 81 | `DXVK_FRAME_RATE=<num>` | HOW | dxvk-rendering | perf~ | low | ✓ | 3r·rec1%·×0.5·100% |
| 82 | `WINEDLLOVERRIDES=<custom>` | WHY | wine-dll-modding | nati+ | medium | ✓ | 12r·rec2%·×0.6·83% |
| 83 | `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1` | WHY | shader-cache-stutter | perf+ | medium | ✓ | 2r·rec0%·×0.7·50% |
| 84 | `PROTON_LOG=<custom>` | WHY | launcher-or-ux | perf~ | medium | ✓ | 4r·rec1%·×0.8·75% |
| 85 | `gamemoderun` | HOW | cpu-scheduling | perf+ | low | ✓ | 113r·rec33%·×0.9·96% |
| 86 | `variant:official` | HOW | proton-runtime-selection | nati+ | low | ✓ | 317r·rec36%·×0.7·90% |

Legend: Axes = nati(ve-parity)/visu(al-fidelity)/perf, `+` improves/enables · `-` degrades · `~` mixed. Evidence = reports · recent prevalence among tinkered configs · enrichment lift · runs-rate.
