# 8BitDo Ultimate 2 — Gamepad Input Latency & Gyro Issues on Arch Linux

## System Context

- **OS:** Arch Linux (fresh install per custom guide)
- **GPU:** NVIDIA RTX 4090 (nvidia-open-dkms)
- **Desktop:** KDE/GNOME on Wayland
- **Steam:** Native pacman install (not Flatpak), multilib enabled
- **Game under test:** ArcRadars via Proton Experimental
- **Controller:** 8BitDo Ultimate 2 Wireless

## Problem Summary

Gamepad input exhibits noticeable latency compared to mouse and keyboard. The delay persists across both wired and wireless connections, and even when controller inputs are mapped to keyboard/mouse keys. Gyro input is functional but suffers the worst latency of all input types.

## Root Cause Analysis

### 1. Kernel driver conflict blocking direct HIDAPI access

On standard Arch Linux (unlike SteamOS/Bazzite), the kernel's `hid-generic` or `xpad` driver claims the 8BitDo Ultimate 2 device before Steam can access it. This forces Steam to read input through the kernel's generic input subsystem (`/dev/input/eventN`) rather than directly through `/dev/hidrawN`.

The indirect path adds latency to all inputs. More critically, gyro and extended button data are only available through the hidraw interface, so when hid-generic grabs the device first, Steam either gets no gyro data at all or receives it through a slower, indirect route.

This is confirmed by SDL logs showing `Permission denied` errors when Steam attempts to open `/dev/hidraw*` devices for the controller (vendor `0x2dc8`, product `0x6012` for 2.4GHz dongle mode).

### 2. Connection mode matters significantly

The Ultimate 2 presents different capabilities depending on connection method:

| Mode | Polling Rate | Gyro Available | Extra Buttons | Latency |
|---|---|---|---|---|
| 2.4GHz dongle (D-Input) | ~250–1000Hz | Yes | Yes | Lowest |
| USB-C wired | ~250–1000Hz | Yes | Yes | Lowest |
| Bluetooth | 125Hz (~8ms) | **No** | Limited | Highest |

Bluetooth disables gyro entirely and caps polling at 125Hz. If currently using Bluetooth, switching connection method is the single biggest fix.

### 3. X-Input vs D-Input mode

The controller defaults to X-Input mode on power-on. X-Input is limited to the standard Xbox controller layout and does not expose gyro or additional buttons. D-Input mode (activated by holding **Home + B** on power-on) uses a protocol that directly exposes all sensors and buttons, but requires Steam's HIDAPI driver to read them — which circles back to the kernel driver conflict above.

## Proposed Actions

### Step 1 — Confirm connection mode and device identity

```bash
# Identify the controller
lsusb | grep 2dc8

# Check which kernel driver has claimed it
sudo lsmod | grep xpad
sudo lsmod | grep hid
```

Expected product IDs:
- `6012` — 2.4GHz dongle (D-Input)
- `310b` — USB wired
- `3106` — older model variant

### Step 2 — Remove conflicting kernel drivers

```bash
sudo modprobe -r xpad
sudo modprobe -r hid_xpadneo   # if present
```

### Step 3 — Create udev rules for persistent fix

```bash
sudo tee /etc/udev/rules.d/71-8bitdo-u2w.rules <<'EOF'
# 8BitDo Ultimate 2 Wireless — grant Steam direct hidraw access
# and prevent xpad from claiming the device

# 2.4GHz dongle (D-Input)
ACTION=="add", ATTRS{idVendor}=="2dc8", ATTRS{idProduct}=="6012", MODE="0666"
ACTION=="add", ATTRS{idVendor}=="2dc8", ATTRS{idProduct}=="6012", RUN+="/usr/bin/modprobe -r xpad"

# USB wired
ACTION=="add", ATTRS{idVendor}=="2dc8", ATTRS{idProduct}=="310b", MODE="0666"
ACTION=="add", ATTRS{idVendor}=="2dc8", ATTRS{idProduct}=="310b", RUN+="/usr/bin/modprobe -r xpad"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Step 4 — Switch to D-Input mode

Power off the controller completely (hold Home), then power on by holding **Home + B** simultaneously. This enables D-Input, which is required for gyro and extended button access through Steam's HIDAPI driver.

### Step 5 — Reconnect and restart Steam

1. Unplug and replug the 2.4GHz dongle (or USB cable).
2. Fully quit and relaunch Steam.
3. Go to **Settings → Controller → General Controller Settings**.
4. Verify the controller appears with gyro, rumble, and extra button options visible.

### Step 6 — Verify HIDAPI access in Steam logs

```bash
# Watch Steam's controller log in real time
tail -f ~/.steam/steam/logs/controller.log | grep -i "hidapi\|8bitdo\|gyro"
```

Look for lines showing `SDL_JOYSTICK_HIDAPI_8BITDO (ENABLED)` and confirming the hidraw path is accessible. If you still see `Permission denied` for `/dev/hidraw*`, the udev rules need adjustment — check the hidraw device number and confirm the rules match.

### Step 7 — Configure per-game launch options (optional)

For ArcRadars specifically, add a launch string in Steam:

```
gamemoderun %command%
```

This engages the CPU governor and GPU power management for lower frame times, which compounds with the input latency fix.

## If Latency Persists After These Steps

- **Firmware update:** The Ultimate 2's firmware and dongle firmware should both be on the latest version. Unfortunately, 8BitDo's update tool (Ultimate Software V2) is Windows-only. If firmware is outdated, temporarily boot a Windows environment or use another machine to update.
- **USB polling rate:** Create a udev rule to force 1000Hz USB polling for the dongle.
- **Steam Beta client:** Some HIDAPI fixes for 8BitDo controllers have landed in Steam beta builds before reaching stable. Opt in via Steam → Settings → Interface → Client Beta Participation.
- **Kernel version:** Newer kernels include improved HID drivers for 8BitDo devices. Ensure the system is fully updated with `yay -Syu`.

## References

- [Steam Client Beta — 8BitDo Ultimate 2 support thread](https://steamcommunity.com/groups/SteamClientBeta/discussions/3/591764731433410123/)
- [steam-devices issue #64 — D-Input udev rules](https://github.com/ValveSoftware/steam-devices/issues/64)
- [GamingOnLinux — 8BitDo Ultimate 2 Steam Input support](https://www.gamingonlinux.com/2025/04/8bitdo-ultimate-2-is-getting-full-steam-input-support-for-more-buttons/)
- [SDL3 8BitDo HIDAPI driver source](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_8bitdo.c)
