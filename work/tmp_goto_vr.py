"""Click through the flat menu into the mod's VR page and screenshot it.

The game's menu uses raw input, so the cursor is moved relatively: first clamp
it in the top-left corner, then move by the offset measured on a full-screen
screenshot of the main menu.
"""

import ctypes
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def send_mouse(flags, dx=0, dy=0, data=0):
    mi = MOUSEINPUT(dx, dy, data, flags, 0, ctypes.pointer(ctypes.c_ulong(0)))
    u32.SendInput(1, ctypes.byref(INPUT(0, INPUT._U(mi=mi))), ctypes.sizeof(INPUT))


def move(dx, dy, chunk=40):
    while dx or dy:
        sx = max(-chunk, min(chunk, dx))
        sy = max(-chunk, min(chunk, dy))
        send_mouse(0x0001, sx, sy)
        dx -= sx
        dy -= sy
        time.sleep(0.01)


def click():
    send_mouse(0x0002)
    time.sleep(0.08)
    send_mouse(0x0004)


def shot(name, bbox=(0, 0, 1920, 1080)):
    ImageGrab.grab(bbox=bbox).convert("RGB").save(f"work/shots/{name}.png")
    print("shot", name)


def foreground(title="4A Engine"):
    hwnd = u32.FindWindowW(None, title)
    if not hwnd:
        print("window not found:", title)
        return 0
    fg = u32.GetForegroundWindow()
    fg_thread = u32.GetWindowThreadProcessId(fg, None)
    my_thread = k32.GetCurrentThreadId()
    u32.AttachThreadInput(my_thread, fg_thread, True)
    u32.ShowWindow(hwnd, 9)
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    u32.SetFocus(hwnd)
    time.sleep(0.7)
    u32.AttachThreadInput(my_thread, fg_thread, False)
    return hwnd


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "vr"
    hwnd = foreground()
    r = RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    print("window", r.left, r.top, r.right, r.bottom)
    shot(f"{tag}_front")
    move(-2400, -2400)
    time.sleep(0.4)
    move(1153, 874)  # main menu -> НАСТРОЙКИ
    time.sleep(0.8)
    shot(f"{tag}_hover")
    click()
    time.sleep(4.0)
    shot(f"{tag}_page")
