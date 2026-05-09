> **Superseded (2026-04-20):** the substrate question is closed. See
> `findings/jsm_sdl3_verified.md`. Open questions listed below in
> "Unknowns" are resolved in the Phase 1 and Phase 2 findings.

# JSM wrapper substrate — recommendation

**Research date:** 2026-04-19. Source agent briefs in `HANDOFFS/virtual_controller_alternatives.md`.

## TL;DR

**Don't build or wrap anything. Build JoyShockMapper from master (default `SDL=ON`) and plug the pad in.**
JSM 3.6.x replaced the JSL backend with SDL3 as the default, and SDL3's
`SDL_hidapi_8bitdo.c` has first-party support for the 8BitDo Ultimate 2 Wireless
(`VID 0x2DC8 / PID 0x6012`, 34-byte v1.03 report, sensors exposed). If that path
surfaces all 17 buttons and the gyro IMU through JSM's bindings, the ViGEm-DS4
bridge (`tools/jsm_bridge.py`), the DS5 minidriver question, and the JSL fork
proposal all become dead letters. The remaining work is verification, not
substrate selection.

## Comparison table

Criteria: **Cov** = carries all 17 physical inputs? **Gyro** = preserves ±2000 dps?
**Frag** = runtime fragility (fewer moving parts = better). **Maint** = upstream
alive? **Burden** = install/build cost for the user. **Port** = non-Windows reach.

| Path | Cov | Gyro | Frag | Maint | Burden | Port | Verdict |
|------|-----|------|------|-------|--------|------|---------|
| **JSM master, default SDL3** | likely 17 | likely ±2000 | lowest (pad → SDL3 → JSM) | SDL3 + JSM both active | build JSM from master (3.6.2 unreleased) | SDL3 is cross-platform | **recommended — verify first** |
| Fork JSL, add device entry | 17 | ±2000 | low (pad → JSL DLL → JSM-JSL variant) | JSL frozen since 2023-09; JSM-JSL is a legacy build flag | C++17 + CMake; ~400–700 LoC | Windows-centric | Obsolete — JSM's JSL path is opt-in legacy |
| UMDF HID minidriver → virtual DualSense Edge | 17 | ±2000 | medium (pad → Python feeder → driver → JSM) | DIY; no upstream | driver signing is a blocker (EV cert or test-signing mode) | Windows only | Not worth it if SDL3 path works |
| DSX+ (Nefarius VirtualPad, commercial) | unclear for synthetic input | — | high (closed service + UDP LED/haptics only) | paid, closed-source | $4.99 DLC + UAC install | Windows only | Can't inject synthetic buttons/sticks — wrong shape |
| ViGEm DS4 bridge (status quo) | 13 of 17 (drops L4/R4/PL/PR) | ±2000 | medium (Python + archived driver) | ViGEmBus archived 2023-11 | already installed | Windows only | Acceptable fallback only; loses 4 buttons |

## Evidence per path

### 1. JSM master + default SDL3 — recommended

**What changed.** JSM 3.x migrated off JoyShockLibrary to SDL. JSM
`CMakeLists.txt` on master pulls **SDL3 `release-3.2.x`** as the default
backend; the JSL backend is opt-in via `-DSDL=OFF` (produces
`JoyShockMapper_JSL`).

- [JSM `JoyShockMapper/CMakeLists.txt`](https://github.com/Electronicks/JoyShockMapper/blob/master/JoyShockMapper/CMakeLists.txt) — SDL3 default, JSL opt-in
- [JSM `CHANGELOG.md`](https://github.com/Electronicks/JoyShockMapper/blob/master/CHANGELOG.md) — SDL3 in 3.6.2
- Background: [JoyShockMapper 3 and the Future (GyroWiki)](http://gyrowiki.jibbsmart.com/blog:joyshockmapper-3-and-the-future)

**SDL3 native support for the pad.** SDL3 has a dedicated HIDAPI driver for
the Ultimate 2 Wireless. It matches `USB_PRODUCT_8BITDO_ULTIMATE2_WIRELESS`,
detects the 34-byte v1.03 report, and exposes sensors.

- [SDL3 `SDL_hidapi_8bitdo.c`](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_8bitdo.c)
- Commits through **2026-01** — actively maintained.

**Release status gotcha.** JSM **3.6.2 is unreleased** (master only). Latest
tagged release is **3.6.1 (Feb 2025)**, which predates the SDL3 default
switch. To test this path, build JSM from master — CMake + the bundled
`SDL3-shared` produce a drop-in `JoyShockMapper.exe` with `SDL3.dll` next
to it.

### 2. Fork JSL — now redundant

**Shape of an add-device PR.** JSL uses a monolithic enum + switch pattern,
not a class hierarchy. Adding one device requires: a new `ControllerType`
enum value, VID/PID constants, a branch in `JslConnectDevices()`, and a
full per-device HID handler (`handle_input`, calibration, rumble, gyro
scaling, button decode).

- [JSL `JoyShock.cpp`](https://github.com/JibbSmart/JoyShockLibrary/blob/eba751b6bddf5edc783790af35b663dec7495dcc/JoyShockLibrary/JoyShock.cpp) — VID/PID table + `ControllerType` init
- [JSL `JoyShockLibrary.cpp`](https://github.com/JibbSmart/JoyShockLibrary/blob/eba751b6bddf5edc783790af35b663dec7495dcc/JoyShockLibrary/JoyShockLibrary.cpp) — `JslConnectDevices()` vendor switch
- Estimated scope: ~400–700 LoC for a fresh device (DS4 handler is ~300 LoC and the Ultimate 2 HID layout is unknown to JSL).

**Staleness.** Last JSL commit **2023-09-20**; last release **v3.0
(2023-04-02)**. Downstream is now `JoyShockMapper_JSL`, a legacy
compatibility flag. Forking into a dead repo for a path that JSM itself
has deprecated is the wrong direction.

### 3. Virtual DualSense — no viable free substrate

**ViGEmBus is archived.** [`nefarius/ViGEmBus`](https://github.com/nefarius/ViGEmBus)
archived 2023-11-02 (trademark conflict with ViGEM GmbH). Final release
v1.22.0, tagged "It's dead, Jim." Supports X360 + DS4 only — **never
shipped DS5/DualSense output**. The LizardByte fork
([`Virtual-Gamepad-Emulation-Bus`](https://github.com/LizardByte/Virtual-Gamepad-Emulation-Bus))
was also archived 2025-08. Nefarius' commercial successor
[VirtualPad](https://docs.nefarius.at/projects/VirtualPad/) is B2B/closed.

**No open-source virtual DualSense driver exists.** Search swept the
`nefarius` namespace, GitHub for "ViGEmBus DualSense", "HID minidriver
DualSense emulate", "virtual DualSense driver Windows", "DS4Windows
DualSense output." Result: nothing that presents as Sony
`054C:0CE6` (DS5) or `054C:0DF2` (DS Edge).

**DIY via `vhidmini2` is blocked on signing.** Microsoft ships a
[`vhidmini2` UMDF sample](https://github.com/microsoft/Windows-driver-samples/tree/main/hid/vhidmini2)
that could be extended with a DS5 descriptor (documented at
[`nondebug/dualsense`](https://github.com/nondebug/dualsense)), but the
output is unsigned. End users would need test-signing mode
(`bcdedit /set testsigning on`, reboot, desktop watermark). Attestation
or WHQL signing requires an EV cert (~$300/yr) and Partner Center
submission. Kernel anti-cheats (EAC, BattlEye, Vanguard) may flag a
novel unsigned driver spoofing a Sony VID/PID.

### 4. Commercial tools — shape mismatch

Neither reWASD nor DSX/DSX+ exposes a synthetic-input API that a Python
bridge could feed into.

- **reWASD** (Disc Soft, ~$19.95 lifetime): virtual output is
  ViGEmBus DS4 (same 14-button ceiling). Virtual DS5 has been on their
  roadmap since 2020 and is still not shipped. CLI
  (`reWASDCommandLine.exe`) only toggles profiles/remap. The vendor
  forum explicitly states reWASD has no input API and does not detect
  synthetic input devices.
  - [reWASD CLI docs](https://help.rewasd.com/interface/command-line.html)
  - [Forum — no virtual DS5](https://forum.rewasd.com/forum/rewasd/technical-questions-aa/222621-do-you-have-any-plans-to-have-the-ps5-dualsense-as-a-virtual-controller)
  - [Forum — no API](https://forum.rewasd.com/forum/rewasd/technical-questions-aa/238468-does-rewasd-support-an-api)

- **DSX+** ($11.98 Steam bundle): *does* install a virtual DualSense
  (Nefarius VirtualPad under the hood), but its UDP API only carries
  adaptive-trigger effects, lightbar, player LED, mic LED, and rumble
  — it assumes a **real** DualSense is supplying the buttons/sticks.
  Wrong shape for an 8BitDo bridge.
  - [DSX+ DLC on Steam](https://store.steampowered.com/app/2345650/DSX_Virtual_DualSense_BT_AudioHaptics_DLC/)
  - [DSXpp UDP API wrapper](https://github.com/tpetsas/DSXpp)

## Unknowns

1. **Does SDL3's `SDL_hidapi_8bitdo.c` actually expose the gyro IMU, and
   at ±2000 dps?** The existing `FINDINGS/gyro_hid.md` states that SDL
   (in its older form) does **not** surface gyro from the Ultimate 2 in
   DInput mode, forcing the pad to be read via raw HIDAPI. The new
   SDL3 driver landed after that note was written; it reads the 34-byte
   v1.03 report and advertises "sensors" in the source, but whether
   those are plumbed through as `SDL_SENSOR_GYRO` at full scale — and
   whether JSM's `SDLWrapper.cpp` then emits them on JSM's gyro
   bindings — has not been verified on a live build. **This is the
   linchpin of the recommendation.**
2. **Do all 17 buttons reach JSM's binding surface via SDL3?** SDL3
   may map the pad to its standard `SDL_Gamepad` layout (13 inputs)
   and leave the 4 extras as raw joystick buttons. JSM's `SDLWrapper`
   behaviour with out-of-gamepad-layout buttons is not confirmed.
3. **Does DInput mode on the pad vs. the SDL3 driver's expected mode
   match?** The SDL3 driver matches on USB VID/PID. DInput mode is the
   8BitDo's native VID/PID (`2DC8:6012`), which is what `SDL_hidapi_8bitdo.c`
   recognises — so on paper this should line up, but it's an assumption
   until tested.
4. **DSX+ virtual-DualSense details.** Whether it registers
   `054C:0CE6` on the bus and whether the driver component is
   separable from the UI was not verifiable without installing. Moot
   unless the SDL3 path fails *and* a signing-free alternative becomes
   necessary.

## Proposed follow-up task breakdown

For the next session / next handoff. Scope: **verify, don't design.**

1. **Build JSM from master.** Clone `Electronicks/JoyShockMapper`, build
   with CMake defaults (`SDL=ON`, implied), confirm `SDL3.dll` and the
   JSM exe appear together in `build/`. No code changes.
2. **Connect the pad in DInput mode (hold B on power-on).** Verify
   JSM sees it as a recognised controller and prints a sensible name.
3. **Button coverage probe.** In JSM's console, bind each of the 17
   physical inputs in turn and press to confirm. Flag any that don't
   register. If L4/R4/PL/PR don't register, escalate with an SDL3
   issue (the `SDL_hidapi_8bitdo` driver is the natural place to
   extend).
4. **Gyro probe.** Map `GYRO` in JSM, confirm motion. If gyro is silent,
   check: (a) SDL3 sees a sensor via `SDL_GetSensorData`, (b) JSM's
   `SDLWrapper.cpp` reads it. If silent at SDL3 level, that's the
   `FINDINGS/gyro_hid.md` caveat still applying — fall through to the
   ViGEm-DS4 bridge as the fallback.
5. **Range probe.** If gyro reads, verify ±2000 dps full scale (use a
   quick spin and check reported dps against `gyro_meter.py`).
6. **Retire `tools/jsm_bridge.py`** once coverage + gyro are confirmed.
   Update `FINDINGS/gyro_hid.md` to note SDL3 exposes sensors on the
   Ultimate 2 in DInput mode (superseding the earlier caveat).

If step 4 or 5 fails, the fallback is the existing ViGEm-DS4 bridge (status
quo, loses 4 buttons). The virtual-DualSense driver and JSL-fork paths
are not worth pursuing unless the SDL3 path reveals a specific,
fixable gap.
