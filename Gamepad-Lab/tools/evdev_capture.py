#!/usr/bin/env python3
"""evdev_capture.py — enumerate and capture Linux input events at the evdev plane.

Part of the Mapper Conversion Lab oracle harness (see mapper-conversion-lab-plan.md,
Phase 0). The lab observes a mapper's *emitted* keyboard/mouse output at /dev/input/event*
because that plane is compositor-agnostic (works the same under Wayland or X11). This tool
is the output observer: it lists devices so you can identify the mapper's virtual
keyboard/mouse, then logs the events those devices emit with timestamps.

Modes
  list                     Enumerate every readable /dev/input/event* with name + a capability
                           summary (does it have KEY_SPACE? BTN_LEFT? REL_X? -> is it a
                           keyboard / mouse / gamepad / a mapper's virtual output device).
  capture [opts]           select() over chosen devices and log KEY/BTN/REL/ABS events.

Capture options
  --name SUBSTR            Only watch devices whose name contains SUBSTR (case-insensitive,
                           repeatable). Default: all readable event devices.
  --exclude SUBSTR         Skip devices whose name contains SUBSTR (repeatable).
  --grab                   EVIOCGRAB every matched device so their events do NOT reach the
                           compositor. Use when capturing a mapper's synthetic SPACE / clicks
                           so they don't leak into the focused window. (Cannot grab a device
                           another process already grabbed.)
  --grab-name SUBSTR       EVIOCGRAB only matched devices whose name contains SUBSTR
                           (repeatable). Use to watch an INPUT device read-only (so the mapper
                           keeps reading it) while grabbing only the mapper's OUTPUT devices.
                           Overrides --grab when given.
  --seconds N              Stop after N seconds (default: run until Ctrl-C).
  --types T[,T...]         Event types to log: key,rel,abs,syn (default: key,rel).
  --jsonl PATH             Append one JSON object per event to PATH (in addition to stdout).

Requires: python-evdev, and read access to /dev/input/event* (the `input` group).
"""
import argparse
import json
import sys
import time
from select import select

try:
    from evdev import InputDevice, ecodes, list_devices
except ImportError:
    sys.exit("python-evdev not found. Install: sudo pacman -S python-evdev")

TYPE_NAME = {
    ecodes.EV_KEY: "KEY",
    ecodes.EV_REL: "REL",
    ecodes.EV_ABS: "ABS",
    ecodes.EV_SYN: "SYN",
}
TYPE_FROM_ARG = {
    "key": ecodes.EV_KEY,
    "rel": ecodes.EV_REL,
    "abs": ecodes.EV_ABS,
    "syn": ecodes.EV_SYN,
}


def open_readable():
    devs = []
    for path in sorted(list_devices(), key=lambda p: int(p.rsplit("event", 1)[-1])):
        try:
            devs.append(InputDevice(path))
        except (PermissionError, OSError):
            pass
    return devs


def cap_summary(dev):
    caps = dev.capabilities()
    keys = set(caps.get(ecodes.EV_KEY, []))
    rel = set(caps.get(ecodes.EV_REL, []))
    abs_ = set(caps.get(ecodes.EV_ABS, []))
    tags = []
    if ecodes.KEY_SPACE in keys or ecodes.KEY_A in keys:
        tags.append("keyboard")
    if ecodes.BTN_LEFT in keys and (ecodes.REL_X in rel or ecodes.REL_Y in rel):
        tags.append("mouse")
    if ecodes.BTN_SOUTH in keys or ecodes.BTN_GAMEPAD in keys:
        tags.append("gamepad")
    if abs_ and not tags:
        tags.append("abs-axes")
    return ",".join(tags) or "other"


def code_name(etype, code):
    names = ecodes.bytype.get(etype, {}).get(code)
    if isinstance(names, (list, tuple)):
        return names[0]
    return names if names else f"{code}"


def do_list():
    devs = open_readable()
    if not devs:
        print("No readable event devices (are you in the `input` group?).", file=sys.stderr)
    for dev in devs:
        print(f"{dev.path:<22} [{cap_summary(dev):<16}] {dev.name!r}  "
              f"(bus={dev.info.bustype:#06x} vid={dev.info.vendor:#06x} pid={dev.info.product:#06x})")
        dev.close()


def do_capture(args):
    want_types = {TYPE_FROM_ARG[t.strip()] for t in args.types.split(",") if t.strip()}
    names = [n.lower() for n in (args.name or [])]
    excludes = [n.lower() for n in (args.exclude or [])]
    grab_names = [g.lower() for g in (args.grab_name or [])]

    watched = {}
    grabbed = set()
    for dev in open_readable():
        ln = dev.name.lower()
        if names and not any(n in ln for n in names):
            dev.close(); continue
        if any(x in ln for x in excludes):
            dev.close(); continue
        should_grab = any(g in ln for g in grab_names) if grab_names else args.grab
        if should_grab:
            try:
                dev.grab(); grabbed.add(dev.fd)
            except OSError as e:
                print(f"# WARN: could not grab {dev.name!r}: {e}", file=sys.stderr)
        watched[dev.fd] = dev

    if not watched:
        sys.exit("No devices matched --name/--exclude filters.")

    print(f"# watching {len(watched)} device(s):", file=sys.stderr)
    for dev in watched.values():
        print(f"#   {dev.path}  {dev.name!r}{'  [GRABBED]' if dev.fd in grabbed else ''}", file=sys.stderr)
    print(f"# types={sorted(TYPE_NAME[t] for t in want_types)}  "
          f"{'seconds='+str(args.seconds) if args.seconds else 'until Ctrl-C'}", file=sys.stderr)

    jf = open(args.jsonl, "a") if args.jsonl else None
    deadline = (time.monotonic() + args.seconds) if args.seconds else None
    count = 0
    try:
        while True:
            if not watched:
                break
            timeout = None
            if deadline is not None:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
            r, _, _ = select(watched.keys(), [], [], timeout)
            for fd in r:
                dev = watched[fd]
                try:
                    for ev in dev.read():
                        if ev.type not in want_types:
                            continue
                        rec = {
                            "t": round(ev.timestamp(), 6),
                            "dev": dev.name,
                            "type": TYPE_NAME.get(ev.type, str(ev.type)),
                            "code": code_name(ev.type, ev.code),
                            "value": ev.value,
                        }
                        count += 1
                        print(f"{rec['t']:.6f}  {rec['dev']!r:<34} {rec['type']:<3} "
                              f"{rec['code']:<16} {rec['value']}")
                        sys.stdout.flush()
                        if jf:
                            jf.write(json.dumps(rec) + "\n"); jf.flush()
                except OSError:
                    # device went away (unplug / driver reload): drop it so select()
                    # doesn't spin on a dead fd that stays perpetually "ready".
                    if dev.fd in grabbed:
                        try:
                            dev.ungrab()
                        except OSError:
                            pass
                        grabbed.discard(dev.fd)
                    watched.pop(fd, None)
                    try:
                        dev.close()
                    except OSError:
                        pass
    except KeyboardInterrupt:
        pass
    finally:
        if jf:
            jf.close()
        for dev in watched.values():
            try:
                if dev.fd in grabbed:
                    dev.ungrab()
            except OSError:
                pass
            dev.close()
        print(f"# captured {count} event(s).", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode")
    sub.add_parser("list", help="enumerate readable event devices")
    c = sub.add_parser("capture", help="capture events from matched devices")
    c.add_argument("--name", action="append", help="only watch devices whose name contains SUBSTR")
    c.add_argument("--exclude", action="append", help="skip devices whose name contains SUBSTR")
    c.add_argument("--grab", action="store_true", help="EVIOCGRAB all matched devices (hide from compositor)")
    c.add_argument("--grab-name", action="append", help="EVIOCGRAB only matched devices whose name contains SUBSTR")
    c.add_argument("--seconds", type=float, default=0, help="stop after N seconds")
    c.add_argument("--types", default="key,rel", help="event types: key,rel,abs,syn")
    c.add_argument("--jsonl", help="append events as JSON lines to PATH")
    args = p.parse_args()
    if args.mode == "capture":
        do_capture(args)
    else:
        do_list()


if __name__ == "__main__":
    main()
