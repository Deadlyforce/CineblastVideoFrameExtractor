"""Helpers OpenCV pour le fallback sans ffmpeg — extraits de Video Frame Extractor.py (Lot 7c)."""

import subprocess
import numpy as np


def detect_limited_range_opencv(vpath, cap, video_info):
    """Détecte si le flux est en range limité (tv/mpeg) via ffprobe ou heuristique pixel."""
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=color_range", "-of", "csv=p=0", vpath]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            out = r.stdout.strip().lower()
            if "tv" in out or "mpeg" in out: return True
            if "pc" in out or "full" in out: return False
    except Exception:
        pass
    try:
        dur = video_info.get("duration", 0)
        mins = []; maxs = []
        for pos in [5000, dur * 500, max(0, dur * 1000 - 5000)]:
            cap.set(1, pos)  # cv2.CAP_PROP_POS_MSEC = 1
            ret, f = cap.read()
            if ret:
                mins.append(int(f.min()))
                maxs.append(int(f.max()))
        if mins and min(mins) >= 14 and max(maxs) <= 237:
            return True
    except Exception:
        pass
    return False


def expand_limited_range(frame):
    """Convertit un frame BGR range limité (16-235) vers full range (0-255)."""
    f = frame.astype(np.float32)
    return np.clip((f - 16.0) * (255.0 / 219.0), 0, 255).astype(np.uint8)