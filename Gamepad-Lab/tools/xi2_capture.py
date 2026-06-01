#!/usr/bin/env python3
"""xi2_capture.py — observe X11 / XInput2 input events (the Steam-Input lane observer).

Counterpart to `evdev_capture.py`. On Wayland, Steam Input's keyboard/mouse output is NOT visible at
evdev (`/dev/input/event*`) but IS visible at the X11/XInput2 layer through Xwayland. This tool watches
XI2 events (by shelling `xinput test-xi2 --root`) and logs each event's SOURCE DEVICE:
  * `xwayland-keyboard:N` / `xwayland-pointer:N`  -> the Xwayland SEAT. On an EIS-enabled Xwayland
        (KWin / recent Xwayland) this is where Wayland seat input, libei injection, AND classic X11
        XTEST ALL surface — verified on this box: `xdotool key F9` (pure XTEST) lands here, not on the
        XTEST device. So the device-id confirms the PLANE (X11/XI2, not evdev) but does NOT reveal the
        upstream injector — XTEST vs libei vs physical are not separable here.
  * `Virtual core XTEST keyboard` / `... XTEST pointer` -> the legacy X11 XTEST slave; may be UNUSED on
        EIS-Xwayland (XTEST is rerouted to the seat above). On a real X11 session it carries XTEST.
  * a named physical slave device                 -> real hardware (mainly X11 sessions).
See `findings/steam_input_linux.md` (Phase 0b: real Steam Input F9 was observable at XI2 on
`xwayland-keyboard`, never at evdev; the XTEST-vs-libei mechanism is undetermined).

Modes
  devices                 List XI2 devices (id -> name) with seat/XTEST/xwayland flags.
  capture [opts]          Stream XI2 events; log (time, event, device-id, device-name, code/keysym).

capture options
  --device SUBSTR         Only log events whose source device NAME contains SUBSTR (repeatable).
  --types T[,T...]        key,button,motion,raw  (default: key,button)
  --seconds N             Stop after N seconds (default: until Ctrl-C).
  --jsonl PATH            Append one JSON object per event to PATH.

Notes
  * Timestamps are this tool's wall-clock at parse time (`xinput` is run under `stdbuf -oL` for
    line-buffered, near-real-time delivery; small subprocess jitter applies — fine for order, rough for
    sub-ms latency).
  * Keysym names are best-effort via python-xlib if importable; otherwise the raw X keycode is logged.
  * Requires `xinput` (pkg: xorg-xinput) and an X/Xwayland display ($DISPLAY).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time

EVENT_RE = re.compile(r"EVENT type \d+ \((\w+)\)")
DEVICE_RE = re.compile(r"^\s*device:\s*(\d+)")
DETAIL_RE = re.compile(r"^\s*detail:\s*(\d+)")

KEY_EVENTS = {"KeyPress", "KeyRelease", "RawKeyPress", "RawKeyRelease"}
BUTTON_EVENTS = {"ButtonPress", "ButtonRelease", "RawButtonPress", "RawButtonRelease"}
MOTION_EVENTS = {"Motion", "RawMotion"}
RAW_EVENTS = {"RawKeyPress", "RawKeyRelease", "RawButtonPress", "RawButtonRelease", "RawMotion"}

TYPE_GROUP = {"key": KEY_EVENTS, "button": BUTTON_EVENTS, "motion": MOTION_EVENTS, "raw": RAW_EVENTS}
BUTTON_NAME = {1: "BTN_LEFT", 2: "BTN_MIDDLE", 3: "BTN_RIGHT", 4: "WHEEL_UP", 5: "WHEEL_DOWN",
               6: "WHEEL_LEFT", 7: "WHEEL_RIGHT", 8: "BTN_BACK", 9: "BTN_FORWARD"}


def require_xinput():
    if not shutil.which("xinput"):
        sys.exit("xinput not found. Install: sudo pacman -S xorg-xinput")


def device_map():
    """id -> name, parsed from `xinput list`."""
    out = subprocess.run(["xinput", "list"], capture_output=True, text=True).stdout
    m = {}
    for line in out.splitlines():
        mm = re.search(r"↳?\s*(.+?)\s+id=(\d+)\s+\[(.+?)\]", line)
        if mm:
            m[int(mm.group(2))] = (mm.group(1).strip(), mm.group(3).strip())
    return m


def device_flag(name):
    n = name.lower()
    if "xtest" in n:
        return "X11-XTEST-dev(oft-unused-on-EIS)"
    if "xwayland" in n:
        return "Xwayland-seat(XTEST/libei/phys)"
    if "virtual core" in n:
        return "master"
    return "physical"


def make_keysym_lookup():
    try:
        from Xlib import display, XK  # type: ignore
        d = display.Display()
        rev = {getattr(XK, k): k[3:] for k in dir(XK) if k.startswith("XK_")}

        def lookup(keycode):
            try:
                ks = d.keycode_to_keysym(keycode, 0)
                return rev.get(ks, f"kc{keycode}")
            except Exception:
                return f"kc{keycode}"
        return lookup
    except Exception:
        return lambda keycode: f"kc{keycode}"


def do_devices():
    for did, (name, types) in sorted(device_map().items()):
        print(f"  id={did:<3} [{device_flag(name):<28}] {name!r}  ({types})")


def do_capture(args):
    want = set()
    for t in args.types.split(","):
        want |= TYPE_GROUP.get(t.strip(), set())
    devfilter = [d.lower() for d in (args.device or [])]
    keysym = make_keysym_lookup()
    devs = device_map()

    proc = subprocess.Popen(["stdbuf", "-oL", "xinput", "test-xi2", "--root"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if proc.stdout is None:
        sys.exit("failed to capture xinput stdout")
    timer = None
    if args.seconds:
        timer = threading.Timer(args.seconds, proc.terminate)
        timer.daemon = True
        timer.start()

    jf = open(args.jsonl, "a") if args.jsonl else None
    cur = dev = det = None
    count = 0
    print(f"# xinput test-xi2 --root  types={sorted(want)}  "
          f"{'seconds='+str(args.seconds) if args.seconds else 'until Ctrl-C'}", file=sys.stderr)

    def emit():
        nonlocal count
        if not cur or cur not in want:
            return
        dname = devs.get(dev, (f"id{dev}", "?"))[0] if dev is not None else "?"
        if dev is not None and dev not in devs:           # device appeared since start; refresh once
            devs.update(device_map()); dname = devs.get(dev, (f"id{dev}", "?"))[0]
        if devfilter and not any(f in dname.lower() for f in devfilter):
            return
        if cur in KEY_EVENTS:
            code = keysym(det) if det is not None else "?"
        elif cur in BUTTON_EVENTS:
            code = BUTTON_NAME.get(det, f"btn{det}") if det is not None else "?"
        else:
            code = "motion"
        rec = {"t": round(time.time(), 6), "event": cur, "dev_id": dev, "dev": dname,
               "code": code, "flag": device_flag(dname)}
        count += 1
        print(f"{rec['t']:.6f}  {rec['event']:<14} id={str(rec['dev_id']):<3} "
              f"{rec['code']:<12} [{rec['flag']}] {rec['dev']!r}")
        sys.stdout.flush()
        if jf:
            jf.write(json.dumps(rec) + "\n"); jf.flush()

    try:
        for line in proc.stdout:
            m = EVENT_RE.search(line)
            if m:
                emit(); cur = m.group(1); dev = det = None; continue
            md = DEVICE_RE.match(line)
            if md and dev is None:  # keep the first device: per event block; ignore later device:/sourceid: lines
                dev = int(md.group(1)); continue
            dd = DETAIL_RE.match(line)
            if dd and det is None:
                det = int(dd.group(1)); continue
        emit()  # flush last
    except KeyboardInterrupt:
        pass
    finally:
        if timer:
            timer.cancel()
        proc.terminate()
        if jf:
            jf.close()
        print(f"# captured {count} event(s).", file=sys.stderr)


def main():
    require_xinput()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode")
    sub.add_parser("devices", help="list XI2 devices with seat/XTEST flags")
    c = sub.add_parser("capture", help="stream and log XI2 events")
    c.add_argument("--device", action="append", help="only log events from devices whose name contains SUBSTR")
    c.add_argument("--types", default="key,button", help="key,button,motion,raw")
    c.add_argument("--seconds", type=float, default=0, help="stop after N seconds")
    c.add_argument("--jsonl", help="append events as JSON lines to PATH")
    args = p.parse_args()
    if args.mode == "capture":
        do_capture(args)
    else:
        do_devices()


if __name__ == "__main__":
    main()
