"""
gyro_enum.py — diagnose what SDL sees, and whether gyro is reachable.

Dumps:
 - every joystick (raw DInput-style)
 - whether SDL considers it a "game controller" (has a mapping)
 - whether the joystick or controller exposes a gyro sensor
 - every standalone sensor SDL_Sensor sees
"""

import ctypes
import sdl2


print("SDL version: ", end="")
v = sdl2.SDL_version()
sdl2.SDL_GetVersion(ctypes.byref(v))
print("{}.{}.{}".format(v.major, v.minor, v.patch))


def init(flag, name):
    rc = sdl2.SDL_Init(flag)
    print("SDL_Init({}): {}".format(name, "OK" if rc == 0 else
          "FAIL " + sdl2.SDL_GetError().decode()))


init(sdl2.SDL_INIT_JOYSTICK,       "JOYSTICK")
init(sdl2.SDL_INIT_GAMECONTROLLER, "GAMECONTROLLER")
init(sdl2.SDL_INIT_SENSOR,         "SENSOR")


print()
print("=== JOYSTICKS ===")
n = sdl2.SDL_NumJoysticks()
print("SDL_NumJoysticks() =", n)
for i in range(n):
    name = sdl2.SDL_JoystickNameForIndex(i)
    name = name.decode(errors="replace") if name else "<no name>"
    is_gc = bool(sdl2.SDL_IsGameController(i))
    guid = sdl2.SDL_JoystickGetDeviceGUID(i)
    guid_buf = (ctypes.c_char * 33)()
    sdl2.SDL_JoystickGetGUIDString(guid, guid_buf, 33)
    guid_str = guid_buf.value.decode()
    print("  [{}] {!r}".format(i, name))
    print("       GUID        : {}".format(guid_str))
    print("       is_controller: {}".format(is_gc))

    # Open as joystick, probe sensor at that level (SDL 2.0.14+)
    js = sdl2.SDL_JoystickOpen(i)
    if js:
        # SDL_JoystickHasSensor may not be exposed by pysdl2; guard.
        has_gyro = False
        try:
            has_gyro = bool(
                sdl2.SDL_JoystickHasSensor(js, sdl2.SDL_SENSOR_GYRO)
            )
        except Exception as e:
            has_gyro = "not exposed ({})".format(type(e).__name__)
        print("       joystick has_gyro   : {}".format(has_gyro))
        sdl2.SDL_JoystickClose(js)

    if is_gc:
        gc = sdl2.SDL_GameControllerOpen(i)
        if gc:
            has_gyro = bool(
                sdl2.SDL_GameControllerHasSensor(gc, sdl2.SDL_SENSOR_GYRO)
            )
            gc_name = sdl2.SDL_GameControllerName(gc)
            gc_name = gc_name.decode(errors="replace") if gc_name else ""
            print("       controller name     : {!r}".format(gc_name))
            print("       controller has_gyro : {}".format(has_gyro))
            sdl2.SDL_GameControllerClose(gc)


print()
print("=== SENSORS (standalone SDL_Sensor API) ===")
try:
    ns = sdl2.SDL_NumSensors()
    print("SDL_NumSensors() =", ns)
    for i in range(ns):
        sname = sdl2.SDL_SensorGetDeviceName(i)
        sname = sname.decode(errors="replace") if sname else "<no name>"
        stype = sdl2.SDL_SensorGetDeviceType(i)
        print("  [{}] {!r}  type={}".format(i, sname, stype))
except AttributeError as e:
    print("standalone SDL_Sensor API not exposed by pysdl2:", e)


print()
print("Done.")
sdl2.SDL_Quit()
