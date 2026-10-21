import ctypes
import json
import time
from ctypes import wintypes

import mss
from PIL import Image

from .config import BASE_DIR

OWN_TITLE = "meeting answers"
REGION_FILE = BASE_DIR / "region.json"
ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def to_image(shot):
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def monitors():
    with mss.mss() as sct:
        return [dict(m) for m in sct.monitors]


def virtual_screen():
    m = monitors()[0]
    return m["left"], m["top"], m["width"], m["height"]


def load_region():
    try:
        data = json.loads(REGION_FILE.read_text(encoding="utf-8"))
        region = tuple(int(v) for v in data["region"])
        if len(region) == 4 and region[2] > 0 and region[3] > 0:
            return region
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save_region(region):
    try:
        REGION_FILE.write_text(json.dumps({"region": list(region)}), encoding="utf-8")
    except OSError:
        pass


def clear_saved_region():
    try:
        REGION_FILE.unlink()
    except OSError:
        pass


def grab_area(sct, left, top, width, height):
    bounds = sct.monitors[0]
    x1 = max(int(left), bounds["left"])
    y1 = max(int(top), bounds["top"])
    x2 = min(int(left + width), bounds["left"] + bounds["width"])
    y2 = min(int(top + height), bounds["top"] + bounds["height"])
    if x2 - x1 < 20 or y2 - y1 < 20:
        return None
    return to_image(sct.grab({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}))


def find_windows(keywords):
    if not keywords:
        return []
    user32 = ctypes.windll.user32
    rects = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()
        if OWN_TITLE in title or not any(k in title for k in keywords):
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width > 200 and height > 150:
            rects.append((rect.left, rect.top, width, height))
        return True

    user32.EnumWindows(ENUM_PROC(callback), 0)
    return rects


def grab(region=None, monitor="all"):
    with mss.mss() as sct:
        if region:
            img = grab_area(sct, *region)
            return [img] if img else []
        if str(monitor).lower() == "all":
            areas = sct.monitors[1:] or [sct.monitors[0]]
        else:
            index = int(monitor)
            if index < 1 or index >= len(sct.monitors):
                raise ValueError(f"Monitor {index} not found. You have {len(sct.monitors) - 1}.")
            areas = [sct.monitors[index]]
        return [to_image(sct.grab(a)) for a in areas]


def grab_all(region, monitor, window_keywords, frames, interval):
    images = []
    seen = set()
    with mss.mss() as sct:
        for i in range(max(frames, 1)):
            if i:
                time.sleep(interval)
            shots = grab(region, monitor)
            if not region:
                for rect in find_windows(window_keywords):
                    img = grab_area(sct, *rect)
                    if img:
                        shots.append(img)
            for img in shots:
                key = (img.size, tuple(p >> 5 for p in img.convert("L").resize((16, 16)).getdata()))
                if key not in seen:
                    seen.add(key)
                    images.append(img)
    return images
