#!/usr/bin/env python3
"""
Video Frame Extractor  —  v4.0
Nouveautés v4.0 : identité des images par chemin (plus d'indices) —
                  sélection / marquage / suppression / déplacement fiabilisés.
Dépendances : pip install opencv-python Pillow numpy send2trash
              ffmpeg requis (brew/apt/winget install ffmpeg)
"""
import os, json, threading, tkinter as tk, subprocess, shutil, tempfile, time, logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from logging.handlers import RotatingFileHandler
from tkinter import ttk, filedialog, messagebox
from tkinter.font import Font
import cv2
import numpy as np
from PIL import Image, ImageTk
try:
    from send2trash import send2trash          # v4.4 : suppression vers la corbeille
    _TRASH_OK = True
except ImportError:
    send2trash = None
    _TRASH_OK = False

# ── Journal (v4.5) ───────────────────────────────────────────────────────────
LOG_FILE = "VFE_Log.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=512*1024,
                                  backupCount=2, encoding="utf-8")],
)
log = logging.getLogger("vfe")

# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_FILE = "VFE_Config.json"
@dataclass
class AppConfig:
    """v4.2 : schéma unique de la configuration — source de vérité des clés,
    types et valeurs par défaut. Ajouter une option = ajouter un champ ici
    + une ligne dans App._collect_config()."""
    video_path:      str  = ""
    output_dir:      str  = ""
    work_dir:        str  = ""
    generic_name:    str  = "capture"
    mode:            str  = "count"
    count_val:       int  = 20
    interval_val:    int  = 30
    thumb_size:      int  = 150
    col_count:       int  = 4
    preview_size:    int  = 280
    window_size:     str  = "auto"
    sash_left:       int  = 310
    sash_right:      int  = 700
    confirm_delete:  bool = True
    black_filter:    bool = True
    mark_key:        str  = "s"
    marked_files:    list = field(default_factory=list)
    hdr_tonemap:     str  = "hable"
    last_video_dir:  str  = ""
    last_output_dir: str  = ""
    last_work_dir:   str  = ""
    window_h:        int  = 1080

DEFAULT_CONFIG = asdict(AppConfig())   # rétro-compatible (dict des défauts)

def _cast_value(val, default):
    """Convertit val vers le type de default ; retombe sur default si invalide."""
    try:
        if isinstance(default, bool):
            if isinstance(val, bool): return val
            if isinstance(val, str):  return val.strip().lower() in ("1","true","oui","yes","on")
            return bool(val)
        if isinstance(default, int):
            return int(float(val))
        if isinstance(default, list):
            return list(val) if isinstance(val, (list, tuple)) else []
        if isinstance(default, str):
            return default if val is None else str(val)
        return val
    except (ValueError, TypeError):
        return default

def _coerce_config(raw):
    """Fusionne raw avec les défauts du schéma et convertit chaque valeur.
    v4.2 : une config corrompue ne peut plus faire planter le démarrage."""
    if not isinstance(raw, dict):
        raw = {}
    out = {}
    defaults = AppConfig()
    for name, default in asdict(defaults).items():
        out[name] = _cast_value(raw.get(name, default), default)
    return out

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return _coerce_config(json.load(f))
        except Exception:
            log.exception("Config illisible — valeurs par défaut utilisées")
    return _coerce_config({})

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        log.exception("Échec de la sauvegarde de la configuration")

# ─────────────────────────────────────────────────────────────────────────────
#  Palette
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#1e1e1e",
    "sidebar":   "#252526",
    "panel":     "#2d2d2d",
    "panel2":    "#333333",
    "input":     "#3a3a3a",
    "border":    "#3f3f3f",
    "border2":   "#505050",
    "accent":    "#4fc3f7",
    "accent_dk": "#0288d1",
    "accent_bg": "#1a3a4a",
    "danger":    "#f48771",
    "danger_dk": "#a83225",
    "ok":        "#89d185",
    "info_bg":   "#2a2a2a",    # fond du bloc d'infos, très légèrement plus clair que bg
    "t1":        "#d4d4d4",
    "t2":        "#9d9d9d",
    "t3":        "#6e6e6e",
    "sel_bg":    "#264f78",
    "sel_brd":   "#4fc3f7",
    "thumb_bg":  "#1e1e1e",
    "thumb_sel": "#1a3a4a",
    "thumb_hov": "#2a2a2a",
}

F_HEAD  = ("Segoe UI Light",    20)
F_TITLE = ("Segoe UI Semibold", 11)
F_UI    = ("Segoe UI",          10)
F_BOLD  = ("Segoe UI Semibold", 10)
F_SMALL = ("Segoe UI",           9)
F_MONO  = ("Consolas",           9)
F_SECT  = ("Segoe UI",           8)

LEFT_MIN_W   = 300
WINDOW_SIZES = ["auto", "1920x1200", "1920x1080", "1280x800", "1280x720"]
FFMPEG_WORKERS = 3   # v4.1 : nb de ffmpeg en parallèle (passe à 4 si SSD + CPU récent)

# v4.7 (chantier 8) : couture pour la grille virtualisée.
# False = grille historique (1 vignette = 3 widgets).
# True  = canvas fenêtré avec recyclage (activé seulement après validation).
GRID_VIRTUAL = True

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

_FONT_CACHE = {}
def _get_font(font_tuple):
    """v4.6 : cache d'objets Font. La création d'une Font (métriques Tcl) est
    coûteuse ; la mesure de texte est rapide. Une Font par (famille, taille, graisse)."""
    key = (font_tuple[0], font_tuple[1], font_tuple[2] if len(font_tuple) > 2 else "normal")
    f = _FONT_CACHE.get(key)
    if f is None:
        f = Font(family=key[0], size=key[1], weight=key[2])
        _FONT_CACHE[key] = f
    return f

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

def ffmpeg_available():
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

def get_display_size(path, raw_w, raw_h):
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,sample_aspect_ratio,display_aspect_ratio",
            "-of", "csv=p=0", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            if len(parts) >= 4:
                sar_str = parts[2].strip()
                if sar_str and ":" in sar_str:
                    sar_n, sar_d = sar_str.split(":")
                    sar_n, sar_d = int(sar_n), int(sar_d)
                    if sar_n > 0 and sar_d > 0 and (sar_n, sar_d) != (1, 1):
                        return int(round(raw_w * sar_n / sar_d)), raw_h
    except Exception:
        pass
    return raw_w, raw_h

def trash_files(paths):
    """v4.4/v4.5 : envoie une liste de fichiers à la corbeille en UNE opération
    (= une seule restauration groupée possible depuis la corbeille).
    Retourne la liste des erreurs [(path, exception), ...].
    Fallback : os.remove si send2trash est absent ou si l'envoi échoue.
    Normalise les chemins Windows (→ backslashes) pour éviter le bug
    send2trash de mélange / et \\ dans la forme étendue \\\\?\\."""
    existing = [p for p in paths if os.path.exists(p)]
    if not existing:
        return []
    # v4.5 : normalisation Windows (os.path.normpath : / → \ sur Windows,
    # identité sur POSIX). Nécessaire pour que send2trash puisse préfixer
    # proprement avec \\?\ sans produire de chemins mixtes invalides.
    normalized = [os.path.normpath(p) for p in existing]
    if _TRASH_OK:
        try:
            send2trash(normalized)
            return []
        except Exception as ex:
            log.warning("send2trash en échec (%s) — fallback os.remove", ex)
    errors = []
    for p in existing:
        try:
            os.remove(p)
        except Exception as ex:
            errors.append((p, ex))
    return errors

# ─────────────────────────────────────────────────────────────────────────────
#  Extraction ffmpeg — commande corrigée v2.9
# ─────────────────────────────────────────────────────────────────────────────
def build_ffmpeg_cmd(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """
    Construit la commande ffmpeg qui produit un JPEG en full range correct.

    Points clés :
      - scale=out_range=full  : force la conversion limited→full range (16-235 → 0-255)
      - -pix_fmt yuvj420p     : indique à l'encodeur JPEG que les données
                                sont en full range (le 'j' = JPEG range)
      - -q:v 2                : qualité JPEG élevée (1=max, 31=min)
      - -ss avant -i          : seek rapide sur keyframe

    Sans ces flags, ffmpeg copie les valeurs YUV telles quelles dans le JPEG,
    ce qui laisse les noirs à 16/255 et les blancs à 235/255 → image délavée.
    """
    # Filtre vidéo : scale avec conversion de plage + resize si SAR
    if sar_applied:
        vf = f"scale={disp_w}:{disp_h}:out_range=full:flags=lanczos"
    else:
        # scale=iw:ih force quand même la conversion de plage sans redimensionner
        vf = "scale=iw:ih:out_range=full"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t_sec:.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-pix_fmt", "yuvj420p",   # ← CLÉ : JPEG full range
        "-q:v", "2",
        out_path
    ]
    return cmd


def build_ffmpeg_cmd_fallback(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """
    Commande alternative si la première échoue.
    Utilise -vf format=yuvj420p qui force également le full range
    via le changement de format pixel.
    """
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
    filters.append("format=yuvj420p")   # conversion full range
    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{max(0, t_sec - 1):.6f}",   # seek légèrement en arrière
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        out_path
    ]
    return cmd


# ─────────────────────────────────────────────────────────────────────────────
#  Détection HDR et pipeline HDR→SDR  (nouveau v3.0)
# ─────────────────────────────────────────────────────────────────────────────

HDR_TRANSFERS  = {"smpte2084", "arib-std-b67", "smpte428", "bt2020-10", "bt2020-12"}
HDR_PRIMARIES  = {"bt2020"}
HDR_COLORSPACES= {"bt2020nc", "bt2020c", "smpte2085", "ictcp"}

def detect_hdr(vpath):
    """
    Analyse le flux vidéo avec ffprobe et retourne un dict :
      {
        "is_hdr": bool,
        "transfer": str,   # ex. "smpte2084"
        "primaries": str,  # ex. "bt2020"
        "colorspace": str, # ex. "bt2020nc"
        "color_range": str,# ex. "tv"
      }
    """
    info = {"is_hdr": False, "transfer": "", "primaries": "", "colorspace": "", "color_range": ""}
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=color_transfer,color_primaries,color_space,color_range",
            "-of", "csv=p=0",
            vpath
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            parts = [p.strip().lower() for p in r.stdout.strip().split(",")]
            # ffprobe order: color_range, color_space, color_transfer, color_primaries
            # but output order matches show_entries order
            # We use a more robust named approach via json
            pass
    except Exception:
        pass

    # Méthode robuste via JSON
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=color_transfer,color_primaries,color_space,color_range",
            "-of", "json",
            vpath
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            import json as _json
            data = _json.loads(r.stdout)
            streams = data.get("streams", [{}])
            s = streams[0] if streams else {}
            transfer   = s.get("color_transfer",  "").lower()
            primaries  = s.get("color_primaries", "").lower()
            colorspace = s.get("color_space",     "").lower()
            color_range= s.get("color_range",     "").lower()
            is_hdr = (
                transfer   in HDR_TRANSFERS  or
                primaries  in HDR_PRIMARIES  or
                colorspace in HDR_COLORSPACES
            )
            info = {
                "is_hdr":      is_hdr,
                "transfer":    transfer,
                "primaries":   primaries,
                "colorspace":  colorspace,
                "color_range": color_range,
            }
    except Exception:
        pass
    return info


def zscale_available():
    """Vérifie que le build ffmpeg inclut libzimg (nécessaire pour zscale)."""
    try:
        r = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=10)
        return "zscale" in r.stdout
    except Exception:
        return False


def build_ffmpeg_cmd_hdr(vpath, t_sec, out_path, disp_w, disp_h, sar_applied,
                          hdr_info, tonemap_algo="hable"):
    """
    Pipeline HDR→SDR via zscale + tonemap + zscale.
    C'est la méthode correcte pour les vidéos PQ/HLG BT.2020.

    Étapes :
      1. zscale : conversion vers linear light (transfer=linear), primaires bt709
      2. tonemap : compression de la plage de luminance HDR→SDR (algo configurable)
      3. zscale : signal SDR en bt709, full range
      4. format=rgb24 puis conversion JPEG

    Paramètres tonemap_algo : hable (doux, cinéma), mobius (équilibré), reinhard (simple)
    """
    # Détermine si la source est HLG ou PQ pour le filtre zscale
    transfer_in = hdr_info.get("transfer", "smpte2084")
    if "hlg" in transfer_in or "arib" in transfer_in:
        zscale_tin = "arib-std-b67"
    else:
        zscale_tin = "smpte2084"  # PQ (HDR10)

    # Chaîne de filtres
    filters = []

    # Resize si SAR non-carré, avant toute conversion de couleur
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")

    # Étape 1 : linéarisation + conversion primaires BT.2020 → BT.709
    filters.append(
        f"zscale=t=linear:npl=100:p=bt709:m=bt709:r=tv"
    )
    # Étape 2 : tone mapping (HDR → SDR)
    filters.append(
        f"tonemap=tonemap={tonemap_algo}:desat=0:peak=0"
    )
    # Étape 3 : signal SDR propre, full range, BT.709
    filters.append(
        "zscale=t=bt709:p=bt709:m=bt709:r=pc"
    )
    # Étape 4 : format pixel pour l'encodeur JPEG
    filters.append("format=rgb24")

    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t_sec:.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        out_path
    ]
    return cmd


def build_ffmpeg_cmd_hdr_fallback(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """
    Fallback HDR si zscale est absent : utilise colorspace + eq pour
    au moins ramener une image lisible (moins précis mais fonctionnel).
    """
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")

    # Conversion approximative HDR→SDR sans zscale
    # colorspace gère BT.2020→BT.709, puis on force full range
    filters.append("colorspace=bt709:iall=bt2020:fast=1")
    filters.append("scale=iw:ih:out_range=full")
    filters.append("format=yuvj420p")

    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t_sec:.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        out_path
    ]
    return cmd

class DarkButton(tk.Canvas):
    STYLES = {
        "accent":  ("#1a3a4a", "#0d2535", "#4fc3f7", C["accent"],  C["t3"]),
        "danger":  ("#3a1f1f", "#2a1010", "#f48771", "#f48771",    C["t3"]),
        "default": (C["panel2"], C["input"], C["border2"], C["t1"], C["t3"]),
        "ghost":   (C["sidebar"], C["panel"], C["panel"], C["t2"],  C["t3"]),
    }

    def __init__(self, parent, text="", command=None, style="default",
                    width=130, height=32, font=None, anchor="w", padx=10, fg=None, **kw):
            kw.setdefault("bg", parent.cget("bg"))
            super().__init__(parent, width=width, height=height,
                            highlightthickness=0, **kw)
            self.full_text = text
            self.text_display = text
            self.cmd = command
            self.style = style
            self.font = font or F_UI
            self.anchor = anchor
            self.padx = padx
            self.custom_fg = fg
            self._st = "normal"
            # Forcer une largeur minimale si width=0
            if width == 0:
                self.configure(width=130)  # temporaire, sera ajusté par grid
            self.bind("<Configure>", self._on_resize)
            self.bind("<Enter>", self._e_enter)
            self.bind("<Leave>", self._e_leave)
            self.bind("<ButtonPress-1>", self._e_press)
            self.bind("<ButtonRelease-1>", self._e_release)
            # Planifier la première mise à jour
            self.after_idle(self._update_display)

    def _on_resize(self, e):
        self._update_display()

    def _update_display(self):
        self._update_truncated_text()
        self._draw()

    def _update_truncated_text(self):
        w = self.winfo_width()
        if w <= 0:
            return
        available = w - 2 * self.padx - 10  # marge intérieure gauche et droite
        if available <= 10:
            self.text_display = "…"
            return
        font = _get_font(self.font)   # v4.6 : cache — plus de Font() recréée
        text_width = font.measure(self.full_text)
        if text_width <= available:
            self.text_display = self.full_text
        else:
            # Troncature
            for i in range(len(self.full_text), 0, -1):
                candidate = self.full_text[:i] + "…"
                if font.measure(candidate) <= available:
                    self.text_display = candidate
                    break
            else:
                self.text_display = "…"

    def set_text(self, text):
        self.full_text = text
        self._update_display()  # recalcule et redessine

    def _draw(self):
        self.delete("all")
        bg, style_fg = self._cols()
        fg = self.custom_fg if self.custom_fg is not None else style_fg
        r = 7
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 14 or h < 8:
            return
        pts = [r, 1, w-r, 1, w-1, 1, w-1, r, w-1, h-r, w-1, h-1,
            w-r, h-1, r, h-1, 1, h-1, 1, h-r, 1, r, 1, 1]
        # Fond
        self.create_polygon(pts, smooth=True, fill=bg, outline="")
        # Bordure
        if self.style == "default":
            border_color = C["accent"] if self._st in ("hover", "pressed") else C["border"]
            self.create_polygon(pts, smooth=True, fill="", outline=border_color, width=1)
        if self.anchor == "w":
            x = self.padx + 5
        elif self.anchor == "e":
            x = w - self.padx - 5
        else:
            x = w // 2
        y = h // 2
        self.create_text(x, y, text=self.text_display, fill=fg, font=self.font, anchor=self.anchor)

    def _cols(self):
        n, h, p, ft, fd = self.STYLES.get(self.style, self.STYLES["default"])
        if self._st == "disabled":
            return C["panel"], fd
        if self._st == "hover":
            return h, ft
        if self._st == "pressed":
            return p, ft
        return n, ft

    def _e_enter(self, e):
        if self._st != "disabled": self._st = "hover"; self._draw(); self.config(cursor="hand2")
    def _e_leave(self,e):
        if self._st!="disabled": self._st="normal"; self._draw()
    def _e_press(self,e):
        if self._st!="disabled": self._st="pressed"; self._draw()
    def _e_release(self,e):
        if self._st!="disabled":
            self._st="hover"; self._draw()
            if self.cmd: self.cmd()
    def set_state(self,st):
        self._st=st; self._draw()
        self.config(cursor="arrow" if st=="disabled" else "hand2")


class PillSelector(tk.Frame):
    def __init__(self, parent, options, variable, command=None, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, **kw)
        self.options=options; self.var=variable; self.cmd=command; self._pills={}
        self._build()
    def _build(self):
        track=tk.Frame(self,bg=C["input"],padx=3,pady=3); track.pack(fill="x")
        for i,(label,value) in enumerate(self.options):
            track.columnconfigure(i,weight=1)
            c=tk.Canvas(track,height=26,highlightthickness=0,bg=C["input"],cursor="hand2")
            c.grid(row=0,column=i,sticky="ew",padx=2)
            self._pills[value]=c
            c.bind("<Button-1>", lambda e,v=value: self._select(v))
            c.bind("<Enter>",    lambda e,v=value: self._hover(v,True))
            c.bind("<Leave>",    lambda e,v=value: self._hover(v,False))
            c.bind("<Configure>",lambda e,v=value: self._draw_pill(v))
    def _select(self,value):
        self.var.set(value)
        for v in self._pills: self._draw_pill(v)
        if self.cmd: self.cmd()
    def _hover(self,value,on):
        if self.var.get()!=value: self._draw_pill(value,hover=on)
    def _draw_pill(self,value,hover=False):
        c=self._pills[value]; c.delete("all")
        w=c.winfo_width() or 120; h=c.winfo_height() or 26
        sel=(self.var.get()==value)
        label=next(l for l,v in self.options if v==value)
        r=5
        if sel:    bg,fg=C["accent_bg"],C["accent"]
        elif hover:bg,fg=C["panel2"],C["t1"]
        else:      bg,fg=C["input"],C["t2"]
        pts=[r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        c.create_polygon(pts,smooth=True,fill=bg,outline=bg)
        c.create_text(w//2,h//2,text=label,fill=fg,
                      font=(F_BOLD if sel else F_SMALL),anchor="center")


class DarkSlider(tk.Frame):
    def __init__(self,parent,from_,to,resolution,variable,
                 label="",unit="",command=None,**kw):
        kw.setdefault("bg",parent.cget("bg"))
        super().__init__(parent,**kw)
        self.columnconfigure(0,weight=1); self._cmd=command; self._unit=unit
        top=tk.Frame(self,bg=self.cget("bg")); top.grid(row=0,column=0,sticky="ew")
        top.columnconfigure(1,weight=1)
        tk.Label(top,text=label,font=F_SMALL,fg=C["t2"],
                 bg=self.cget("bg"),anchor="w").grid(row=0,column=0,sticky="w")
        self._val_lbl=tk.Label(top,text="",font=F_BOLD,fg=C["accent"],
                               bg=self.cget("bg"),anchor="e")
        self._val_lbl.grid(row=0,column=1,sticky="e")
        self._scale=tk.Scale(self,from_=from_,to=to,resolution=resolution,
                             orient="horizontal",variable=variable,
                             bg=C["bg"],fg=C["t1"],troughcolor=C["input"],
                             activebackground=C["accent"],highlightthickness=0,
                             showvalue=False,sliderrelief="flat",sliderlength=14,
                             command=self._on_change)
        self._scale.grid(row=1,column=0,sticky="ew",pady=(1,0))
        self._info_lbl=tk.Label(self,text="",font=F_SMALL,fg=C["t3"],
                                bg=self.cget("bg"),anchor="w")
        self._info_lbl.grid(row=2,column=0,sticky="w")
        self._update_label(variable.get())
    def _on_change(self,val): self._update_label(val);(self._cmd and self._cmd(val))
    def _update_label(self,val):
        try:
            v=float(val)
            if self._unit=="s" and v>=60: self._val_lbl.config(text=hms(v))
            elif self._unit=="s":         self._val_lbl.config(text=f"{int(v)} s")
            else: self._val_lbl.config(text=f"{int(v)} {self._unit}".strip())
        except Exception: pass
    def set_info(self,text): self._info_lbl.config(text=text)
    def set_state(self,state): self._scale.config(state=state)


class RoundedCombo(tk.Frame):
    def __init__(self,parent,values,variable,width=80,**kw):
        kw.setdefault("bg",parent.cget("bg"))
        super().__init__(parent,**kw)
        self._values=values; self._var=variable; self._width=width; self._open=False
        self._btn=tk.Canvas(self,height=28,width=width,highlightthickness=0,
                            bg=self.cget("bg"),cursor="hand2")
        self._btn.pack()
        self._btn.bind("<Button-1>",  self._toggle)
        self._btn.bind("<Configure>", lambda e: self._draw())
        self._var.trace_add("write",  lambda *a: self._draw())
    def _draw(self):
        c=self._btn; c.delete("all")
        w=c.winfo_width() or self._width; h=c.winfo_height() or 28; r=7
        pts=[r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        c.create_polygon(pts,smooth=True,fill=C["input"],outline="")
        c.create_text(10,h//2,text=str(self._var.get()),fill=C["t1"],font=F_UI,anchor="w")
        cx=w-14; cy=h//2
        c.create_polygon(cx-4,cy-2,cx+4,cy-2,cx,cy+3,fill=C["t3"],outline="")
    def _toggle(self,event=None):
        if self._open: self._close_menu(); return
        self._open=True
        menu=tk.Menu(self,tearoff=0,bg=C["panel2"],fg=C["t1"],
                     activebackground=C["accent_bg"],activeforeground=C["accent"],
                     relief="flat",bd=0,font=F_UI)
        for v in self._values:
            menu.add_command(label=str(v),command=lambda val=v: self._pick(val))
        menu.tk_popup(self._btn.winfo_rootx(),
                      self._btn.winfo_rooty()+self._btn.winfo_height())
        menu.bind("<Unmap>",lambda e: self._close_menu())
    def _pick(self,val): self._var.set(val); self._open=False; self._draw()
    def _close_menu(self): self._open=False


class DarkEntry(tk.Entry):
    def __init__(self,parent,**kw):
        kw.setdefault("bg",C["input"]); kw.setdefault("fg",C["t1"])
        kw.setdefault("insertbackground",C["t1"]); kw.setdefault("relief","flat")
        kw.setdefault("font",F_UI); kw.setdefault("highlightthickness",1)
        kw.setdefault("highlightbackground",C["border"])
        kw.setdefault("highlightcolor",C["accent"])
        super().__init__(parent,**kw)


class DarkProgress(tk.Canvas):
    def __init__(self,parent,height=4,**kw):
        kw.setdefault("bg",C["bg"])
        super().__init__(parent,height=height,highlightthickness=0,**kw)
        self._v=0; self.bind("<Configure>",lambda e: self._draw())
    def set(self,v): self._v=max(0,min(100,v)); self._draw()
    def _draw(self):
        self.delete("all"); w=self.winfo_width(); h=self.winfo_height()
        if w<4: return
        r=h//2; self._rr(0,0,w,h,r,fill=C["panel2"],outline="")
        if self._v>0:
            fw=max(r*2,int(w*self._v/100))
            self._rr(0,0,fw,h,r,fill=C["accent"],outline="")
    def _rr(self,x1,y1,x2,y2,r,**kw):
        pts=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
             x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        self.create_polygon(pts,smooth=True,**kw)

class ModernScrollbar(tk.Canvas):
    """Scrollbar verticale fine, aux coins arrondis, sans flèche ni marque centrale."""
    def __init__(self, parent, command=None, **kw):
        kw.setdefault("bg", C["bg"])
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("width", 8)
        super().__init__(parent, **kw)
        self.command = command
        self.pack_propagate(False)
        self.configure(width=8)

        # État interne
        self._thumb_top = 0.0
        self._thumb_height = 1.0
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_thumb = 0.0
        self._visible = True   # pouce invisible par défaut


        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

        self._hover = False
        self._base_color = C["border"]   # gris sombre cohérent avec l’interface
        # Ajouter les bindings de survol sur la scrollbar elle-même
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self._hover = True
        self._redraw()

    def _on_leave(self, event):
        self._hover = False
        self._redraw()

    def set(self, first, last):
        """Appelé par le widget lié pour indiquer la portion visible (0.0 à 1.0)."""
        first = max(0.0, min(1.0, float(first)))
        last = max(0.0, min(1.0, float(last)))
        if last <= first:
            first, last = 0.0, 1.0
        self._thumb_top = first
        self._thumb_height = last - first
        self._redraw()

    def _redraw(self, event=None):
        self.delete("all")
        if not self._visible:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return
        thumb_h = max(20, self._thumb_height * h)
        thumb_y = self._thumb_top * h
        thumb_y = max(0, min(thumb_y, h - thumb_h))
        r = min(5, w // 2, thumb_h // 2)
        thumb_color = C["accent"] if self._hover else self._base_color
        self._draw_rounded_rect(2, thumb_y, w - 2, thumb_y + thumb_h, r,
                                fill=thumb_color, outline="")


    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        """Dessine un rectangle aux coins arrondis."""
        points = [x1+r, y1, x2-r, y1,
                  x2, y1, x2, y1+r,
                  x2, y2-r, x2, y2,
                  x2-r, y2, x1+r, y2,
                  x1, y2, x1, y2-r,
                  x1, y1+r, x1, y1]
        self.create_polygon(points, smooth=True, **kw)

    def _on_press(self, event):
        """Début du drag du pouce."""
        h = self.winfo_height()
        thumb_y = self._thumb_top * h
        thumb_h = max(20, self._thumb_height * h)
        if thumb_y <= event.y <= thumb_y + thumb_h:
            self._dragging = True
            self._drag_start_y = event.y
            self._drag_start_thumb = self._thumb_top
            self.configure(cursor="hand2")
        else:
            # Clic en dehors du pouce : saut de page
            if event.y < thumb_y:
                delta = -0.1
            else:
                delta = 0.1
            new_top = max(0.0, min(1.0, self._thumb_top + delta))
            self._move_to(new_top)

    def _on_drag(self, event):
        if not self._dragging:
            return
        h = self.winfo_height()
        if h < 1:
            return
        dy = (event.y - self._drag_start_y) / h
        new_top = max(0.0, min(1.0 - self._thumb_height, self._drag_start_thumb + dy))
        self._move_to(new_top)

    def _on_release(self, event):
        self._dragging = False
        self.configure(cursor="")

    def _move_to(self, top):
        """Appelle la commande de défilement avec 'moveto'."""
        if self.command:
            self.command("moveto", top)
        # La mise à jour du pouce se fera via set(...) rappelé par le widget


class HSep(tk.Frame):
    def __init__(self,parent,**kw):
        super().__init__(parent,bg=C["border"],height=1,**kw)

class SectLabel(tk.Label):
    def __init__(self,parent,text,**kw):
        kw.setdefault("bg",C["bg"]); kw.setdefault("fg",C["t3"])
        kw.setdefault("font",F_SECT); kw.setdefault("anchor","w")
        super().__init__(parent,text=text.upper(),**kw)

class Tooltip:
    DELAY=0
    def __init__(self,widget,text_fn):
        self._w=widget; self._fn=text_fn; self._win=None; self._job=None
        widget.bind("<Enter>", self._schedule,add="+")
        widget.bind("<Leave>", self._cancel,  add="+")
        widget.bind("<Button>",self._cancel,  add="+")
    def _schedule(self,e=None):
        self._cancel(); self._job=self._w.after(self.DELAY,self._show)
    def _cancel(self,e=None):
        if self._job: self._w.after_cancel(self._job); self._job=None
        if self._win: self._win.destroy(); self._win=None
    def _show(self):
        text=self._fn()
        if not text: return
        x=self._w.winfo_rootx(); y=self._w.winfo_rooty()+self._w.winfo_height()+4
        self._win=tw=tk.Toplevel(self._w)
        tw.wm_overrideredirect(True); tw.wm_attributes("-topmost",True)
        PAD=10
        lbl=tk.Label(tw,text=text,font=F_SMALL,fg="#3a2a00",bg="#fffae8",
                     justify="left",padx=PAD,pady=6,relief="flat",bd=0)
        lbl.pack(); tw.update_idletasks()
        w=tw.winfo_reqwidth(); h=tw.winfo_reqheight()
        sw=self._w.winfo_screenwidth()
        if x+w>sw-10: x=sw-w-10
        tw.geometry(f"+{x}+{y}")
        cv=tk.Canvas(tw,width=w,height=h,bg="#fffae8",highlightthickness=0)
        cv.place(x=0,y=0)
        r=8; pts=[r,0,w-r,0,w,0,w,r,w,h-r,w,h,w-r,h,r,h,0,h,0,h-r,0,r,0,0]
        cv.create_polygon(pts,smooth=True,fill="#fffae8",outline="#c8b87a",width=1)
        cv.create_text(PAD,h//2,text=text,font=F_SMALL,fill="#3a2a00",anchor="w",justify="left")
        lbl.lift()

def setup_style(root):
    s=ttk.Style(root); s.theme_use("clam")
    s.configure("TCombobox",fieldbackground=C["input"],background=C["input"],
                foreground=C["t1"],selectbackground=C["sel_bg"],
                selectforeground=C["t1"],bordercolor=C["border"],
                arrowcolor=C["t2"],font=F_UI,padding=4)
    s.map("TCombobox",fieldbackground=[("readonly",C["input"])],
          bordercolor=[("focus",C["accent"])])


def _parse_tc_from_filename(fname):
    import re
    m=re.search(r'_(\d{2})h(\d{2})m(\d{2})s',fname)
    if m: return int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))
    return 0

def is_black_frame(arr_rgb, threshold=5):
    """Détecte une frame noire depuis un array RGB numpy."""
    sample = arr_rgb[::8, ::8]
    lum = 0.299*sample[:,:,0] + 0.587*sample[:,:,1] + 0.114*sample[:,:,2]
    return float(lum.mean()) < threshold


# ─────────────────────────────────────────────────────────────────────────────
#  Grille virtualisée — composant isolé (v4.7 / E65)
# ─────────────────────────────────────────────────────────────────────────────
class VirtualThumbGrid:
    """v4.7 (chantier 8) : renderer virtualisé.
    Dessine uniquement la fenêtre visible et gère un cache PhotoImage borné."""

    def __init__(self, canvas, app):
        self.canvas = canvas
        self.app = app

        # Cache PhotoImage : path -> ((thumb_w, thumb_h), PhotoImage)
        self._photo_cache = {}

        # Anti-mitraillage : un seul redraw programmé à la fois
        self._scheduled = False

        # Métriques de layout
        self._pad_x = 9
        self._pad_y = 8
        self._text_h = 18

    def reload(self):
        self.refresh()

    def refresh(self):
        if self._scheduled:
            return
        self._scheduled = True
        try:
            self.canvas.after_idle(self._redraw)
        except Exception:
            self._scheduled = False

    def _thumb_height(self, thumb_w):
        info = getattr(self.app, "video_info", {}) or {}
        w = info.get("disp_w") or info.get("width") or 0
        h = info.get("disp_h") or info.get("height") or 0

        try:
            w = int(w)
            h = int(h)
        except Exception:
            w = h = 0

        if w > 0 and h > 0:
            return max(24, int(thumb_w * h / w))

        # Fallback raisonnable si la vidéo n'est pas chargée
        return max(24, int(thumb_w * 9 / 16))

    def _metrics(self):
        try:
            cols = max(1, int(self.app.v_cols.get()))
        except Exception:
            cols = 4

        try:
            thumb_w = max(40, int(self.app.v_tsize.get()))
        except Exception:
            thumb_w = 150

        thumb_h = self._thumb_height(thumb_w)

        cell_w = thumb_w + 2 * self._pad_x
        cell_h = thumb_h + self._text_h + 2 * self._pad_y

        return cols, thumb_w, thumb_h, cell_w, cell_h

    def _row_count(self, count, cols):
        if count <= 0:
            return 0
        return (count + cols - 1) // cols

    def _update_scrollregion(self):
        try:
            count = len(self.app.thumbs)
        except Exception:
            count = 0

        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()
        rows = self._row_count(count, cols)

        try:
            canvas_w = max(1, self.canvas.winfo_width())
        except Exception:
            canvas_w = 1

        try:
            canvas_h = max(1, self.canvas.winfo_height())
        except Exception:
            canvas_h = 1

        content_h = rows * cell_h + 1

        width = max(canvas_w, cols * cell_w + 1)
        height = max(canvas_h, content_h)

        self.canvas.configure(scrollregion=(0, 0, width, height))

        if content_h <= canvas_h:
            try:
                self.canvas.yview_moveto(0)
            except Exception:
                pass

    def _redraw(self):
        self._scheduled = False

        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return

        self._update_scrollregion()
        self.canvas.delete("vt")

        try:
            count = len(self.app.thumbs)
        except Exception:
            count = 0

        if count == 0:
            self._photo_cache.clear()
            return

        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()

        try:
            top = self.canvas.canvasy(0)
            bottom = self.canvas.canvasy(max(1, self.canvas.winfo_height()))
        except Exception:
            top, bottom = 0, 1

        buffer = cell_h * 2
        top = max(0, top - buffer)
        bottom += buffer

        first_row = max(0, int(top // cell_h))
        last_row = min(self._row_count(count, cols) - 1, int(bottom // cell_h))

        first_idx = first_row * cols
        last_idx = min(count - 1, (last_row + 1) * cols - 1)

        visible = []

        try:
            sel = self.app.sel
        except Exception:
            sel = set()

        for idx in range(first_idx, last_idx + 1):
            try:
                entry = self.app.thumbs[idx]
            except IndexError:
                continue

            path = entry.get("path", "")
            if not path:
                continue

            visible.append(path)

            row, col = divmod(idx, cols)
            x0 = col * cell_w
            y0 = row * cell_h

            rx0 = x0 + 3
            ry0 = y0 + 3
            rx1 = x0 + cell_w - 3
            ry1 = y0 + cell_h - 3

            if path in sel:
                self.canvas.create_rectangle(
                    rx0, ry0, rx1, ry1,
                    fill=C["thumb_sel"],
                    outline=C["sel_brd"],
                    width=1,
                    tags=("vt", f"vt::{path}", "vtbg"),
                )
            else:
                self.canvas.create_rectangle(
                    rx0, ry0, rx1, ry1,
                    fill=C["thumb_bg"],
                    outline="",
                    tags=("vt", f"vt::{path}", "vtbg"),
                )

            imgtk = self._photo_for(entry, thumb_w, thumb_h)
            if imgtk is not None:
                self.canvas.create_image(
                    x0 + cell_w // 2,
                    y0 + self._pad_y + thumb_h // 2,
                    image=imgtk,
                    anchor="center",
                    tags=("vt", f"vt::{path}"),
                )

            self.canvas.create_text(
                x0 + cell_w // 2,
                y0 + self._pad_y + thumb_h + 4,
                text=hms(entry.get("tc", 0)),
                font=F_SMALL,
                fill=C["t3"],
                anchor="n",
                tags=("vt", f"vt::{path}"),
            )

        self._prune_cache(set(visible))

    def _get_check_icon(self):
        if getattr(self, "_check_icon", None) is None:
            try:
                self._check_icon = self.app._make_check_icon(size=22)
            except Exception:
                self._check_icon = None
        return self._check_icon

    def _photo_for(self, entry, thumb_w, thumb_h):
        path = entry.get("path", "")
        marked = path in getattr(self.app, "marked", set())
        key = (thumb_w, thumb_h, marked)

        cached = self._photo_cache.get(path)
        if cached is not None and cached[0] == key:
            return cached[1]

        img = entry.get("img")
        if img is None:
            try:
                im = Image.open(path)
                im.draft("RGB", (thumb_w, thumb_h))
                img = im.copy()
            except Exception:
                return None

        try:
            th = img.copy()
            th.thumbnail((thumb_w, thumb_h), Image.LANCZOS)

            if marked:
                icon = self._get_check_icon()
                if icon is not None and th.width >= icon.width + 4 and th.height >= icon.height + 4:
                    th_rgba = th.convert("RGBA")
                    x = th_rgba.width - icon.width - 2
                    y = 2
                    th_rgba.paste(icon, (x, y), icon)
                    th = th_rgba.convert("RGB")

            imgtk = ImageTk.PhotoImage(th)
        except Exception:
            return None

        self._photo_cache[path] = (key, imgtk)
        return imgtk

    def _prune_cache(self, visible_paths):
        for path in list(self._photo_cache.keys()):
            if path not in visible_paths:
                self._photo_cache.pop(path, None)

    def update_selection(self):
        if getattr(self, "_sel_scheduled", False):
            return
        self._sel_scheduled = True
        try:
            self.canvas.after_idle(self._update_selection_now)
        except Exception:
            self._sel_scheduled = False

    def _update_selection_now(self):
        self._sel_scheduled = False

        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return

        try:
            sel = self.app.sel
        except Exception:
            sel = set()

        for iid in self.canvas.find_withtag("vtbg"):
            path = None
            for tag in self.canvas.gettags(iid):
                if tag.startswith("vt::"):
                    path = tag[4:]
                    break

            if not path:
                continue

            if path in sel:
                self.canvas.itemconfigure(
                    iid,
                    fill=C["thumb_sel"],
                    outline=C["sel_brd"],
                    width=1,
                )
            else:
                self.canvas.itemconfigure(
                    iid,
                    fill=C["thumb_bg"],
                    outline="",
                    width=1,
                )

    def scroll_to_path(self, path):
        try:
            idx = self.app._position_of(path)
        except Exception:
            idx = -1

        if idx < 0:
            return

        self._update_scrollregion()

        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()
        row = idx // cols

        y0 = row * cell_h
        y1 = y0 + cell_h

        try:
            top = self.canvas.canvasy(0)
            canvas_h = max(1, self.canvas.winfo_height())
        except Exception:
            top, canvas_h = 0, 1

        bottom = top + canvas_h

        if y0 >= top and y1 <= bottom:
            self.refresh()
            return

        count = len(self.app.thumbs)
        rows = self._row_count(count, cols)

        content_h = rows * cell_h + 1
        total_h = max(content_h, canvas_h)

        target = max(0, y0 - canvas_h // 3)
        target = min(target, max(0, total_h - canvas_h))

        try:
            self.canvas.yview_moveto(target / max(1, total_h))
            self.canvas.update_idletasks()
        except Exception:
            pass

        self.refresh()


# ─────────────────────────────────────────────────────────────────────────────
#  Application
# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Frame Extractor  —  v4.0")
        self.configure(bg=C["bg"])
        self._cfg = load_config()
        self._ffmpeg_ok = ffmpeg_available()
        log.info("Démarrage — ffmpeg %s | corbeille (send2trash) %s",
                 "présent" if self._ffmpeg_ok else "ABSENT (fallback OpenCV)",
                 "ACTIVE" if _TRASH_OK else "ABSENTE → suppressions DÉFINITIVES !")

        self.v_path         = tk.StringVar(value=self._cfg["video_path"])
        self.v_outdir       = tk.StringVar(value=self._cfg["output_dir"])
        self.v_outdir.trace_add("write", lambda *a: self._update_refresh_btn_state())

        self.v_workdir      = tk.StringVar(value=self._cfg.get("work_dir",""))
        self.v_generic      = tk.StringVar(value=self._cfg.get("generic_name","capture"))
        self.v_mode         = tk.StringVar(value=self._cfg["mode"])
        self.v_count        = tk.IntVar(value=int(self._cfg["count_val"]))
        self.v_intv         = tk.IntVar(value=int(self._cfg["interval_val"]))
        self.v_tsize        = tk.IntVar(value=int(self._cfg["thumb_size"]))
        self.v_cols         = tk.IntVar(value=int(self._cfg["col_count"]))
        self.v_psize        = tk.IntVar(value=int(self._cfg["preview_size"]))
        self.v_winsize      = tk.StringVar(value=self._cfg.get("window_size","auto"))
        self.v_confirm_del  = tk.BooleanVar(value=bool(self._cfg.get("confirm_delete",True)))
        self.v_black_filter = tk.BooleanVar(value=bool(self._cfg.get("black_filter",True)))
        self.v_mark_key     = tk.StringVar(value=self._cfg.get("mark_key","s"))
        self.v_hdr_tonemap  = tk.StringVar(value=self._cfg.get("hdr_tonemap","hable"))
        # Auto-save sur changement de ces options
        for _v in (self.v_confirm_del, self.v_black_filter, self.v_hdr_tonemap):
            _v.trace_add("write", lambda *a: self._auto_save_config())

        self.video_info={}; self.thumbs=[]; self.thumb_refs={}      # v4 : refs PhotoImage par chemin
        self.thumb_by_path={}                                       # v4 : accès O(1) par chemin
        self.thumb_wids={}; self.sel=set(); self.marked=set()       # v4 : sets de CHEMINS
        self._cancel=False; self._prev_ref=None; self._last_click_path=None
        self._drag_active=False; self._drag_in_zone=False; self._drag_sel_before=set()
        self._hdr_info={}          # résultat detect_hdr() pour la vidéo courante
        self._zscale_ok=None       # cache du test zscale_available()

        self.minsize(LEFT_MIN_W+400,560)
        setup_style(self)
        self._geometry_ready = False
        self._build_ui()
        self._bind_events()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Géométrie précise depuis la config, sashes inclus — synchrone
        self._apply_initial_geometry()

        # _loading_thumbs actif dès maintenant pour bloquer _fit_window
        self._loading_thumbs = True

        if self.v_path.get() and os.path.exists(self.v_path.get()):
            self._load_video_info(self.v_path.get())
        else:
            self._update_derived()

        # Chargement des images en dernier, après que l'UI est stable
        if self.v_outdir.get() and os.path.isdir(self.v_outdir.get()):
            self.after(300, self._reload_extraction_folder)
        else:
            # Pas d'images à charger : on libère le flag immédiatement
            self._loading_thumbs = False

        self._scrollbar_hide_jobs = {}

    def _update_refresh_btn_state(self):
        if not hasattr(self, '_refresh_btn'):
            return
        outdir = self.v_outdir.get()
        state = "normal" if outdir and os.path.isdir(outdir) else "disabled"
        self._refresh_btn.set_state(state)


    # ── Sashes ────────────────────────────────────────────────────────────────
    def _restore_sashes(self):
        try:
            self._pane.sash_place(0,int(self._cfg.get("sash_left",310)),0)
            self._pane.sash_place(1,int(self._cfg.get("sash_right",700)),0)
        except Exception: pass

    def _get_sash_positions(self):
        try: return int(self._pane.sash_coord(0)[0]),int(self._pane.sash_coord(1)[0])
        except Exception: return 310,700

    def _apply_window_size(self,size):
        self.update_idletasks()
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight()
        if size=="auto":
            w=min(int(sw*0.90)//10*10,1920); h=min(int(sh*0.90)//10*10,1200)
        else:
            try: w,h=map(int,size.split("x"))
            except ValueError: w,h=1280,800
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _apply_initial_geometry(self):
        col_count    = int(self._cfg.get("col_count",   4))
        thumb_size   = int(self._cfg.get("thumb_size",  150))
        preview_size = int(self._cfg.get("preview_size", 280))
        sash_left    = int(self._cfg.get("sash_left",   310))
        sash_right   = int(self._cfg.get("sash_right",  700))

        center_need = col_count * (thumb_size + 22) + 26
        right_need  = preview_size + 36

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        win_w = min(sash_left + center_need + right_need + 14, sw - 40)

        win_h = int(self._cfg.get("window_h", 1080))
        win_h = max(560, win_h)
        win_h = min(win_h, max(560, sh - 40))

        cx = max(0, (sw - win_w) // 2)
        cy = max(0, (sh - win_h) // 2)

        self.geometry(f"{win_w}x{win_h}+{cx}+{cy}")

        def _place_sashes():
            try:
                self._pane.sash_place(0, sash_left, 0)
                self._pane.sash_place(1, sash_right, 0)
            except Exception:
                pass

        self.after(50,  _place_sashes)
        self.after(150, _place_sashes)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._pane=tk.PanedWindow(self,orient="horizontal",bg=C["bg"],
                                  sashwidth=5,sashrelief="flat",opaqueresize=True)
        self._pane.pack(fill="both",expand=True)

        self._lf=tk.Frame(self._pane,bg=C["bg"])
        self._cf=tk.Frame(self._pane,bg=C["bg"])
        self._rf=tk.Frame(self._pane,bg=C["bg"])
        self._pane.add(self._lf,minsize=LEFT_MIN_W,sticky="nsew")
        self._pane.add(self._cf,minsize=300,sticky="nsew")
        self._pane.add(self._rf,minsize=180,sticky="nsew")

        self._build_left(); self._build_center(); self._build_right()

        # v4.7 (chantier 8) : branchement de la grille virtualisée.
        if GRID_VIRTUAL:
            self._vg = VirtualThumbGrid(self._cv, self)
            self._center_scrollbar.command = self._vg_yview
            self._cv.bind("<Configure>", lambda e: self._vg.refresh(), add="+")
            self._cv.bind("<MouseWheel>", lambda e: self._vg.refresh(), add="+")
            self._cv.bind("<Button-4>", lambda e: self._vg.refresh(), add="+")
            self._cv.bind("<Button-5>", lambda e: self._vg.refresh(), add="+")
            self._cv.bind("<Button-1>", self._vg_on_click, add="+")
            try:
                self._cv.itemconfigure(self._gwin, state="hidden")
            except Exception:
                pass

        self._statusbar=tk.Label(self,text="",font=F_SMALL,fg=C["t3"],
                                 bg=C["panel"],anchor="w",padx=12,pady=4)
        self._statusbar.pack(side="bottom",fill="x")

    def _build_left(self):
        p=self._lf; p.rowconfigure(1,weight=1); p.columnconfigure(0,weight=1)
        hdr=tk.Frame(p,bg=C["bg"])
        hdr.grid(row=0,column=0,sticky="ew",padx=14,pady=(14,4))
        tk.Label(hdr,text="Frame",font=("Segoe UI Light",20),
                 fg=C["t2"],bg=C["bg"]).pack(side="left")
        tk.Label(hdr,text="Extractor",font=("Segoe UI Semibold",20),
                 fg=C["accent"],bg=C["bg"]).pack(side="left",padx=(4,0))
        tk.Label(hdr,text=" v4.0",font=("Segoe UI",9),
                 fg=C["t3"],bg=C["bg"]).pack(side="left",anchor="s",pady=(0,2))

        sc_frame = tk.Frame(p, bg=C["bg"])
        sc_frame.grid(row=1, column=0, sticky="nsew")
        sc_frame.rowconfigure(0, weight=1)
        sc_frame.columnconfigure(0, weight=1)
        sc_frame.columnconfigure(1, weight=0)

        sc = tk.Canvas(sc_frame, bg=C["bg"], highlightthickness=0)
        self._left_canvas = sc
        sc.grid(row=0, column=0, sticky="nsew")

        self._left_scrollbar = ModernScrollbar(sc_frame, command=sc.yview)
        self._left_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2))
        # Pas de grid_remove() — la colonne reste toujours présente

        sc.configure(yscrollcommand=self._left_scrollbar.set)

        inner = tk.Frame(sc, bg=C["bg"])
        win_id = sc.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(0, weight=1)
        inner.bind("<Configure>", lambda e: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>", lambda e: sc.itemconfig(win_id, width=e.width))
        sc.bind("<MouseWheel>", lambda e: sc.yview_scroll(-int(e.delta / 120), "units"))
        sc.bind("<Button-4>",   lambda e: sc.yview_scroll(-1, "units"))
        sc.bind("<Button-5>",   lambda e: sc.yview_scroll(1, "units"))

        # Auto-hide : apparaît au survol, disparaît après 500 ms
        # sc.bind("<Enter>",                lambda e: self._show_scrollbar_grid(self._left_scrollbar))
        # sc.bind("<Leave>",                lambda e: self._hide_scrollbar_grid_later(self._left_scrollbar))
        # self._left_scrollbar.bind("<Enter>",  lambda e: self._show_scrollbar_grid(self._left_scrollbar))
        # self._left_scrollbar.bind("<Leave>",  lambda e: self._hide_scrollbar_grid_later(self._left_scrollbar))


        self._build_left_content(inner)

        footer=tk.Frame(p,bg=C["bg"])
        footer.grid(row=2,column=0,sticky="ew"); footer.columnconfigure(0,weight=1)
        HSep(footer).grid(row=0,column=0,sticky="ew")
        DarkButton(footer,"💾  Sauvegarder la configuration",self._save_config_action,
                   style="ghost",width=0,height=32,font=F_SMALL).grid(row=1,column=0,sticky="ew",padx=14,pady=8)

    def _build_info_block(self, inner, PAD):
        """Remplace la construction du bloc d'infos dans _build_left_content."""
        
        # Conteneur externe — juste pour le padding et la bordure simulée
        outer = tk.Frame(inner, bg=C["border"], padx=1, pady=1)
        outer.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(0, 6))
        outer.columnconfigure(0, weight=1)

        # Ligne brillante du haut (1px, couleur claire)
        top_line = tk.Frame(outer, bg=C["t2"], height=1)
        top_line.grid(row=0, column=0, sticky="ew")

        # Corps du bloc
        self.info_content = tk.Frame(outer, bg=C["info_bg"], padx=10, pady=6)
        self.info_content.grid(row=1, column=0, sticky="ew")
        self.info_content.columnconfigure(0, weight=1)

        # Indicateur FFMPEG (bouton carré)
        ff_frame = tk.Frame(self.info_content, bg=C["info_bg"])
        ff_frame.grid(row=0, column=0, sticky="ew", pady=4)

        self._ffmpeg_indicator = tk.Label(
            ff_frame,
            text="FFMPEG",
            font=F_BOLD,
            bg=C["panel2"],      # gris éteint par défaut
            fg=C["t3"],
            relief="ridge",
            bd=1,
            padx=8,
            pady=2,
            width=10,
            anchor="center"
        )
        self._ffmpeg_indicator.pack(side="left")

        self._ffmpeg_label = tk.Label(
            ff_frame,
            text="",
            font=F_SMALL,
            fg=C["t3"],
            bg=C["info_bg"],
            anchor="w"
        )
        self._ffmpeg_label.pack(side="left", padx=(8, 0))

        # Appliquer l'état en fonction de la disponibilité de ffmpeg
        if self._ffmpeg_ok:
            self._ffmpeg_indicator.config(bg=C["ok"], fg="black", relief="raised")
            self._ffmpeg_label.config(text="Couleurs fidèles", fg=C["ok"])
        else:
            self._ffmpeg_indicator.config(bg=C["panel2"], fg=C["t3"], relief="ridge")
            self._ffmpeg_label.config(
                text="ffmpeg absent — couleurs approximatives. Installez ffmpeg !",
                fg=C["danger"],
                wraplength=260
            )

        # Indicateur HDR10 (bouton carré)
        hdr_frame = tk.Frame(self.info_content, bg=C["info_bg"])
        hdr_frame.grid(row=1, column=0, sticky="ew", pady=4)
        self._hdr10_indicator = tk.Label(
            hdr_frame,
            text="HDR10 PQ",
            font=F_BOLD,
            bg=C["panel2"],
            fg=C["t3"],
            relief="ridge",
            bd=1,
            padx=8,
            pady=2,
            width=10,
            anchor="center"
        )
        self._hdr10_indicator.pack(side="left")

        # Label texte d'information complémentaire
        self._hdr_info_label = tk.Label(
            hdr_frame,
            text="SDR — espace standard",
            font=F_SMALL,
            fg=C["t3"],
            bg=C["info_bg"],
            anchor="w"
        )
        self._hdr_info_label.pack(side="left", padx=(8, 0))

        # Sélecteur tone mapping (caché par défaut)
        self._hdr_tonemap_frame = tk.Frame(self.info_content, bg=C["info_bg"])
        self._hdr_tonemap_frame.columnconfigure(0, weight=1)

        tk.Label(self._hdr_tonemap_frame, text="Tone mapping HDR→SDR :",
                font=F_SMALL, fg="#ffd54f", bg=C["info_bg"], anchor="w", padx=4
                ).grid(row=0, column=0, sticky="w", pady=(4, 2))

        tm_row = tk.Frame(self._hdr_tonemap_frame, bg=C["info_bg"])
        tm_row.grid(row=1, column=0, sticky="w", padx=4, pady=(0, 6))

        for algo, label, tip in [("hable",   "Hable",   "Doux, cinématique — recommandé"),
                                ("mobius",  "Mobius",  "Équilibré, préserve les couleurs"),
                                ("reinhard","Reinhard","Simple et rapide")]:
            rb = tk.Radiobutton(tm_row, text=label, variable=self.v_hdr_tonemap,
                                value=algo, bg=C["info_bg"], fg="#ffd54f",
                                selectcolor=C["accent_bg"], activebackground=C["info_bg"],
                                activeforeground="#fff", font=F_SMALL, cursor="hand2")
            rb.pack(side="left", padx=(0, 8))
            Tooltip(rb, lambda t=tip: t)

        tk.Label(self._hdr_tonemap_frame,
                text="  ℹ  Requiert ffmpeg avec libzimg (zscale).\n"
                    "  Fallback automatique si non disponible.",
                font=("Segoe UI", 8), fg="#a09060", bg=C["info_bg"],
                anchor="w", padx=4, justify="left"
                ).grid(row=2, column=0, sticky="w", pady=(0, 2))

        # Caché au démarrage
        # (grid utilisé à la place de pack pour _hdr_tonemap_frame)

    def _build_left_content(self, inner):
        PAD=12; row=0

        # ← REMPLACE tout l'ancien bloc canvas par ceci :
        self._build_info_block(inner, PAD)
        row += 1

        # Source
        row=self._sect(inner,row,"Fichier source")
        f=tk.Frame(inner,bg=C["bg"]); f.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,4))
        f.columnconfigure(0,weight=1); row+=1

        # Bouton unique : affiche le nom du fichier ou "Parcourir"
        self._src_btn = DarkButton(
            f,
            text="Parcourir",
            command=self._pick_video,
            style="default",
            height=32,
            font=F_UI,
            anchor="w",
            padx=10,
            fg=C["accent"]
        )
        self._src_btn.grid(row=0, column=0, sticky="ew", ipady=2)

        # Liaison du tooltip — src seulement ici
        self._src_btn.bind("<Enter>", lambda e: self._show_full_tooltip(self._src_btn, self.v_path.get()), add="+")
        self._src_btn.bind("<Leave>", lambda e: self._hide_tooltip(), add="+")

        # Mise à jour du texte du bouton quand v_path change
        def update_src_btn(*args):
            path = self.v_path.get()
            if path and os.path.exists(path):
                self._src_btn.set_text(os.path.basename(path))
            else:
                self._src_btn.set_text("Parcourir")
        self.v_path.trace_add("write", update_src_btn)
        update_src_btn()

        self._src_name_lbl = None

        self._info_lbl=tk.Label(inner,text="Aucun fichier chargé",font=F_MONO,
                                fg=C["t2"],bg=C["panel"],justify="left",
                                anchor="w",padx=10,pady=8)
        self._info_lbl.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(0,6)); row+=1



        # Dossier d'Extraction
        row=self._sect(inner,row,"Dossier d'Extraction")
        f2=tk.Frame(inner,bg=C["bg"]); f2.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6))
        f2.columnconfigure(0,weight=1); row+=1

        self._outdir_btn = DarkButton(
            f2,
            text="Parcourir",
            command=self._pick_output,
            style="default",
            width=0,
            height=32,
            font=F_UI,
            anchor="w",
            padx=10,
            fg=C["accent"]
        )
        self._outdir_btn.grid(row=0, column=0, sticky="ew", ipady=2)

        # Mise à jour du texte du bouton en fonction de v_outdir
        def update_outdir_btn(*args):
            path = self.v_outdir.get()
            if path and os.path.isdir(path):
                self._outdir_btn.set_text(os.path.basename(path.rstrip("/\\")))
            else:
                self._outdir_btn.set_text("Parcourir")
        self.v_outdir.trace_add("write", update_outdir_btn)
        update_outdir_btn()

        # Tooltip instantané sur le bouton (chemin complet)
        self._outdir_btn.bind("<Enter>", lambda e: self._show_full_tooltip(self._outdir_btn, self.v_outdir.get()), add="+")
        self._outdir_btn.bind("<Leave>", lambda e: self._hide_tooltip(), add="+")

        # On supprime l'ancien label self._outdir_name_lbl (optionnel)
        self._outdir_name_lbl = None


        # Dossier Travail
        row=self._sect(inner,row,"Dossier de Travail")
        f3=tk.Frame(inner,bg=C["bg"]); f3.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6))
        f3.columnconfigure(0,weight=1); row+=1

        self._workdir_btn = DarkButton(
            f3,
            text="Parcourir",
            command=self._pick_workdir,
            style="default",
            width=0,
            height=32,
            font=F_UI,
            anchor="w",
            padx=10,
            fg=C["accent"]
        )
        self._workdir_btn.grid(row=0, column=0, sticky="ew", ipady=2)

        def update_workdir_btn(*args):
            p = self.v_workdir.get()
            if p and os.path.isdir(p):
                self._workdir_btn.set_text(os.path.basename(p.rstrip("/\\")))
            else:
                self._workdir_btn.set_text("Parcourir")
        self.v_workdir.trace_add("write", update_workdir_btn)
        update_workdir_btn()

        self._workdir_btn.bind("<Enter>", lambda e: self._show_full_tooltip(self._workdir_btn, self.v_workdir.get()), add="+")
        self._workdir_btn.bind("<Leave>", lambda e: self._hide_tooltip(), add="+")

        self._workdir_name_lbl = None

        # Nom générique (déplacé ici, sous le dossier de travail)
        row=self._sect(inner,row,"Renommer les fichiers à déplacer")
        nm=tk.Frame(inner,bg=C["bg"]); nm.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,4))
        nm.columnconfigure(0,weight=1); row+=1
        DarkEntry(nm,textvariable=self.v_generic).grid(row=0,column=0,sticky="ew",ipady=5,padx=(0,6))
        tk.Label(nm,text="_0001.jpg",font=F_SMALL,fg=C["t3"],bg=C["bg"]
                 ).grid(row=0,column=1,sticky="w")

        self._copy_btn=DarkButton(inner,"📋  Déplacer sélection → Dossier de Travail",
                                self._move_to_workdir,style="accent",
                                width=0,height=30,font=F_SMALL,bg=C["bg"])
        self._copy_btn.grid(row=row,column=0,pady=(4,4),padx=PAD,sticky="ew")
        self._copy_btn.set_state("disabled"); row+=1



        # Mode capture
        row=self._sect(inner,row,"Mode de capture")
        self._pill=PillSelector(inner,[("Nombre d'images","count"),("Intervalle (s)","interval")],
                                self.v_mode,command=self._on_mode_change,bg=C["bg"])
        self._pill.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6)); row+=1
        self._sl_count=DarkSlider(inner,from_=5,to=500,resolution=5,variable=self.v_count,
                                  label="Nombre d'images",unit="images",
                                  command=self._on_slider_change,bg=C["bg"])
        self._sl_count.grid(row=row,column=0,sticky="ew",padx=PAD+4,pady=(0,6)); row+=1
        self._sl_intv=DarkSlider(inner,from_=5,to=1800,resolution=5,variable=self.v_intv,
                                 label="Intervalle entre captures",unit="s",
                                 command=self._on_slider_change,bg=C["bg"])
        self._sl_intv.grid(row=row,column=0,sticky="ew",padx=PAD+4,pady=(0,6)); row+=1
        self._on_mode_change()

        bf=tk.Frame(inner,bg=C["bg"]); bf.grid(row=row,column=0,sticky="w",padx=PAD,pady=(4,0)); row+=1
        tk.Checkbutton(bf,text="Supprimer les frames noires (luminosité < 5/255)",
                       variable=self.v_black_filter,bg=C["bg"],fg=C["t2"],
                       selectcolor=C["input"],activebackground=C["bg"],
                       activeforeground=C["t1"],font=F_SMALL,anchor="w",
                       cursor="hand2").pack(side="left")
        
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Taille fenêtre
        row=self._sect(inner,row,"Taille de la fenêtre")
        wf=tk.Frame(inner,bg=C["bg"]); wf.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,10)); row+=1
        wf.columnconfigure(1,weight=1)   # v4.6 : la colonne du bouton absorbe l'espace restant
        self._v_winsize_var=tk.StringVar(value=self.v_winsize.get())
        _saved_ws=self.v_winsize.get()
        _winsize_list=WINDOW_SIZES if _saved_ws in WINDOW_SIZES else WINDOW_SIZES+[_saved_ws]
        self._winsize_combo=RoundedCombo(wf,_winsize_list,self._v_winsize_var,width=120,bg=C["bg"])
        self._winsize_combo.grid(row=0,column=0,sticky="w")
        DarkButton(wf,"Appliquer",
                   lambda:(self.v_winsize.set(self._v_winsize_var.get()),
                           self._apply_window_size(self._v_winsize_var.get())),
                   width=0,height=28).grid(row=0,column=1,sticky="ew",padx=(8,0))
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Actions
        row=self._sect(inner,row,"Actions")
        act=tk.Frame(inner,bg=C["bg"]); act.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(4,4)); row+=1
        act.columnconfigure(0,weight=1); act.columnconfigure(1,weight=1)   # v4.6 : les 2 colonnes absorbent l'espace
        GAP=6
        self._run_btn=DarkButton(act,"▶  Extraire les frames",self._start_extraction,
                                 style="accent",width=0,height=36,font=F_BOLD)
        self._run_btn.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,5))
        self._cancel_btn=DarkButton(act,"✕  Annuler",self._cancel_extraction,
                                   style="ghost",width=0,height=30)
        self._cancel_btn.grid(row=1,column=0,sticky="ew",padx=(0,GAP)); self._cancel_btn.set_state("disabled")
        self._del_btn=DarkButton(act,"🗑  Supprimer",self._delete_selected,
                                 style="danger",width=0,height=30)
        self._del_btn.grid(row=1,column=1,sticky="ew"); self._del_btn.set_state("disabled")
        DarkButton(act,"🗂  Vider le dossier d'extraction",self._clear_output_dir,
                   style="danger",width=0,height=30).grid(row=2,column=0,columnspan=2,sticky="ew",pady=(5,0))

        chk=tk.Frame(inner,bg=C["bg"]); chk.grid(row=row,column=0,sticky="w",padx=PAD,pady=(6,0)); row+=1
        tk.Checkbutton(chk,text="Demander confirmation avant suppression",
                       variable=self.v_confirm_del,bg=C["bg"],fg=C["t2"],
                       selectcolor=C["input"],activebackground=C["bg"],
                       activeforeground=C["t1"],font=F_SMALL,anchor="w",
                       cursor="hand2").pack(side="left")
        self._prog=DarkProgress(inner,height=4,bg=C["bg"])
        self._prog.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(8,2)); row+=1
        self._prog_lbl=tk.Label(inner,text="",font=F_SMALL,fg=C["t3"],
                                bg=C["bg"],anchor="w")
        self._prog_lbl.grid(row=row,column=0,sticky="ew",padx=PAD+2,pady=(0,14)); row+=1

    def _sect(self,parent,row,text):
        SectLabel(parent,text).grid(row=row,column=0,sticky="ew",padx=14,pady=(10,3))
        return row+1

    def _build_center(self):
        c=self._cf; c.rowconfigure(2,weight=1); c.columnconfigure(0,weight=1)
        hdr=tk.Frame(c,bg=C["panel"]); hdr.grid(row=0,column=0,sticky="new")
        hdr.columnconfigure(1,weight=1)
        tk.Label(hdr,text="Vignettes",font=F_TITLE,fg=C["t1"],
                 bg=C["panel"],padx=14).grid(row=0,column=0,sticky="w")
        self._badge_total=tk.Label(hdr,text="0 image(s)",font=F_SMALL,
                                   fg=C["t3"],bg=C["panel"],padx=8)
        self._badge_total.grid(row=0,column=1,sticky="e")
        self._badge_sel=tk.Label(hdr,text="",font=F_SMALL,fg=C["accent"],
                                 bg=C["panel"],padx=8)
        self._badge_sel.grid(row=0,column=2,sticky="e")

        mtb=tk.Frame(c,bg=C["panel2"],pady=3); mtb.grid(row=1,column=0,sticky="ew")
        self._badge_marked=tk.Label(mtb,text="",font=F_SMALL,fg=C["ok"],
                                    bg=C["panel2"],padx=8)
        self._badge_marked.pack(side="left")
        DarkButton(mtb,"✕  Tout démarquer",self._unmark_all,
                   style="ghost",width=120,height=24,font=F_SMALL).pack(side="left",padx=(4,4))
        DarkButton(mtb,"✔  Marquer",self._mark_selection,
                   style="ghost",width=90,height=24,font=F_SMALL).pack(side="left",padx=(0,10))
        tk.Frame(mtb,bg=C["border"],width=1).pack(side="left",fill="y",pady=2)
        tk.Label(mtb,text="  Marquer :",font=F_SMALL,fg=C["t3"],
                 bg=C["panel2"]).pack(side="left")
        self._mark_key_entry=DarkEntry(mtb,textvariable=self.v_mark_key,
                                       width=3,font=F_BOLD,justify="center")
        self._mark_key_entry.pack(side="left",padx=(4,0),ipady=2)
        tk.Label(mtb,text="  (raccourci)",font=F_SMALL,fg=C["t3"],
                 bg=C["panel2"]).pack(side="left")
        tk.Frame(mtb,bg=C["border"],width=1).pack(side="left",fill="y",pady=2,padx=(8,0))
        tk.Label(mtb,text="  Vignettes :",font=F_SMALL,fg=C["t3"],
                 bg=C["panel2"]).pack(side="left")
        self._v_tsize_var=tk.StringVar(value=str(self.v_tsize.get()))
        RoundedCombo(mtb,["100","150","200","250","300"],self._v_tsize_var,
                     width=68,bg=C["panel2"]).pack(side="left",padx=(4,0))
        tk.Label(mtb,text="px",font=F_SMALL,fg=C["t3"],
                 bg=C["panel2"]).pack(side="left",padx=(3,0))
        self._v_tsize_var.trace_add("write",self._on_tsize_change)
        tk.Label(mtb,text="  Colonnes :",font=F_SMALL,fg=C["t3"],
                 bg=C["panel2"]).pack(side="left",padx=(8,0))
        self._v_cols_var=tk.StringVar(value=str(self.v_cols.get()))
        RoundedCombo(mtb,["3","4","5","6"],self._v_cols_var,
                     width=50,bg=C["panel2"]).pack(side="left",padx=(4,8))
        
        self._v_cols_var.trace_add("write",self._on_cols_change)
        self.v_mark_key.trace_add("write",lambda *a: self._rebind_mark_key())

        # Bouton Rafraîchir le dossier d'extraction
        tk.Frame(mtb, bg=C["border"], width=1).pack(side="left", fill="y", pady=2, padx=(8, 0))
        self._refresh_btn = DarkButton(
            mtb,
            "🔄 Rafraîchir",
            self._refresh_folder,
            style="ghost",
            width=110,
            height=24,
            font=F_SMALL
        )
        self._refresh_btn.pack(side="right", padx=(8, 8))

        cf2=tk.Frame(c,bg=C["thumb_bg"]); cf2.grid(row=2,column=0,sticky="nsew")
        cf2.rowconfigure(0,weight=1); cf2.columnconfigure(0,weight=1)
        self._cv=tk.Canvas(cf2,bg=C["thumb_bg"],highlightthickness=0)
        self._cv.grid(row=0,column=0,sticky="nsew")

        cf2.columnconfigure(1, weight=0)

        self._center_scrollbar = ModernScrollbar(cf2, command=self._cv.yview)
        self._center_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2))
        # Pas de grid_remove()

        self._cv.configure(yscrollcommand=self._center_scrollbar.set)

        # self._cv.bind("<Enter>",                    lambda e: self._show_scrollbar_grid(self._center_scrollbar))
        # self._cv.bind("<Leave>",                    lambda e: self._hide_scrollbar_grid_later(self._center_scrollbar))
        # self._center_scrollbar.bind("<Enter>",      lambda e: self._show_scrollbar_grid(self._center_scrollbar))
        # self._center_scrollbar.bind("<Leave>",      lambda e: self._hide_scrollbar_grid_later(self._center_scrollbar))


        self._gf=tk.Frame(self._cv,bg=C["thumb_bg"],padx=6,pady=8)
        self._gwin=self._cv.create_window((0,0),window=self._gf,anchor="nw")
        self._gf.bind("<Configure>",self._on_grid_configure)
        self._cv.bind("<Configure>",lambda e: self._cv.itemconfig(self._gwin,width=e.width))
        self._cv.bind("<MouseWheel>",self._scroll)
        self._cv.bind("<Button-4>",  self._scroll)
        self._cv.bind("<Button-5>",  self._scroll)
        self._cv.bind("<Button-1>",  lambda e: self.focus_set(),add="+")
        for widget in (self._cv,self._gf):
            widget.bind("<ButtonPress-1>",  self._drag_start)
            widget.bind("<B1-Motion>",      self._drag_motion)
            widget.bind("<ButtonRelease-1>",self._drag_end)

    def _vg_yview(self, *args):
        self._cv.yview(*args)
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    def _vg_on_click(self, event):
        if getattr(self, "_vg", None) is None:
            return

        self.focus_set()

        x = self._cv.canvasx(event.x)
        y = self._cv.canvasy(event.y)

        ids = self._cv.find_overlapping(x, y, x, y)
        path = None

        for iid in reversed(ids):
            for tag in self._cv.gettags(iid):
                if tag.startswith("vt::"):
                    path = tag[4:]
                    break
            if path:
                break

        SHIFT_MASK = 0x0001
        CTRL_MASK  = 0x0004

        if path and path in self.thumb_by_path:
            if event.state & CTRL_MASK:
                self._ctrl_click(path)
            elif event.state & SHIFT_MASK:
                self._shift_click(path)
            else:
                self._click(path)
        else:
            if not (event.state & CTRL_MASK) and not (event.state & SHIFT_MASK):
                if self.sel:
                    self._clear_selection()
                    self._upd_badges()
                    self._prev_info.config(text="Cliquez sur une\nvignette…")

        return "break"

    def _on_info_canvas_configure(self, event):
        """Le canvas change de taille → on ajuste la largeur du contenu et on redessine le fond."""
        w = event.width
        self.info_canvas.itemconfig("content", width=w)   # force la largeur du contenu
        self._draw_info_block_bg()

    def _on_info_content_configure(self, event):
        self.info_content.update_idletasks()
        h = self.info_content.winfo_reqheight()
        self.info_canvas.configure(height=h)
        self._draw_info_block_bg()

    def _draw_info_block_bg(self):
        cv = self.info_canvas
        cv.delete("bg")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 4 or h < 4:
            return
        r = 10
        # Fond arrondi
        pts = [r,0, w-r,0, w,0, w,r, w,h-r, w,h,
            w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
        cv.create_polygon(pts, smooth=True, fill=C["info_bg"], outline="", tags="bg")

        # Bordure brillante — coins haut-gauche et haut-droit
        cv.create_arc(0, 0, 2*r, 2*r,
                    start=90, extent=90,          # ← haut-gauche ✓
                    style="arc", outline=C["t1"], width=1, tags="bg")
        cv.create_arc(w-2*r, 0, w, 2*r,
                    start=0, extent=90,           # ← haut-droit ✓
                    style="arc", outline=C["t1"], width=1, tags="bg")
        # Segment horizontal qui relie les deux arcs
        cv.create_line(r, 0, w-r, 0,
                    fill=C["t1"], width=1, tags="bg")

    def _build_right(self):
        r=self._rf; r.rowconfigure(1,weight=1); r.columnconfigure(0,weight=1)
        hdr=tk.Frame(r,bg=C["panel"],height=38); hdr.grid(row=0,column=0,sticky="ew")
        hdr.grid_propagate(False)
        tk.Label(hdr,text="Aperçu",font=F_TITLE,fg=C["t1"],
                 bg=C["panel"],padx=14).pack(side="left",fill="y")
        self._prev_frame=tk.Frame(r,bg=C["thumb_bg"]); self._prev_frame.grid(row=1,column=0,sticky="nsew")
        self._prev_frame.columnconfigure(0,weight=1); self._prev_frame.rowconfigure(0,weight=1)
        self._prev_lbl=tk.Label(self._prev_frame,bg=C["thumb_bg"],anchor="center",padx=12,pady=0)
        self._prev_lbl.grid(row=0,column=0,sticky="new",padx=12,pady=(12,12))
        HSep(r).grid(row=2,column=0,sticky="ew",padx=8)
        self._prev_info=tk.Label(r,text="Cliquez sur une\nvignette…",font=F_SMALL,
                                 fg=C["t3"],bg=C["bg"],justify="left",padx=14,pady=8)
        self._prev_info.grid(row=3,column=0,sticky="w")
        HSep(r).grid(row=4,column=0,sticky="ew",padx=8)
        pf=tk.Frame(r,bg=C["bg"]); pf.grid(row=5,column=0,sticky="ew",padx=12,pady=(6,10))
        tk.Label(pf,text="Taille :",font=F_SMALL,fg=C["t3"],bg=C["bg"]).pack(side="left")
        self._v_psize_var=tk.StringVar(value=str(self.v_psize.get()))
        RoundedCombo(pf,["150","200","250","300","350","400","450","500","550","600","650"],
                     self._v_psize_var,width=80,bg=C["bg"]).pack(side="left",padx=(8,0))
        tk.Label(pf,text="px",font=F_SMALL,fg=C["t3"],bg=C["bg"]).pack(side="left",padx=(5,0))
        self._v_psize_var.trace_add("write",self._on_psize_change)

    # ── Bind ──────────────────────────────────────────────────────────────────
    def _bind_events(self):
        self.bind("<Delete>",    lambda e: self._delete_selected())
        self.bind("<BackSpace>", lambda e: self._delete_selected())
        self.bind_all("<MouseWheel>",self._scroll_universal)
        self.bind_all("<Button-4>",  self._scroll_universal)
        self.bind_all("<Button-5>",  self._scroll_universal)
        self._mark_binding_id=None; self._rebind_mark_key()
        self.bind_all("<ButtonPress-1>",self._global_click_deselect,add="+")
        self.bind("<Left>",  self._on_arrow_key)
        self.bind("<Right>", self._on_arrow_key)
        self.bind("<Up>",    self._on_arrow_key)
        self.bind("<Down>",  self._on_arrow_key)
        

    # def _on_window_configure(self, event):
    #     if not self._geometry_ready:
    #         return
    #     if event.widget is self and event.height > 100:
    #         self._cfg["window_h"] = event.height

    # def _on_window_configure(self, event):
    #     if event.widget is self and event.height > 100:
    #         import time
    #         ready = getattr(self, '_geometry_ready', False)
    #         print(f"[CONFIGURE] h={event.height}  ready={ready}  t={time.time():.3f}")
    #         if ready:
    #             self._cfg["window_h"] = event.height

    def _on_window_configure(self, event):
        pass

    def _on_close(self):
        self._cfg["window_h"] = self.winfo_height()
        self._cancel = True          # v4.5 : interrompt l'extraction en cours → sortie propre
        self._auto_save_config()
        self.destroy()

    def _on_arrow_key(self, event):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, DarkEntry)):
            return
        if not self.thumbs:
            return
        cols = self.v_cols.get()
        total = len(self.thumbs)
        order = [e["path"] for e in self.thumbs]
        # Déterminer la position de départ
        if len(self.sel) == 1:
            current = self._position_of(next(iter(self.sel)))
        elif not self.sel:
            current = -1
        else:
            anchor = self._last_click_path
            current = self._position_of(anchor) if anchor else min(self._position_of(p) for p in self.sel)
        if current < 0:
            current = -1
        # Calculer la nouvelle position
        if event.keysym == "Right":  new = current + 1
        elif event.keysym == "Left": new = current - 1
        elif event.keysym == "Down": new = current + cols
        elif event.keysym == "Up":   new = current - cols
        else: return
        new = max(0, min(new, total - 1))
        if new == current:
            return
        new_path = order[new]
        self._clear_selection()
        self.sel.add(new_path)
        self._set_sel(new_path, True)
        self._last_click_path = new_path
        self._upd_badges()
        self._show_preview(new_path)
        self._scroll_to_thumb(new_path)

    def _scroll_to_thumb(self, path):
        """Fait défiler le canvas central pour que la vignette path soit visible."""
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.scroll_to_path(path)
            return

        if path not in self.thumb_wids:
            return

        cell = self.thumb_wids[path]["frame"]

        try:
            self._cv.update_idletasks()
            total_h = self._cv.bbox("all")[3]
            if not total_h:
                return

            cell_top    = cell.winfo_rooty() - self._cv.winfo_rooty() + self._cv.canvasy(0)
            cell_bottom = cell_top + cell.winfo_height()
            canvas_h    = self._cv.winfo_height()
            scroll_top  = self._cv.canvasy(0)
            scroll_bot  = scroll_top + canvas_h

            if cell_top < scroll_top:
                self._cv.yview_moveto(cell_top / total_h)
            elif cell_bottom > scroll_bot:
                self._cv.yview_moveto((cell_bottom - canvas_h) / total_h)
        except Exception:
            pass

    def _global_click_deselect(self,event):
        """v4.6 : désélectionne si le clic est hors de toute vignette.
        Optimisé : on remonte la hiérarchie du widget cliqué (0 appel Tcl de
        géométrie) au lieu de tester les 4 coordonnées de chaque vignette."""
        if not self.sel: return
        w=event.widget
        KEEP=(tk.Entry,DarkEntry,DarkButton,tk.Scale,tk.Checkbutton,
              ttk.Scrollbar,tk.Scrollbar,tk.Menu,PillSelector,RoundedCombo)
        if isinstance(w,KEEP): return
        # v4.6 : le clic est-il dans une vignette ? Chaque cellule/label de
        # vignette porte un attribut _path (chantier n°1) : on remonte les
        # parents jusqu'à le trouver (3-5 itérations Python, aucun winfo_*).
        cur=w
        while cur is not None:
            if getattr(cur,"_path",None) is not None:
                return
            cur=getattr(cur,"master",None)
        self._clear_selection()
        self._upd_badges()
        self._prev_info.config(text="Cliquez sur une\nvignette…")

    def _rebind_mark_key(self):
        if self._mark_binding_id:
            try: self.unbind(self._mark_binding_id[0],self._mark_binding_id[1])
            except Exception: pass
        key=self.v_mark_key.get().strip()
        if not key: return
        bid=self.bind(f"<KeyPress-{key}>",self._on_mark_key,add=True)
        self._mark_binding_id=(f"<KeyPress-{key}>",bid)

    def _show_full_tooltip(self, widget, text):
        """Affiche un tooltip immédiat avec le texte complet, fond gris, coins arrondis."""
        if not text:
            return
        # Supprimer l'ancien tooltip s'il existe
        if hasattr(self, '_tooltip_win') and self._tooltip_win:
            self._tooltip_win.destroy()
        # Créer une fenêtre Toplevel
        win = tk.Toplevel(widget)
        win.wm_overrideredirect(True)   # pas de bordure de fenêtre
        win.wm_attributes("-topmost", True)
        # Fond gris
        bg_color = C["panel2"]   # gris foncé
        fg_color = C["t1"]       # texte clair
        # Conception avec Canvas pour les coins arrondis
        pad = 8
        # Calculer la taille nécessaire
        temp_label = tk.Label(win, text=text, font=F_SMALL, bg=bg_color, fg=fg_color)
        temp_label.pack()
        win.update_idletasks()
        width = temp_label.winfo_reqwidth() + 2 * pad
        height = temp_label.winfo_reqheight() + 2 * pad
        temp_label.destroy()
        win.geometry(f"{width}x{height}")
        # Canvas arrondi
        canvas = tk.Canvas(win, width=width, height=height, highlightthickness=0, bg=bg_color)
        canvas.pack()
        r = 8
        # Dessiner un rectangle aux coins arrondis
        canvas.create_rounded_rect = lambda x1,y1,x2,y2,r,**kw: canvas.create_polygon(
            (x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
            x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1),
            smooth=True, **kw)
        canvas.create_rounded_rect(0, 0, width, height, r, fill=bg_color, outline="")
        # Ajouter le texte
        canvas.create_text(width//2, height//2, text=text, font=F_SMALL,
                        fill=fg_color, anchor="center")
        # Positionner sous la souris (légèrement décalé)
        x = widget.winfo_rootx() + 10
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        win.geometry(f"+{x}+{y}")
        self._tooltip_win = win

    def _hide_tooltip(self):
        """Détruit le tooltip."""
        if hasattr(self, '_tooltip_win') and self._tooltip_win:
            self._tooltip_win.destroy()
            self._tooltip_win = None

    def _scroll_universal(self, e):
        # Canvas central
        wx = self._cv.winfo_rootx()
        wy = self._cv.winfo_rooty()
        if wx <= e.x_root <= wx + self._cv.winfo_width() and wy <= e.y_root <= wy + self._cv.winfo_height():
            if e.num == 4:
                self._cv.yview_scroll(-1, "units")
            elif e.num == 5:
                self._cv.yview_scroll(1, "units")
            elif hasattr(e, "delta") and e.delta:
                self._cv.yview_scroll(-int(e.delta / 120), "units")
            return  # priorité au centre

        # Canvas gauche
        if hasattr(self, '_left_canvas') and self._left_canvas.winfo_exists():
            lx = self._left_canvas.winfo_rootx()
            ly = self._left_canvas.winfo_rooty()
            if lx <= e.x_root <= lx + self._left_canvas.winfo_width() and \
               ly <= e.y_root <= ly + self._left_canvas.winfo_height():
                if e.num == 4:
                    self._left_canvas.yview_scroll(-1, "units")
                elif e.num == 5:
                    self._left_canvas.yview_scroll(1, "units")
                elif hasattr(e, "delta") and e.delta:
                    self._left_canvas.yview_scroll(-int(e.delta / 120), "units")

    def _scroll(self,e):
        if e.num==4:   self._cv.yview_scroll(-1,"units")
        elif e.num==5: self._cv.yview_scroll(1,"units")
        elif hasattr(e,"delta") and e.delta: self._cv.yview_scroll(-int(e.delta/120),"units")

    # ── Mode / sliders ────────────────────────────────────────────────────────
    def _on_mode_change(self):
        m=self.v_mode.get()
        if m=="count": self._sl_count.grid(); self._sl_intv.grid_remove()
        else:          self._sl_count.grid_remove(); self._sl_intv.grid()
        self._update_derived()
        self._auto_save_config()

    def _on_slider_change(self,val=None):
        self._update_derived()
        self._auto_save_config()

    def _update_derived(self):
        dur=self.video_info.get("duration",0); n=self.v_count.get(); iv=self.v_intv.get()
        if self.v_mode.get()=="count":
            if dur and n>1: self._sl_count.set_info(f"≈ {hms(dur/(n-1))} entre chaque capture")
            elif dur and n==1: self._sl_count.set_info("1 seule image (début du film)")
            else: self._sl_count.set_info("")
        else:
            if dur and iv>0: self._sl_intv.set_info(f"→ {int(dur/iv)+1} photo(s) au total")
            else: self._sl_intv.set_info("")

    # ── Fichiers ──────────────────────────────────────────────────────────────
    def _pick_video(self):
        initial = self._cfg.get("last_video_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")   # dossier utilisateur par défaut
        p = filedialog.askopenfilename(
            title="Choisir une vidéo",
            filetypes=[("Vidéos","*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.m4v *.ts *.webm"),("Tous","*.*")],
            initialdir=initial
        )
        if p:
            self.v_path.set(p)
            self._cfg["last_video_dir"] = os.path.dirname(p)
            self._auto_save_config()
            self._load_video_info(p)

    def _pick_output(self):
        initial = self._cfg.get("last_output_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        p = filedialog.askdirectory(title="Dossier d'Extraction", initialdir=initial)
        if p:
            self.v_outdir.set(p)
            self._cfg["last_output_dir"] = p
            self._auto_save_config()

    def _pick_workdir(self):
        initial = self._cfg.get("last_work_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        p = filedialog.askdirectory(title="Dossier de Travail", initialdir=initial)
        if p:
            self.v_workdir.set(p)
            self._cfg["last_work_dir"] = p
            self._auto_save_config()

    def _load_video_info(self,path):
        cap=cv2.VideoCapture(path)
        if not cap.isOpened():
            messagebox.showerror("Erreur","Impossible d'ouvrir la vidéo.")
            self._info_lbl.config(text="❌  Fichier invalide"); return
        fps=cap.get(cv2.CAP_PROP_FPS) or 25
        fc=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        raw_w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        raw_h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur=fc/fps; cap.release()
        disp_w,disp_h=get_display_size(path,raw_w,raw_h)
        sar_applied=(disp_w!=raw_w)
        self.video_info={"fps":fps,"frames":fc,"width":raw_w,"height":raw_h,
                         "disp_w":disp_w,"disp_h":disp_h,"sar_applied":sar_applied,"duration":dur}
        mb=os.path.getsize(path)/1_048_576
        sar_note=f"\n  Affiché     {disp_w}×{disp_h} (SAR)" if sar_applied else ""
        self._info_lbl.config(
            text=f"  Durée       {hms(dur)}\n  Résolution  {raw_w}×{raw_h}{sar_note}\n"
                 f"  FPS         {fps:.2f}\n  Taille      {mb:.1f} Mo")
        self._update_derived()
        # Détection HDR en arrière-plan pour ne pas bloquer l'UI
        threading.Thread(target=self._detect_hdr_async, args=(path,), daemon=True).start()
        log.info("Vidéo chargée : %s | %s | %dx%d | %.2f fps",
                 os.path.basename(path), hms(dur), raw_w, raw_h, fps)        

    def _force_info_redraw(self):
        """Force un redimensionnement et redessine le fond du bloc d'infos."""
        self.info_content.update_idletasks()
        h = self.info_content.winfo_reqheight()
        self.info_canvas.configure(height=h)
        self._draw_info_block_bg()

    # ── HDR ───────────────────────────────────────────────────────────────────
    def _detect_hdr_async(self, path):
        """Lance detect_hdr() en thread, puis met à jour l'UI."""
        hdr = detect_hdr(path)
        self._hdr_info = hdr
        log.info("Analyse couleur : %s", "HDR" if hdr.get("is_hdr") else "SDR")
        self.after(0, self._update_hdr_indicator, hdr)

    def _update_hdr_indicator(self, hdr):
        """
        Met à jour l'indicateur HDR10 PQ (bouton orange) et le label d'info.
        Le sélecteur tonemap s'affiche pour tout HDR (PQ ou HLG).
        """
        is_hdr = hdr.get("is_hdr", False)
        transfer = hdr.get("transfer", "").lower()
        is_hdr10 = ("smpte2084" in transfer) or ("pq" in transfer)

        if is_hdr:
            # Afficher le sélecteur de tone mapping
            self._hdr_tonemap_frame.grid(row=2, column=0, sticky="ew")

            if is_hdr10:
                # Allumer le bouton HDR10
                self._hdr10_indicator.config(
                    bg="#ff8c00",          # orange vif
                    fg="black",
                    relief="raised"
                )
                self._hdr_info_label.config(
                    text="Pipeline HDR→SDR actif",
                    fg="#ffd54f"
                )
            elif "hlg" in transfer or "arib" in transfer:
                # HDR HLG : bouton éteint, label spécifique
                self._hdr10_indicator.config(
                    bg=C["panel2"],
                    fg=C["t3"],
                    relief="ridge"
                )
                self._hdr_info_label.config(
                    text="HLG détecté",
                    fg="#ffd54f"
                )
            else:
                # Autre HDR (rare) : bouton éteint
                self._hdr10_indicator.config(
                    bg=C["panel2"],
                    fg=C["t3"],
                    relief="ridge"
                )
                self._hdr_info_label.config(
                    text="HDR détecté (non PQ)",
                    fg="#ffd54f"
                )
        else:
            # Pas de HDR : bouton éteint, masquer le sélecteur tonemap
            self._hdr_tonemap_frame.grid_remove()
            self._hdr10_indicator.config(
                bg=C["panel2"],
                fg=C["t3"],
                relief="ridge"
            )
            self._hdr_info_label.config(
                text="SDR — espace standard",
                fg=C["t3"]
            )

    # ── Options affichage ─────────────────────────────────────────────────────
    def _on_tsize_change(self,*a):
        try: self.v_tsize.set(int(self._v_tsize_var.get()))
        except: pass
        self._rebuild_grid(); self._fit_window(animate=True)

    def _on_cols_change(self,*a):
        try:
            self.v_cols.set(int(self._v_cols_var.get()))
        except:
            pass
        self._reflow_grid()          # ← au lieu de _rebuild_grid
        self._fit_window(animate=True)

    def _on_psize_change(self,*a):
        try: self.v_psize.set(int(self._v_psize_var.get()))
        except: return
        self._fit_window(animate=True)
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))

    def _compute_targets(self):
        dur=self.video_info["duration"]
        if self.v_mode.get()=="count":
            n=max(1,self.v_count.get())
            return [0.0] if n==1 else [i*dur/(n-1) for i in range(n)]
        else:
            iv=max(1,self.v_intv.get()); targets=[]; t=0.0
            while t<=dur+0.001: targets.append(min(t,dur)); t+=iv
            return targets

    # ── Extraction ────────────────────────────────────────────────────────────
    def _start_extraction(self):
        self._loading_thumbs = False
        if not self.v_path.get():
            messagebox.showwarning("Attention","Veuillez choisir une vidéo."); return
        if not self.v_outdir.get():
            messagebox.showwarning("Attention","Veuillez choisir un dossier."); return
        if not self.video_info:
            messagebox.showwarning("Attention","Informations vidéo non chargées."); return
        targets=self._compute_targets()
        if not targets: messagebox.showinfo("Info","Aucune frame à extraire."); return

        self.thumbs.clear(); self.thumb_refs.clear(); self.thumb_by_path.clear()
        self.thumb_wids.clear(); self.sel.clear(); self.marked.clear()
        self._last_click_path=None
        self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Extraction en cours…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._run_btn.set_state("disabled")
        self._cancel_btn.set_state("normal"); self._cancel=False
        # v4.1 : état du flush ordonné (les workers terminent dans le désordre)
        self._next_flush=0; self._flushed=0; self._flush_tot=len(targets)
        self._pending_results={}; self._failed_tcs=[]     # v4.5 : échecs
        log.info("Extraction lancée : %d frame(s) ciblée(s) — %s",
                 len(targets), os.path.basename(self.v_path.get()))
        self._prog.set(0); self._prog_lbl.config(text="Initialisation…")

        threading.Thread(target=self._worker,
                         args=(self.v_path.get(),self.v_outdir.get(),targets),
                         daemon=True).start()

    def _cancel_extraction(self):
        self._cancel=True; self._cancel_btn.set_state("disabled")
        self._prog_lbl.config(text="Annulation…")

    def _run_ffmpeg(self, cmd, timeout):
        """v4.1 : lance ffmpeg via Popen et surveille self._cancel / le timeout.
        v4.5 : retourne (returncode, raison) — la raison est la queue du stderr
        de ffmpeg (capturé dans un fichier temporaire, sans risque de blocage).
        returncode : 0 = succès, -1 = annulation / timeout / erreur de lancement."""
        err_fd, err_path = tempfile.mkstemp(suffix=".txt", prefix="vfe_err_")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err_fd)
        except Exception as ex:
            os.close(err_fd)
            try: os.remove(err_path)
            except Exception: pass
            return -1, f"lancement impossible : {ex}"
        os.close(err_fd)          # l'enfant a sa propre copie du descripteur
        deadline = time.time() + timeout
        rc, reason = -1, ""
        try:
            while True:
                if self._cancel:
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except Exception: proc.kill()
                    rc, reason = -1, "annulé"
                    break
                rc = proc.poll()
                if rc is not None:
                    break
                if time.time() > deadline:
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except Exception: proc.kill()
                    rc, reason = -1, f"timeout après {timeout}s"
                    break
                time.sleep(0.05)
        except Exception as ex:
            try: proc.kill()
            except Exception: pass
            rc, reason = -1, f"erreur : {ex}"
        # Queue du stderr (diagnostic)
        tail = ""
        try:
            with open(err_path, "r", encoding="utf-8", errors="replace") as f:
                tail = f.read().strip()
        except Exception:
            pass
        try: os.remove(err_path)
        except Exception: pass
        return rc, (reason or tail)

    @staticmethod
    def _tmp_ok(tmp_path):
        """Le fichier temporaire existe et n'est pas vide."""
        try:
            return os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0
        except Exception:
            return False

    def _worker(self,vpath,outdir,targets):
        black_tcs=[]
        if self._ffmpeg_ok:
            self._worker_ffmpeg(vpath,outdir,targets,black_tcs)
        else:
            self._worker_opencv(vpath,outdir,targets,black_tcs)
        self.after(0,self._extract_done,black_tcs)

    # ══════════════════════════════════════════════════════════════════════════
    #  WORKER FFMPEG — v3.0 : pipeline HDR→SDR si HDR détecté
    # ══════════════════════════════════════════════════════════════════════════
    def _worker_ffmpeg(self,vpath,outdir,targets,black_tcs):
        # v4.1 : le flush ordonné (thread principal) alimente cette liste
        self._flush_black_tcs = black_tcs
        info=self.video_info
        disp_w=info.get("disp_w",info["width"])
        disp_h=info.get("disp_h",info["height"])
        sar_applied=info.get("sar_applied",False)
        do_filter=self.v_black_filter.get()
        base=os.path.splitext(os.path.basename(vpath))[0]
        hdr_info   = self._hdr_info
        is_hdr     = hdr_info.get("is_hdr", False)
        tonemap    = self.v_hdr_tonemap.get()
        if is_hdr and self._zscale_ok is None:
            self._zscale_ok = zscale_available()

        def task(i, t):
            """Extrait la frame n°i (timestamp t) — tourne dans un thread du pool.
            v4.5 : chaque échec remonte avec sa raison (journal + statut final)."""
            if self._cancel:
                self.after(0, self._on_worker_result, i, "fail", None, "", t, "annulé")
                return
            tmp_fd,tmp_path=tempfile.mkstemp(suffix=".jpg",prefix="vfe_")
            os.close(tmp_fd)
            try: os.remove(tmp_path)
            except Exception: pass
            ok=False; last_reason=""; rc=-1
            if is_hdr:
                # ── Pipeline HDR→SDR (cascade de fallback) ─────────────────
                if self._zscale_ok:
                    cmd=build_ffmpeg_cmd_hdr(vpath,t,tmp_path,disp_w,disp_h,
                                             sar_applied,hdr_info,tonemap)
                    rc,last_reason = self._run_ffmpeg(cmd, timeout=60)
                    ok = rc == 0 and self._tmp_ok(tmp_path)
                if not ok and not self._cancel:
                    cmd2=build_ffmpeg_cmd_hdr_fallback(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    rc,r2 = self._run_ffmpeg(cmd2, timeout=60)
                    if rc == 0 and self._tmp_ok(tmp_path): ok=True
                    else: last_reason = r2 or last_reason
                if not ok and not self._cancel:
                    cmd3=build_ffmpeg_cmd(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    rc,r3 = self._run_ffmpeg(cmd3, timeout=30)
                    if rc == 0 and self._tmp_ok(tmp_path): ok=True
                    else: last_reason = r3 or last_reason
            else:
                # ── Pipeline SDR standard ──────────────────────────────────
                cmd=build_ffmpeg_cmd(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                rc,last_reason = self._run_ffmpeg(cmd, timeout=30)
                ok = rc == 0 and self._tmp_ok(tmp_path)
                if not ok and not self._cancel:
                    cmd2=build_ffmpeg_cmd_fallback(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    rc,r2 = self._run_ffmpeg(cmd2, timeout=30)
                    if rc == 0 and self._tmp_ok(tmp_path): ok=True
                    else: last_reason = r2 or last_reason
            if not ok:
                try: os.remove(tmp_path)
                except Exception: pass
                if rc == 0 and not self._tmp_ok(tmp_path):
                    last_reason = last_reason or "fichier de sortie vide ou absent"
                self.after(0, self._on_worker_result, i, "fail", None, "", t,
                           last_reason or "raison inconnue")
                return
            try:
                img=Image.open(tmp_path).copy()
            except Exception as ex:
                try: os.remove(tmp_path)
                except Exception: pass
                self.after(0, self._on_worker_result, i, "fail", None, "", t,
                           f"décodage image : {ex}")
                return
            if do_filter:
                arr=np.array(img)
                if is_black_frame(arr,threshold=5):
                    try: os.remove(tmp_path)
                    except Exception: pass
                    self.after(0, self._on_worker_result, i, "black", None, "", t)
                    return
            # v4.1 : numéro = position dans le plan d'extraction
            fname=f"{base}_{i+1:04d}_{tc_str(t)}.jpg"
            fpath=os.path.join(outdir,fname)
            try:
                shutil.move(tmp_path,fpath)
            except Exception as ex:
                try: os.remove(tmp_path)
                except Exception: pass
                self.after(0, self._on_worker_result, i, "fail", None, "", t,
                           f"déplacement : {ex}")
                return
            self.after(0, self._on_worker_result, i, "ok", img, fpath, t)

        # v4.1 : FFMPEG_WORKERS ffmpeg en parallèle
        with ThreadPoolExecutor(max_workers=FFMPEG_WORKERS) as ex:
            futures=[ex.submit(task,i,t) for i,t in enumerate(targets)]
            for f in futures:
                try: f.result()
                except Exception as exc:
                    log.exception("Worker inattendu : %s", exc)

    # ── Fallback OpenCV ───────────────────────────────────────────────────────
    def _worker_opencv(self,vpath,outdir,targets,black_tcs):
        cap=cv2.VideoCapture(vpath)
        tot=len(targets)
        info=self.video_info
        disp_w=info.get("disp_w",info["width"])
        disp_h=info.get("disp_h",info["height"])
        sar_applied=info.get("sar_applied",False)
        do_filter=self.v_black_filter.get()
        base=os.path.splitext(os.path.basename(vpath))[0]
        color_limited=self._detect_limited_range_opencv(vpath,cap)

        for i,t in enumerate(targets):
            if self._cancel: break
            cap.set(cv2.CAP_PROP_POS_MSEC,t*1000.0)
            ret,frame=cap.read()
            if not ret:
                for bk in (500,1000,1500,2000,3000):
                    cap.set(cv2.CAP_PROP_POS_MSEC,max(0.0,t*1000.0-bk))
                    ret,frame=cap.read()
                    if ret: break
            if not ret: continue
            if color_limited: frame=self._expand_limited_range(frame)
            if do_filter and is_black_frame(
                    np.array(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))),5):
                black_tcs.append(t)
                self.after(0,self._black_skipped,t,i+1,tot,(i+1)/tot*100); continue
            img=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            if sar_applied and (disp_w,disp_h)!=(img.width,img.height):
                img=img.resize((disp_w,disp_h),Image.LANCZOS)
            fname=f"{base}_{i+1:04d}_{tc_str(t)}.jpg"   # v4.1 : numéro = position dans le plan
            fpath=os.path.join(outdir,fname)
            img.save(fpath,"JPEG",quality=95,subsampling=0)
            self.after(0,self._frame_done,img,fpath,t,i+1,tot,(i+1)/tot*100)
        cap.release()

    def _detect_limited_range_opencv(self,vpath,cap):
        try:
            cmd=["ffprobe","-v","error","-select_streams","v:0",
                 "-show_entries","stream=color_range","-of","csv=p=0",vpath]
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
            if r.returncode==0:
                out=r.stdout.strip().lower()
                if "tv" in out or "mpeg" in out: return True
                if "pc" in out or "full" in out: return False
        except Exception: pass
        try:
            dur=self.video_info.get("duration",0); mins=[]; maxs=[]
            for pos in [5000,dur*500,max(0,dur*1000-5000)]:
                cap.set(cv2.CAP_PROP_POS_MSEC,pos)
                ret,f=cap.read()
                if ret: mins.append(int(f.min())); maxs.append(int(f.max()))
            if mins and min(mins)>=14 and max(maxs)<=237: return True
        except Exception: pass
        return False

    @staticmethod
    def _expand_limited_range(frame):
        f=frame.astype(np.float32)
        return np.clip((f-16.0)*(255.0/219.0),0,255).astype(np.uint8)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _black_skipped(self,t,done,tot,pct):
        self._prog.set(pct)
        self._prog_lbl.config(text=f"{done}/{tot}  ·  {hms(t)}  🔲 noire ignorée")

    def _on_worker_result(self, i, kind, img, fpath, t, info=""):
        """v4.1 : résultat d'un worker ffmpeg (kind = "ok" / "black" / "fail").
        Bufferise puis affiche strictement dans l'ordre du plan.
        v4.5 : les échecs sont comptés, journalisés et affichés en fin d'extraction."""
        self._pending_results[i] = (kind, img, fpath, t, info)
        while self._next_flush in self._pending_results:
            k, im, fp, tc, inf = self._pending_results.pop(self._next_flush)
            self._flushed += 1
            pct = self._flushed / max(1, self._flush_tot) * 100
            if k == "ok":
                self._frame_done(im, fp, tc, self._flushed, self._flush_tot, pct)
            elif k == "black":
                self._flush_black_tcs.append(tc)
                self._black_skipped(tc, self._flushed, self._flush_tot, pct)
            else:   # "fail"
                self._failed_tcs.append(tc)
                log.warning("Échec frame %d (%s) : %s", i + 1, hms(tc), inf or "raison inconnue")
            self._next_flush += 1

    def _frame_done(self,img,fpath,t,done,tot,pct):
        entry={"img":img,"path":fpath,"tc":t}
        self.thumbs.append(entry)
        self.thumb_by_path[fpath]=entry            # v4
        pos=len(self.thumbs)-1
        self._prog.set(pct); self._prog_lbl.config(text=f"{done}/{tot}  ·  {hms(t)}")
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._add_thumb(fpath,pos)
        self._adjust_center_width()

    def _extract_done(self,black_tcs=None):
        self._run_btn.set_state("normal"); self._cancel_btn.set_state("disabled")
        n=len(self.thumbs); nb=len(black_tcs) if black_tcs else 0
        nf=len(self._failed_tcs)                       # v4.5
        log.info("Extraction terminée : %d image(s), %d noire(s) filtrée(s), %d échec(s)%s",
                 n, nb, nf, "  [ANNULÉE]" if self._cancel else "")
        if self._cancel: self._prog_lbl.config(text=f"Annulé · {n} image(s) sauvegardée(s)")
        elif nf: self._prog.set(100); self._prog_lbl.config(text=f"⚠  Terminé · {n} image(s) · {nf} échec(s)")
        else: self._prog.set(100); self._prog_lbl.config(text=f"✔  Terminé · {n} image(s)")
        self._prev_info.config(text="Cliquez sur une\nvignette…" if n else "Aucune image extraite.")
        # v4.5 : les échecs sont l'info la plus importante → priorité dans la barre de statut
        if nf and not self._cancel:
            self._status(f"⚠  {nf} échec(s) d'extraction :  "+"  |  ".join(hms(t) for t in self._failed_tcs),duration=0)
        elif nb>0:
            self._status(f"🔲  {nb} frame(s) noire(s) :  "+"  |  ".join(hms(t) for t in black_tcs),duration=0)
        elif black_tcs is not None and self.v_black_filter.get():
            self._status("✔  Aucune frame noire détectée.",duration=6000)

    # ── Grille vignettes ──────────────────────────────────────────────────────
    def _add_thumb(self, path, pos):
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.refresh()
            return

        entry = self.thumb_by_path[path]
        sz = self.v_tsize.get()
        cols = self.v_cols.get()
        th = entry["img"].copy()
        th.thumbnail((sz, sz), Image.LANCZOS)
        # ── Composite de l'icône si marquée ───────────────────────────────────
        if path in self.marked:
            if not hasattr(self, '_cached_check_pil'):
                self._cached_check_pil = self._make_check_icon(size=22)
            ICON_SIZE = 22
            icon = self._cached_check_pil
            th_rgba = th.convert("RGBA")
            x = th_rgba.width - ICON_SIZE - 2
            y = 2
            th_rgba.paste(icon, (x, y), icon)
            th = th_rgba.convert("RGB")
        imgtk = ImageTk.PhotoImage(th)
        self.thumb_refs[path] = imgtk              # v4 : dict par chemin
        ri, ci = divmod(pos, cols)
        cell = tk.Frame(self._gf, bg=C["thumb_bg"], padx=4, pady=4, cursor="hand2")
        cell.grid(row=ri, column=ci, padx=5, pady=5)
        lbl = tk.Label(cell, image=imgtk, bg=C["thumb_bg"], bd=0, relief="flat",
                     cursor="hand2", highlightthickness=2,
                     highlightbackground=C["thumb_bg"], highlightcolor=C["thumb_bg"])
        lbl.image = imgtk
        lbl.pack()
        tclbl = tk.Label(cell, text=hms(entry["tc"]), font=("Segoe UI", 8),
                         fg=C["t3"], bg=C["thumb_bg"])
        tclbl.pack()
        for w in (cell, lbl, tclbl):
            w._path = path                          # v4 : identité = chemin
        for w in (cell, lbl, tclbl):
            w.bind("<ButtonPress-1>",    self._on_thumb_press)
            w.bind("<Button-1>",         self._on_thumb_button1)
            w.bind("<Control-Button-1>", self._on_thumb_ctrl_click)
            w.bind("<Shift-Button-1>",   self._on_thumb_shift_click)
            w.bind("<B1-Motion>",        self._on_thumb_motion)
            w.bind("<ButtonRelease-1>",  self._on_thumb_release)
            w.bind("<Enter>",            self._on_thumb_enter)
            w.bind("<Leave>",            self._on_thumb_leave)
        self.thumb_wids[path] = {"frame": cell, "label": lbl, "tc_lbl": tclbl}

    # ── Redimensionnement ─────────────────────────────────────────────────────
    _fit_job=None

    def _fit_window(self, animate=True):
        SASH_W = 5
        sz = self.v_tsize.get()
        cols = self.v_cols.get()
        center_need = cols * (sz + 22) + 12 + 14 + 10
        right_need = self.v_psize.get() + 36
        self.update_idletasks()

        try:
            s0 = self._pane.sash_coord(0)[0]
        except Exception:
            s0 = LEFT_MIN_W

        if getattr(self, '_loading_thumbs', False):
            try:
                self._pane.paneconfig(self._cf, minsize=center_need)
                self._pane.paneconfig(self._rf, minsize=right_need)
            except Exception:
                pass
            return

        sw = self.winfo_screenwidth()
        win_target = min(max(s0 + center_need + right_need + SASH_W * 2 + 4,
                            LEFT_MIN_W + 300), sw - 40)
        # ↓ toujours conserver la hauteur actuelle de la fenêtre
        current_h = self.winfo_height()
        cy = self.winfo_y()

        def _apply(w):
            cx = max(0, (sw - w) // 2)
            self.geometry(f"{w}x{current_h}+{cx}+{cy}")  # ← current_h figé au début
            self.update_idletasks()
            try:
                self._pane.paneconfig(self._cf, minsize=center_need)
                self._pane.paneconfig(self._rf, minsize=right_need)
                self.update_idletasks()
                total = self._pane.winfo_width()
                s1_new = max(s0 + center_need, total - right_need - SASH_W)
                self._pane.sash_place(0, s0, 0)
                self._pane.sash_place(1, s1_new, 0)
            except Exception:
                pass

        if not animate:
            _apply(win_target)
            return

        w_start = self.winfo_width()
        delta = win_target - w_start
        if abs(delta) < 4:
            _apply(win_target)
            return

        if self._fit_job:
            self.after_cancel(self._fit_job)
            self._fit_job = None

        def _step(i):
            t = i / 8
            ease = t * (2 - t)
            _apply(int(w_start + delta * ease))
            if i < 8:
                self._fit_job = self.after(15, _step, i + 1)
            else:
                self._fit_job = None
                _apply(win_target)

        _step(1)

    def _adjust_center_width(self): self._fit_window(animate=False)

    def _on_grid_configure(self, e):
        if GRID_VIRTUAL:
            return

        if getattr(self, '_loading_thumbs', False):
            return
        self._cv.configure(scrollregion=self._cv.bbox("all"))

    def _clear_grid(self):
        if hasattr(self, "_preview_cache"):
            self._preview_cache.clear()

        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.canvas.delete("vt")
                self._vg.refresh()
            return

        for w in self._gf.winfo_children(): w.destroy()
        self.thumb_refs.clear(); self.thumb_wids.clear()

    def _clear_all_thumb_state(self):
        """Réinitialise complètement l'état des vignettes (zéro image)."""
        self._clear_grid()
        self.thumbs.clear()
        self.thumb_refs.clear()
        self.thumb_by_path.clear()
        self.thumb_wids.clear()
        self.sel.clear()
        self.marked.clear()
        self._last_click_path=None
        self._upd_marked_badge()
        self._prev_lbl.config(image="")
        self._prev_ref = None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text="0 image(s)")
        self._badge_sel.config(text="")
        self._del_btn.set_state("disabled")
        self._copy_btn.set_state("disabled")

    def _rebuild_grid(self):
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.refresh()
            return

        self._clear_grid()
        self._loading_thumbs = True
        for pos, entry in enumerate(self.thumbs):
            self._add_thumb(entry["path"], pos)
        self._loading_thumbs = False
        for p in self.sel:    self._set_sel(p, True)
        for p in self.marked: self._update_mark_overlay(p)
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        self._adjust_center_width()
        # --- forcer le rafraîchissement du canvas ---
        self._gf.update_idletasks()
        self._cv.configure(scrollregion=self._cv.bbox("all"))
        self._cv.yview_moveto(0)

    # ── Sélection ─────────────────────────────────────────────────────────────
    def _thumb_hover(self,cell,path,on):
        try:
            if not cell.winfo_exists() or path in self.sel: return
            bg=C["thumb_hov"] if on else C["thumb_bg"]; cell.config(bg=bg)
            for ch in cell.winfo_children():
                try: ch.config(bg=bg)
                except Exception: pass
        except Exception: pass

    def _thumb_click(self,idx): self._click(idx)

    def _get_path_from_event(self, event):
        """v4 : retourne le chemin stocké dans le widget ayant reçu l'événement."""
        return event.widget._path

    def _on_thumb_press(self, event):
        self.focus_set()
        self._drag_start_from_thumb(event)

    def _on_thumb_button1(self, event):
        self._click(self._get_path_from_event(event))

    def _on_thumb_ctrl_click(self, event):
        self.focus_set()
        self._ctrl_click(self._get_path_from_event(event))

    def _on_thumb_shift_click(self, event):
        self.focus_set()
        self._shift_click(self._get_path_from_event(event))

    def _on_thumb_motion(self, event):
        self._drag_motion_from_thumb(event)

    def _on_thumb_release(self, event):
        self._drag_end_from_thumb(event)

    def _on_thumb_enter(self, event):
        path = self._get_path_from_event(event)
        cell = self.thumb_wids[path]["frame"]
        self._thumb_hover(cell, path, True)

    def _on_thumb_leave(self, event):
        path = self._get_path_from_event(event)
        cell = self.thumb_wids[path]["frame"]
        self._thumb_hover(cell, path, False)

    def _clear_selection(self):
        """v4 : efface toute la sélection (les sets contiennent des chemins)."""
        for p in list(self.sel):
            self._set_sel(p, False)
        self.sel.clear()
        self._last_click_path = None

    def _position_of(self, path):
        """Position d'affichage d'un chemin dans self.thumbs, ou -1 si absent."""
        entry = self.thumb_by_path.get(path)
        if entry is None:
            return -1
        try:
            return self.thumbs.index(entry)
        except ValueError:
            return -1

    def _click(self,path):
        if path in self.sel:
            self._set_sel(path,False); self.sel.discard(path); self._upd_badges()
            if len(self.sel)==1:
                remaining=next(iter(self.sel))
                self._show_preview(remaining); self._last_click_path=remaining
            elif len(self.sel)==0:
                self._last_click_path=None; self._prev_info.config(text="Cliquez sur une\nvignette…")
            return
        self._clear_selection()
        self.sel.add(path); self._set_sel(path,True)
        self._last_click_path=path; self._upd_badges(); self._show_preview(path)

    def _ctrl_click(self,path):
        if path in self.sel: self.sel.discard(path); self._set_sel(path,False)
        else:                self.sel.add(path);     self._set_sel(path,True)
        self._upd_badges()
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        elif len(self.sel)>1:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _shift_click(self,path):
        anchor=self._last_click_path
        if anchor is None or anchor not in self.thumb_by_path:
            self._click(path); return
        order=[e["path"] for e in self.thumbs]
        try:
            a=order.index(anchor); b=order.index(path)
        except ValueError:
            self._click(path); return
        lo,hi=min(a,b),max(a,b)
        self._clear_selection()
        for p in order[lo:hi+1]:
            self.sel.add(p); self._set_sel(p,True)
        self._last_click_path=path
        self._upd_badges()
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        else:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _set_sel(self,path,on):
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.update_selection()
            return

        if path not in self.thumb_wids: return
        w=self.thumb_wids[path]
        bg=C["thumb_sel"] if on else C["thumb_bg"]; brd=C["sel_brd"] if on else C["thumb_bg"]
        w["frame"].config(bg=bg)
        w["label"].config(bg=bg,highlightthickness=2,highlightbackground=brd,highlightcolor=brd)
        w["tc_lbl"].config(bg=bg)
        sync=w.get("mark_sync")
        if sync:
            try: sync(on)
            except Exception: pass

    def _upd_badges(self):
        n_sel = len(self.sel)
        n_marked = len(self.marked)
        self._badge_sel.config(text=f"{n_sel} sélectionnée(s)" if n_sel else "")
        self._del_btn.set_state("normal" if n_sel else "disabled")
        self._copy_btn.set_state("normal" if (n_sel or n_marked) else "disabled")

    # ── Suppression ───────────────────────────────────────────────────────────
    def _delete_selected(self):
        if not self.sel:
            return
        n = len(self.sel)
        if self.v_confirm_del.get():
            if not messagebox.askyesno("Supprimer",
                    f"Supprimer {n} image(s) sélectionnée(s) ?\nLes fichiers seront déplacés vers la corbeille."):
                return
        # v4 : identité = chemin → aucune renumérotation nécessaire
        deleted_paths = list(self.sel)
        deleted_set   = set(deleted_paths)
        first_pos     = min(self._position_of(p) for p in deleted_paths)
        # 1) v4.4 : envoyer les fichiers à la corbeille (envoi groupé)
        errors = trash_files(deleted_paths)
        log.info("Suppression : %d image(s) → corbeille%s", len(deleted_paths),
                 f" ({len(errors)} erreur(s))" if errors else "")
        # 2) Détruire les widgets + nettoyer les structures
        for path in deleted_paths:
            w = self.thumb_wids.pop(path, None)
            if w:
                w["frame"].destroy()
            self.marked.discard(path)
            self.thumb_refs.pop(path, None)
            self.thumb_by_path.pop(path, None)
        # 3) Reconstruire la liste ordonnée sans les supprimés
        self.thumbs = [e for e in self.thumbs if e["path"] not in deleted_set]
        self.sel.clear()
        if errors:
            messagebox.showwarning("Erreurs",
                "Fichier(s) non supprimé(s), encore présent(s) dans le dossier :\n" +
                "\n".join(f"{os.path.basename(p)} : {ex}" for p, ex in errors))
        # 4) Plus rien → réinitialiser
        if not self.thumbs:
            self._clear_all_thumb_state()
            self._auto_save_config()
            return
        # 5) Repositionner + sélectionner le voisin le plus proche
        self._reflow_grid()
        new_pos  = min(first_pos, len(self.thumbs) - 1)
        new_path = self.thumbs[new_pos]["path"]
        self.sel.add(new_path)
        self._set_sel(new_path, True)
        self._last_click_path = new_path
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._upd_badges()
        self._upd_marked_badge()
        self._show_preview(new_path)
        self._scroll_to_thumb(new_path)
        self._auto_save_config()

    def _clear_output_dir(self):
        outdir=self.v_outdir.get()
        if not outdir: messagebox.showwarning("Attention","Aucun dossier cible défini."); return
        if not os.path.isdir(outdir): messagebox.showwarning("Attention","Le dossier n'existe pas."); return
        jpgs=[f for f in os.listdir(outdir) if f.lower().endswith((".jpg",".jpeg"))]
        if not jpgs: messagebox.showinfo("Info","Le dossier est déjà vide."); return
        # v4.4 : confirmation TOUJOURS demandée pour "Vider" (même si la case est décochée)
        if not messagebox.askyesno("Vider le dossier",
                f"Déplacer {len(jpgs)} fichier(s) JPG vers la corbeille ?"):
            return
        # v4.4 : corbeille au lieu de la suppression définitive
        errors = trash_files([os.path.join(outdir, f) for f in jpgs])
        if errors:
            messagebox.showwarning("Erreurs",
                "\n".join(f"{os.path.basename(p)} : {ex}" for p, ex in errors))
        log.info("Vider le dossier : %d fichier(s) → corbeille", len(jpgs) - len(errors))
        self.thumbs.clear(); self.thumb_refs.clear(); self.thumb_by_path.clear(); self.thumb_wids.clear()
        self.sel.clear(); self.marked.clear(); self._last_click_path=None; self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._prog.set(0)
        self._prog_lbl.config(text=f"✔  {len(jpgs)-len(errors)} fichier(s) déplacé(s) vers la corbeille")

    # ── Drag-select ───────────────────────────────────────────────────────────
    def _drag_start(self,event):
        if GRID_VIRTUAL:
            self._drag_in_zone=False
            return

        self._drag_active=False; self._drag_in_zone=True; self._drag_sel_before=set(self.sel)
        rx=event.x_root-self._cv.winfo_rootx(); ry=event.y_root-self._cv.winfo_rooty()
        self._drag_origin_cv=(self._cv.canvasx(rx),self._cv.canvasy(ry))
        self._drag_origin_root=(event.x_root,event.y_root); self.focus_set()

    def _drag_start_from_thumb(self,event):
        rx=event.x_root-self._cv.winfo_rootx(); ry=event.y_root-self._cv.winfo_rooty()
        self._drag_active=False; self._drag_in_zone=True; self._drag_sel_before=set(self.sel)
        self._drag_origin_cv=(self._cv.canvasx(rx),self._cv.canvasy(ry))
        self._drag_origin_root=(event.x_root,event.y_root)

    def _drag_motion(self,event):
        if not self._drag_in_zone: return
        ox_r,oy_r=self._drag_origin_root; ox_cv,oy_cv=self._drag_origin_cv
        if not self._drag_active:
            if abs(event.x_root-ox_r)<5 and abs(event.y_root-oy_r)<5: return
            self._drag_active=True
            self._clear_selection()
        self._do_drag(event.x_root,event.y_root,ox_cv,oy_cv)

    def _drag_motion_from_thumb(self,event):
        if not self._drag_in_zone: return
        ox_r,oy_r=self._drag_origin_root; ox_cv,oy_cv=self._drag_origin_cv
        if not self._drag_active:
            if abs(event.x_root-ox_r)<5 and abs(event.y_root-oy_r)<5: return
            self._drag_active=True
            self._clear_selection()
        self._do_drag(event.x_root,event.y_root,ox_cv,oy_cv)

    def _do_drag(self,x_root,y_root,ox_cv,oy_cv):
        rx=x_root-self._cv.winfo_rootx(); ry=y_root-self._cv.winfo_rooty()
        cx_cv=self._cv.canvasx(rx); cy_cv=self._cv.canvasy(ry)
        x1,x2=min(ox_cv,cx_cv),max(ox_cv,cx_cv); y1,y2=min(oy_cv,cy_cv),max(oy_cv,cy_cv)
        self._cv.delete("rb")
        self._cv.create_rectangle(x1,y1,x2,y2,outline="",fill=C["accent_bg"],stipple="gray25",tags="rb")
        self._cv.create_rectangle(x1,y1,x2,y2,outline=C["accent"],fill="",width=2,dash=(6,3),tags="rb")
        self._cv.tag_raise("rb")
        gx=self._gf.winfo_x(); gy=self._gf.winfo_y(); new_sel=set()
        for path,w in self.thumb_wids.items():
            cell=w["frame"]
            try:
                if not cell.winfo_exists(): continue
                cx0=cell.winfo_x()+gx; cy0=cell.winfo_y()+gy
                cw=cell.winfo_width(); ch=cell.winfo_height()
                if cx0<x2 and cx0+cw>x1 and cy0<y2 and cy0+ch>y1: new_sel.add(path)
            except Exception: pass
        for p in new_sel-self.sel:  self.sel.add(p);    self._set_sel(p,True)
        for p in self.sel-new_sel:  self.sel.discard(p);self._set_sel(p,False)
        self._upd_badges()
        if len(self.sel)>1:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _drag_end(self,event):
        if GRID_VIRTUAL:
            return
        self._finish_drag(event)

    def _drag_end_from_thumb(self,event):
        if self._drag_active: self._finish_drag(event)
        self._drag_in_zone=False

    def _finish_drag(self,event):
        self._cv.delete("rb"); self._drag_in_zone=False
        if not self._drag_active: self._deselect_all_if_empty_click(event); return
        self._drag_active=False
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        elif len(self.sel)==0: self._prev_info.config(text="Cliquez sur une\nvignette…")

    def _deselect_all_if_empty_click(self,event):
        xr,yr=event.x_root,event.y_root
        for w in self.thumb_wids.values():
            cell=w["frame"]
            try:
                if not cell.winfo_exists(): continue
                if (cell.winfo_rootx()<=xr<=cell.winfo_rootx()+cell.winfo_width() and
                    cell.winfo_rooty()<=yr<=cell.winfo_rooty()+cell.winfo_height()): return
            except Exception: pass
        if self.sel:
            self._clear_selection(); self._upd_badges()
            self._prev_info.config(text="Cliquez sur une\nvignette…")

    # ── Marquage ──────────────────────────────────────────────────────────────
    def _on_mark_key(self,event):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,DarkEntry)): return
        if not self.sel: return
        if self.sel.issubset(self.marked):
            for p in list(self.sel): self.marked.discard(p); self._update_mark_overlay(p)
        else:
            for p in self.sel: self.marked.add(p); self._update_mark_overlay(p)
        self._upd_marked_badge(); self._auto_save_config()

    def _make_check_icon(self, size=22):
        """Génère l'icône programmatiquement : carré arrondi gris + coche orange."""
        from PIL import ImageDraw
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # fond 100% transparent
        draw = ImageDraw.Draw(img)

        # Carré arrondi gris moyen semi-opaque
        r = 4
        box = [1, 1, size - 2, size - 2]
        draw.rounded_rectangle(box, radius=r, fill=(30, 30, 30, 255))

        # Coche orange
        orange = (255, 140, 0, 255)
        m = size / 22
        pts = [
            (4 * m,  11 * m),
            (9 * m,  16 * m),
            (18 * m,  6 * m),
        ]
        draw.line(pts, fill=orange, width=max(2, int(2.5 * m)))

        return img

    def _update_mark_overlay(self, path):
        """Recrée la vignette avec ou sans icône composite selon l'état marqué."""
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.refresh()
            return

        if path not in self.thumb_wids:
            return

        w = self.thumb_wids[path]
        entry = self.thumb_by_path[path]
        sz = self.v_tsize.get()

        th = entry["img"].copy()
        th.thumbnail((sz, sz), Image.LANCZOS)

        if path in self.marked:
            if not hasattr(self, '_cached_check_pil'):
                self._cached_check_pil = self._make_check_icon(size=22)

            ICON_SIZE = 22
            icon = self._cached_check_pil
            th_rgba = th.convert("RGBA")
            x = th_rgba.width - ICON_SIZE - 2
            y = 2
            th_rgba.paste(icon, (x, y), icon)
            th = th_rgba.convert("RGB")

        imgtk = ImageTk.PhotoImage(th)
        self.thumb_refs[path] = imgtk
        w["label"].config(image=imgtk)
        w["label"].image = imgtk

    def _toggle_mark(self,path):
        if path in self.marked: self.marked.discard(path)
        else: self.marked.add(path)
        self._update_mark_overlay(path); self._upd_marked_badge(); self._auto_save_config()

    def _unmark_all(self):
        for p in list(self.marked): self.marked.discard(p); self._update_mark_overlay(p)
        self._upd_marked_badge(); self._auto_save_config()

    def _mark_selection(self):
        if not self.sel:
            self._status("⚠  Aucune image sélectionnée.")
            return
        if self.sel.issubset(self.marked):
            for p in list(self.sel):
                self.marked.discard(p)
                self._update_mark_overlay(p)
        else:
            for p in list(self.sel):
                self.marked.add(p)
                self._update_mark_overlay(p)
        self._upd_marked_badge()
        self._auto_save_config()

    def _upd_marked_badge(self):
        n = len(self.marked)
        self._badge_marked.config(text=f"✓ {n} marquée(s)" if n else "")
        self._upd_badges()   # active/désactive le bouton de déplacement selon sel + marked

    def _collect_config(self):
        """v4.2 : point unique de collecte de la config (UI + état interne).
        Remplace les deux dicts dupliqués des anciennes sauvegardes."""
        s0, s1 = self._get_sash_positions()
        raw = {
            "video_path":     self.v_path.get(),
            "output_dir":     self.v_outdir.get(),
            "work_dir":       self.v_workdir.get(),
            "generic_name":   self.v_generic.get(),
            "mode":           self.v_mode.get(),
            "count_val":      self.v_count.get(),
            "interval_val":   self.v_intv.get(),
            "thumb_size":     self.v_tsize.get(),
            "col_count":      self.v_cols.get(),
            "preview_size":   self.v_psize.get(),
            "window_size":    self.v_winsize.get(),
            "sash_left":      s0,
            "sash_right":     s1,
            "confirm_delete": self.v_confirm_del.get(),
            "black_filter":   self.v_black_filter.get(),
            "mark_key":       self.v_mark_key.get(),
            "hdr_tonemap":    self.v_hdr_tonemap.get(),
            "last_video_dir":  self._cfg.get("last_video_dir", ""),
            "last_output_dir": self._cfg.get("last_output_dir", ""),
            "last_work_dir":   self._cfg.get("last_work_dir", ""),
            "marked_files":    sorted(self.marked),
            "window_h":        self.winfo_height(),
        }
        return _coerce_config(raw)

    def _auto_save_config(self):
        save_config(self._collect_config())

    def _restore_marked(self):
        saved = set(self._cfg.get("marked_files", []))
        if not saved:
            return

        for entry in self.thumbs:
            p = entry["path"]
            if p in saved:
                self.marked.add(p)
                self._update_mark_overlay(p)

        self._upd_marked_badge()

    # ── Déplacement vers dossier de travail ───────────────────────────────────
    def _status(self,msg,duration=4000):
        self._statusbar.config(text=msg)
        if duration: self.after(duration,lambda: self._statusbar.config(text=""))

    def _next_num_in_workdir(self,workdir,generic):
        import re
        pat=re.compile(r'^'+re.escape(generic)+r'_(\d+)\.jpe?g$',re.IGNORECASE)
        max_n=0
        try:
            for f in os.listdir(workdir):
                m=pat.match(f)
                if m: max_n=max(max_n,int(m.group(1)))
        except Exception: pass
        return max_n+1

    def _move_to_workdir(self):
        combined = self.sel | self.marked
        if not combined:
            self._status("⚠  Aucune image sélectionnée ni marquée."); return
        workdir = self.v_workdir.get().strip()
        if not workdir: self._status("⚠  Dossier de Travail non défini."); return
        if not os.path.isdir(workdir): self._status(f"⚠  Dossier introuvable : {workdir}"); return
        generic = self.v_generic.get().strip() or "capture"
        paths = sorted(combined)
        n = len(paths)
        num = self._next_num_in_workdir(workdir, generic)
        moves = []
        for src in paths:
            while True:
                dst = os.path.join(workdir, f"{generic}_{num:04d}.jpg")   # v4.3 : 4 chiffres → tri alpha = ordre
                if not os.path.exists(dst): break
                num += 1
            moves.append((src, dst)); num += 1
        ok = 0; errors = []; moved_paths = set()
        for src, dst in moves:
            try:
                shutil.move(src, dst); ok += 1; moved_paths.add(src)
            except Exception as ex:
                errors.append(f"{os.path.basename(src)} → {ex}")
        if errors: messagebox.showwarning("Erreurs", "\n".join(errors))
        log.info("Déplacement : %d/%d image(s) → %s", ok, n, workdir)
        # v4 : retirer les images déplacées (identité = chemin)
        for path in moved_paths:
            w = self.thumb_wids.pop(path, None)
            if w: w["frame"].destroy()
            self.sel.discard(path)
            self.marked.discard(path)
            self.thumb_refs.pop(path, None)
            self.thumb_by_path.pop(path, None)
        self.thumbs = [e for e in self.thumbs if e["path"] not in moved_paths]
        self._last_click_path = None
        self._reflow_grid()
        self._prev_lbl.config(image=""); self._prev_ref = None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._upd_badges(); self._upd_marked_badge()
        self._auto_save_config()
        msg = f"✔  {ok}/{n} image(s) déplacée(s) vers {os.path.basename(workdir)}"
        if errors: msg += f"  ({len(errors)} erreur(s))"
        self._status(msg, duration=6000)

    # ── Aperçu ────────────────────────────────────────────────────────────────
    def _show_preview(self,path):
        if path is None:
            return

        entry = self.thumb_by_path.get(path)
        if entry is None:
            return

        sz = self.v_psize.get()

        if not hasattr(self, "_preview_cache"):
            self._preview_cache = {}

        key = (path, sz)
        cached = self._preview_cache.get(key)

        if cached is not None:
            imgtk, ow, oh = cached
        else:
            try:
                full = Image.open(entry["path"])
                ow, oh = full.size
                full.draft("RGB", (sz, sz))
                p = full.copy()
            except Exception:
                p = entry["img"].copy() if entry.get("img") is not None else None
                ow, oh = (p.size if p is not None else (0, 0))

            if p is None:
                return

            p.thumbnail((sz, sz), Image.LANCZOS)
            imgtk = ImageTk.PhotoImage(p)

            self._preview_cache[key] = (imgtk, ow, oh)

            if len(self._preview_cache) > 16:
                try:
                    self._preview_cache.pop(next(iter(self._preview_cache)))
                except Exception:
                    pass

        self._prev_ref = imgtk
        self._prev_lbl.config(image=imgtk)

        pos = self._position_of(path) + 1
        self._prev_info.config(
            text=f"{os.path.basename(entry['path'])}\n\n"
                 f"⏱  {hms(entry['tc'])}\n📐  {ow}×{oh} px\n#{pos} / {len(self.thumbs)}")

    # ── Rechargement dossier ──────────────────────────────────────────────────
    def _reload_extraction_folder(self):
        outdir = self.v_outdir.get()
        if not outdir or not os.path.isdir(outdir):
            return
        jpgs = sorted([f for f in os.listdir(outdir)
                    if f.lower().endswith((".jpg", ".jpeg"))], key=str.lower)
        if not jpgs:
            self._clear_all_thumb_state()
            self._prog_lbl.config(text="✔  Dossier vide, aucune image.")
            self.after(3000, lambda: self._prog_lbl.config(text=""))
            return

        self.thumbs.clear()
        self.thumb_refs.clear()
        self.thumb_by_path.clear()
        self.thumb_wids.clear()
        self.sel.clear()
        self.marked.clear()
        self._last_click_path=None
        self._upd_marked_badge()
        self._clear_grid()
        self._prog_lbl.config(text=f"Lecture du dossier ({len(jpgs)} fichier(s))…")

        # Plus de thread : on livre les chemins directement, sans charger les images
        entries = [(os.path.join(outdir, fname),
                    _parse_tc_from_filename(fname)) for fname in jpgs]
        self._reload_done_lazy(entries)

    def _reflow_grid(self):
        """Repositionne les widgets existants dans la grille sans rien recréer."""
        if GRID_VIRTUAL:
            if getattr(self, "_vg", None) is not None:
                self._vg.refresh()
            return

        cols = self.v_cols.get()
        for pos, entry in enumerate(self.thumbs):
            w = self.thumb_wids.get(entry["path"])
            if w:
                ri, ci = divmod(pos, cols)
                w["frame"].grid(row=ri, column=ci, padx=5, pady=5)
        self._adjust_center_width()

    def _refresh_folder(self):
        """Relance le chargement des images depuis le dossier d'extraction."""
        outdir = self.v_outdir.get()
        if not outdir or not os.path.isdir(outdir):
            self._status("⚠  Aucun dossier d'extraction défini ou inexistant.", duration=4000)
            return
        self._status("🔁 Rafraîchissement en cours…", duration=0)
        self._reload_extraction_folder()

    def _reload_done(self, loaded):
        for img, fpath, tc in loaded:
            entry = {"img": img, "path": fpath, "tc": tc}
            self.thumbs.append(entry)
            self.thumb_by_path[fpath] = entry
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._prog_lbl.config(text=f"Chargement des vignettes… 0 / {len(self.thumbs)}")
        self._build_thumbs_async(0)

    def _reload_done_lazy(self, entries):
        """Stocke les métadonnées sans charger les pixels, puis construit les vignettes une par une."""
        for fpath, tc in entries:
            entry = {"img": None, "path": fpath, "tc": tc}
            self.thumbs.append(entry)
            self.thumb_by_path[fpath] = entry
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._prog_lbl.config(text=f"Chargement des vignettes… 0 / {len(self.thumbs)}")
        self._build_thumbs_async(0)

    def _build_thumbs_async(self, start_idx):
        if start_idx == 0:
            self._loading_thumbs = True

        BATCH_SIZE = 5
        end_idx = min(start_idx + BATCH_SIZE, len(self.thumbs))
        sz = self.v_tsize.get()
        for i in range(start_idx, end_idx):
            entry = self.thumbs[i]
            if entry["img"] is None:
                try:
                    im = Image.open(entry["path"])
                    im.draft("RGB", (sz, sz))   # décodage JPEG allégé, échelle 1/2·1/4·1/8
                    entry["img"] = im.copy()
                except Exception:
                    continue
            self._add_thumb(entry["path"], i)
        self._prog_lbl.config(text=f"Chargement des vignettes… {end_idx} / {len(self.thumbs)}")
        if end_idx < len(self.thumbs):
            self.after(1, self._build_thumbs_async, end_idx)
        else:
            self._loading_thumbs = False
            self._gf.update_idletasks()
            self._cv.configure(scrollregion=self._cv.bbox("all"))
            self._prog_lbl.config(text=f"✔  {len(self.thumbs)} image(s) rechargée(s)")
            self.after(3000, lambda: self._prog_lbl.config(text=""))
            # ↓ on passe la hauteur cible explicitement
            target_h = int(self._cfg.get("window_h", self.winfo_height()))
            self.after(50, lambda: self._fit_window_with_height(target_h, animate=False))
            self.after(80, self._restore_marked)

    def _fit_window_with_height(self, target_h, animate=False):
        """Comme _fit_window mais impose une hauteur plutôt que winfo_height()."""
        SASH_W = 5
        sz = self.v_tsize.get()
        cols = self.v_cols.get()

        center_need = cols * (sz + 22) + 12 + 14 + 10
        right_need = self.v_psize.get() + 36

        self.update_idletasks()

        try:
            s0 = self._pane.sash_coord(0)[0]
        except Exception:
            s0 = LEFT_MIN_W

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        target_h = int(target_h)
        target_h = max(560, target_h)
        target_h = min(target_h, max(560, sh - 40))

        win_target = min(max(s0 + center_need + right_need + SASH_W * 2 + 4,
                             LEFT_MIN_W + 300), sw - 40)

        cy = max(0, self.winfo_y())
        cx = max(0, (sw - win_target) // 2)

        self.geometry(f"{win_target}x{target_h}+{cx}+{cy}")
        self.update_idletasks()

        try:
            self._pane.paneconfig(self._cf, minsize=center_need)
            self._pane.paneconfig(self._rf, minsize=right_need)
            self.update_idletasks()
            total = self._pane.winfo_width()
            s1_new = max(s0 + center_need, total - right_need - SASH_W)
            self._pane.sash_place(0, s0, 0)
            self._pane.sash_place(1, s1_new, 0)
        except Exception:
            pass

    # ── Sauvegarde config ─────────────────────────────────────────────────────
    def _save_config_action(self):
        save_config(self._collect_config())
        self._prog_lbl.config(text="✔  Configuration sauvegardée")
        self.after(3000, lambda: self._prog_lbl.config(text=""))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()