"""Helpers purs de VFE — extraits de Video Frame Extractor.py (refactor A1).
Aucune dépendance tkinter ici."""
import os
import re
import numpy as np


def hms(s):
    s = int(max(0, s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}h {m:02d}m {sec:02d}s" if h else f"{m}m {sec:02d}s"


def tc_str(s):
    s = int(max(0, s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}h{m:02d}m{sec:02d}s"


def dir_parent_label(path):
    """Libellé court d'un dossier : 'parent/dossier' quand c'est possible."""
    p = os.path.normpath(path)
    base = os.path.basename(p)
    if not base:
        return p
    parent = os.path.basename(os.path.dirname(p))
    if parent and parent != base:
        return f"{parent}/{base}"
    return base


def _parse_tc_from_filename(fname):
    m = re.search(r'_(\d{2})h(\d{2})m(\d{2})s', fname)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return 0


def frame_filename(base, num, t_sec):
    """M6 : format de nommage unique des frames extraites.
    num : numéro 1-based affiché dans le nom de fichier."""
    return f"{base}_{num:04d}_{tc_str(t_sec)}.jpg"


def is_black_frame(arr_rgb, threshold=5):
    """Détecte une frame noire depuis un array RGB numpy."""
    sample = arr_rgb[::8, ::8]
    lum = 0.299 * sample[:, :, 0] + 0.587 * sample[:, :, 1] + 0.114 * sample[:, :, 2]
    return float(lum.mean()) < threshold