#!/usr/bin/env python3
"""
Video Frame Extractor  —  v3.5
Nouveautés v3.5 :

Dépendances : pip install opencv-python Pillow numpy
              ffmpeg requis (brew/apt/winget install ffmpeg)
"""

import os, json, threading, tkinter as tk, subprocess, shutil, tempfile
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk

# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_FILE = "VFE_Config.json"
DEFAULT_CONFIG = {
    "video_path":    "",
    "output_dir":    "",
    "work_dir":      "",
    "generic_name":  "capture",
    "mode":          "count",
    "count_val":     20,
    "interval_val":  30,
    "thumb_size":    150,
    "col_count":     4,
    "preview_size":  280,
    "window_size":   "auto",
    "sash_left":     310,
    "sash_right":    700,
    "confirm_delete":  True,
    "black_filter":    True,
    "mark_key":        "s",
    "marked_files":    [],
    "hdr_tonemap":     "hable",
    "last_video_dir": "",
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                c = DEFAULT_CONFIG.copy()
                c.update(json.load(f))
                return c
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

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

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
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
                 width=130, height=32, font=None, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, **kw)
        self.text=text; self.cmd=command; self.style=style
        self.w=width; self.h=height; self.font=font or F_UI; self._st="normal"
        self._draw()
        self.bind("<Enter>",           self._e_enter)
        self.bind("<Leave>",           self._e_leave)
        self.bind("<ButtonPress-1>",   self._e_press)
        self.bind("<ButtonRelease-1>", self._e_release)
        self.bind("<Configure>",       self._on_resize)
    def _on_resize(self, e): self.w=e.width; self.h=e.height; self._draw()
    def _cols(self):
        n,h,p,ft,fd=self.STYLES.get(self.style,self.STYLES["default"])
        if self._st=="disabled": return C["panel"],fd
        if self._st=="hover":    return h,ft
        if self._st=="pressed":  return p,ft
        return n,ft
    def _draw(self):
        self.delete("all"); bg,fg=self._cols()
        r=7; w,h=self.w,self.h
        if w<14 or h<8: return
        pts=[r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        self.create_polygon(pts,smooth=True,fill=bg,
                            outline=C["border"] if self.style=="default" else "")
        self.create_text(w//2,h//2,text=self.text,fill=fg,font=self.font,anchor="center")
    def _e_enter(self,e):
        if self._st!="disabled": self._st="hover"; self._draw(); self.config(cursor="hand2")
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
    def set_text(self,t): self.text=t; self._draw()


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
                             bg=C["sidebar"],fg=C["t1"],troughcolor=C["input"],
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
        kw.setdefault("bg",C["sidebar"])
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


class HSep(tk.Frame):
    def __init__(self,parent,**kw):
        super().__init__(parent,bg=C["border"],height=1,**kw)

class SectLabel(tk.Label):
    def __init__(self,parent,text,**kw):
        kw.setdefault("bg",C["sidebar"]); kw.setdefault("fg",C["t3"])
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
    s.configure("Vertical.TScrollbar",troughcolor=C["bg"],background=C["border"],
                arrowcolor=C["t3"],bordercolor=C["bg"],darkcolor=C["bg"],
                lightcolor=C["bg"],relief="flat",width=8)
    s.map("Vertical.TScrollbar",background=[("active",C["border2"])])

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
#  Application
# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Frame Extractor  —  v3.5")
        self.configure(bg=C["bg"])
        self._cfg = load_config()
        self._ffmpeg_ok = ffmpeg_available()

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

        self.video_info={}; self.thumbs=[]; self.thumb_refs=[]
        self.thumb_wids={}; self.sel=set(); self.marked=set()
        self._cancel=False; self._prev_ref=None; self._last_click_idx=None
        self._drag_active=False; self._drag_in_zone=False; self._drag_sel_before=set()
        self._hdr_info={}          # résultat detect_hdr() pour la vidéo courante
        self._zscale_ok=None       # cache du test zscale_available()

        self.minsize(LEFT_MIN_W+400,560)
        setup_style(self)
        self._apply_window_size(self.v_winsize.get())
        self._build_ui()
        self._bind_events()
        self.after(80,self._restore_sashes)

        if self.v_path.get() and os.path.exists(self.v_path.get()):
            self._load_video_info(self.v_path.get())
        else:
            self._update_derived()

        if self.v_outdir.get() and os.path.isdir(self.v_outdir.get()):
            self.after(150,self._reload_extraction_folder)

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

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._pane=tk.PanedWindow(self,orient="horizontal",bg=C["bg"],
                                  sashwidth=5,sashrelief="flat",opaqueresize=True)
        self._pane.pack(fill="both",expand=True)
        self._lf=tk.Frame(self._pane,bg=C["sidebar"])
        self._cf=tk.Frame(self._pane,bg=C["bg"])
        self._rf=tk.Frame(self._pane,bg=C["sidebar"])
        self._pane.add(self._lf,minsize=LEFT_MIN_W,sticky="nsew")
        self._pane.add(self._cf,minsize=300,sticky="nsew")
        self._pane.add(self._rf,minsize=180,sticky="nsew")
        self._build_left(); self._build_center(); self._build_right()
        self._statusbar=tk.Label(self,text="",font=F_SMALL,fg=C["t3"],
                                 bg=C["panel"],anchor="w",padx=12,pady=4)
        self._statusbar.pack(side="bottom",fill="x")

    def _build_left(self):
        p=self._lf; p.rowconfigure(1,weight=1); p.columnconfigure(0,weight=1)
        hdr=tk.Frame(p,bg=C["sidebar"])
        hdr.grid(row=0,column=0,sticky="ew",padx=14,pady=(14,4))
        tk.Label(hdr,text="Frame",font=("Segoe UI Light",20),
                 fg=C["t2"],bg=C["sidebar"]).pack(side="left")
        tk.Label(hdr,text="Extractor",font=("Segoe UI Semibold",20),
                 fg=C["accent"],bg=C["sidebar"]).pack(side="left",padx=(4,0))
        tk.Label(hdr,text=" v3.5",font=("Segoe UI",9),
                 fg=C["t3"],bg=C["sidebar"]).pack(side="left",anchor="s",pady=(0,2))

        sc_frame=tk.Frame(p,bg=C["sidebar"])
        sc_frame.grid(row=1,column=0,sticky="nsew")
        sc_frame.rowconfigure(0,weight=1); sc_frame.columnconfigure(0,weight=1)
        sc=tk.Canvas(sc_frame,bg=C["sidebar"],highlightthickness=0)
        sc.grid(row=0,column=0,sticky="nsew")
        vsb=ttk.Scrollbar(sc_frame,orient="vertical",command=sc.yview,
                          style="Vertical.TScrollbar")
        vsb.grid(row=0,column=1,sticky="ns")
        sc.configure(yscrollcommand=vsb.set)
        inner=tk.Frame(sc,bg=C["sidebar"]); win_id=sc.create_window((0,0),window=inner,anchor="nw")
        inner.columnconfigure(0,weight=1)
        inner.bind("<Configure>",lambda e: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>",lambda e: sc.itemconfig(win_id,width=e.width))
        sc.bind("<MouseWheel>",lambda e: sc.yview_scroll(-int(e.delta/120),"units"))
        sc.bind("<Button-4>",lambda e: sc.yview_scroll(-1,"units"))
        sc.bind("<Button-5>",lambda e: sc.yview_scroll(1,"units"))
        self._build_left_content(inner)

        footer=tk.Frame(p,bg=C["sidebar"])
        footer.grid(row=2,column=0,sticky="ew"); footer.columnconfigure(0,weight=1)
        HSep(footer).grid(row=0,column=0,sticky="ew")
        DarkButton(footer,"💾  Sauvegarder la configuration",self._save_config_action,
                   style="ghost",width=240,height=32,font=F_SMALL).grid(row=1,column=0,pady=8)

    def _build_left_content(self, inner):
        PAD=12; row=0

        # Indicateur ffmpeg
        ff_color=C["ok"] if self._ffmpeg_ok else C["danger"]
        ff_text=("✔  ffmpeg détecté — extraction couleurs fidèles"
                 if self._ffmpeg_ok else
                 "⚠  ffmpeg absent — couleurs approximatives\n   Installez ffmpeg !")
        tk.Label(inner,text=ff_text,font=F_SMALL,fg=ff_color,bg=C["sidebar"],
                 anchor="w",padx=14,pady=6,justify="left",wraplength=260
                 ).grid(row=row,column=0,sticky="ew"); row+=1

        # Indicateur HDR
        self._hdr_badge=tk.Label(inner,text="SDR — espace colorimétrique standard",
                                 font=F_SMALL,fg=C["t3"],bg=C["sidebar"],
                                 anchor="w",padx=14,pady=4,justify="left",wraplength=260)
        self._hdr_badge.grid(row=row,column=0,sticky="ew"); row+=1

        # Sélecteur tone mapping (masqué par défaut, visible si HDR détecté)
        self._hdr_tonemap_frame=tk.Frame(inner,bg="#1e1800")
        self._hdr_tonemap_frame.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(0,4))
        self._hdr_tonemap_frame.columnconfigure(0,weight=1)
        self._hdr_tonemap_frame.grid_remove()
        row+=1
        tk.Label(self._hdr_tonemap_frame,text="Tone mapping HDR→SDR :",
                 font=F_SMALL,fg="#ffd54f",bg="#1e1800",anchor="w",padx=4
                 ).grid(row=0,column=0,sticky="w",pady=(4,2))
        tm_row=tk.Frame(self._hdr_tonemap_frame,bg="#1e1800")
        tm_row.grid(row=1,column=0,sticky="w",padx=4,pady=(0,6))
        for algo,label,tip in [
            ("hable",   "Hable",    "Doux, cinématique — recommandé"),
            ("mobius",  "Mobius",   "Équilibré, préserve les couleurs"),
            ("reinhard","Reinhard", "Simple et rapide"),
        ]:
            rb=tk.Radiobutton(tm_row,text=f"{label}",variable=self.v_hdr_tonemap,
                              value=algo,bg="#1e1800",fg="#ffd54f",
                              selectcolor="#332b00",activebackground="#1e1800",
                              activeforeground="#fff",font=F_SMALL,cursor="hand2",
                              indicatoron=1)
            rb.pack(side="left",padx=(0,8))
            Tooltip(rb,lambda t=tip: t)

        tk.Label(self._hdr_tonemap_frame,
                 text="  ℹ  Requiert ffmpeg avec libzimg (zscale).\n"
                      "  Fallback automatique si non disponible.",
                 font=("Segoe UI",8),fg="#a09060",bg="#1e1800",
                 anchor="w",padx=4,justify="left"
                 ).grid(row=2,column=0,sticky="w",pady=(0,4))

        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=4); row+=1

        # Source
        row=self._sect(inner,row,"Fichier source")
        f=tk.Frame(inner,bg=C["sidebar"]); f.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,4))
        f.columnconfigure(0,weight=1); row+=1
        DarkEntry(f,textvariable=self.v_path).grid(row=0,column=0,sticky="ew",ipady=5,padx=(0,6))
        DarkButton(f,"Parcourir",self._pick_video,width=80,height=30).grid(row=0,column=1)
        self._src_name_lbl=tk.Label(inner,text="—",font=F_MONO,fg=C["accent"],
                                    bg=C["sidebar"],anchor="w",padx=14)
        self._src_name_lbl.grid(row=row,column=0,sticky="ew",pady=(0,2)); row+=1
        def _upd_src(*a):
            p=self.v_path.get()
            self._src_name_lbl.config(text=os.path.basename(p) if p else "—")
        self.v_path.trace_add("write",_upd_src); _upd_src()
        self._info_lbl=tk.Label(inner,text="Aucun fichier chargé",font=F_MONO,
                                fg=C["t2"],bg=C["panel"],justify="left",
                                anchor="w",padx=10,pady=8)
        self._info_lbl.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(0,6)); row+=1
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Dossier Extraction
        row=self._sect(inner,row,"Dossier d'Extraction")
        f2=tk.Frame(inner,bg=C["sidebar"]); f2.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6))
        f2.columnconfigure(0,weight=1); row+=1
        DarkEntry(f2,textvariable=self.v_outdir).grid(row=0,column=0,sticky="ew",ipady=5,padx=(0,6))
        DarkButton(f2,"Parcourir",self._pick_output,width=80,height=30).grid(row=0,column=1)
        self._outdir_name_lbl=tk.Label(inner,text="—",font=F_MONO,fg=C["accent"],
                                       bg=C["sidebar"],anchor="w",padx=14)
        self._outdir_name_lbl.grid(row=row,column=0,sticky="ew",pady=(0,2)); row+=1
        def _upd_out(*a):
            p=self.v_outdir.get()
            self._outdir_name_lbl.config(text=os.path.basename(p.rstrip("/\\")) if p else "—" or "—")
        self.v_outdir.trace_add("write",_upd_out); _upd_out()
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Dossier Travail
        row=self._sect(inner,row,"Dossier de Travail")
        f3=tk.Frame(inner,bg=C["sidebar"]); f3.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6))
        f3.columnconfigure(0,weight=1); row+=1
        DarkEntry(f3,textvariable=self.v_workdir).grid(row=0,column=0,sticky="ew",ipady=5,padx=(0,6))
        DarkButton(f3,"Parcourir",self._pick_workdir,width=80,height=30).grid(row=0,column=1)
        self._workdir_name_lbl=tk.Label(inner,text="—",font=F_MONO,fg=C["accent"],
                                        bg=C["sidebar"],anchor="w",padx=14)
        self._workdir_name_lbl.grid(row=row,column=0,sticky="ew",pady=(0,2)); row+=1
        def _upd_wk(*a):
            p=self.v_workdir.get()
            self._workdir_name_lbl.config(text=os.path.basename(p.rstrip("/\\")) if p else "—" or "—")
        self.v_workdir.trace_add("write",_upd_wk); _upd_wk()

        # Nom générique (déplacé ici, sous le dossier de travail)
        row=self._sect(inner,row,"Renommer les fichiers à déplacer")
        nm=tk.Frame(inner,bg=C["sidebar"]); nm.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,4))
        nm.columnconfigure(0,weight=1); row+=1
        DarkEntry(nm,textvariable=self.v_generic).grid(row=0,column=0,sticky="ew",ipady=5,padx=(0,6))
        tk.Label(nm,text="_0001.jpg",font=F_SMALL,fg=C["t3"],bg=C["sidebar"]
                 ).grid(row=0,column=1,sticky="w")

        self._copy_btn=DarkButton(inner,"📋  Déplacer sélection → Dossier de Travail",
                                  self._move_to_workdir,style="accent",
                                  width=240,height=30,font=F_SMALL,bg=C["sidebar"])
        self._copy_btn.grid(row=row,column=0,pady=(4,4),padx=PAD)
        self._copy_btn.set_state("disabled"); row+=1
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Mode capture
        row=self._sect(inner,row,"Mode de capture")
        self._pill=PillSelector(inner,[("Nombre d'images","count"),("Intervalle (s)","interval")],
                                self.v_mode,command=self._on_mode_change,bg=C["sidebar"])
        self._pill.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6)); row+=1
        self._sl_count=DarkSlider(inner,from_=5,to=500,resolution=5,variable=self.v_count,
                                  label="Nombre d'images",unit="images",
                                  command=self._on_slider_change,bg=C["sidebar"])
        self._sl_count.grid(row=row,column=0,sticky="ew",padx=PAD+4,pady=(0,6)); row+=1
        self._sl_intv=DarkSlider(inner,from_=5,to=1800,resolution=5,variable=self.v_intv,
                                 label="Intervalle entre captures",unit="s",
                                 command=self._on_slider_change,bg=C["sidebar"])
        self._sl_intv.grid(row=row,column=0,sticky="ew",padx=PAD+4,pady=(0,6)); row+=1
        self._on_mode_change()

        bf=tk.Frame(inner,bg=C["sidebar"]); bf.grid(row=row,column=0,sticky="w",padx=PAD,pady=(4,0)); row+=1
        tk.Checkbutton(bf,text="Supprimer les frames noires (luminosité < 5/255)",
                       variable=self.v_black_filter,bg=C["sidebar"],fg=C["t2"],
                       selectcolor=C["input"],activebackground=C["sidebar"],
                       activeforeground=C["t1"],font=F_SMALL,anchor="w",
                       cursor="hand2").pack(side="left")
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Taille fenêtre
        row=self._sect(inner,row,"Taille de la fenêtre")
        wf=tk.Frame(inner,bg=C["sidebar"]); wf.grid(row=row,column=0,sticky="w",padx=PAD,pady=(2,10)); row+=1
        self._v_winsize_var=tk.StringVar(value=self.v_winsize.get())
        _saved_ws=self.v_winsize.get()
        _winsize_list=WINDOW_SIZES if _saved_ws in WINDOW_SIZES else WINDOW_SIZES+[_saved_ws]
        self._winsize_combo=RoundedCombo(wf,_winsize_list,self._v_winsize_var,width=120,bg=C["sidebar"])
        self._winsize_combo.pack(side="left")
        DarkButton(wf,"Appliquer",
                   lambda:(self.v_winsize.set(self._v_winsize_var.get()),
                           self._apply_window_size(self._v_winsize_var.get())),
                   width=76,height=28).pack(side="left",padx=(8,0))
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        # Actions
        row=self._sect(inner,row,"Actions")
        act=tk.Frame(inner,bg=C["sidebar"]); act.grid(row=row,column=0,sticky="w",padx=PAD,pady=(4,4)); row+=1
        BTN_W=110; GAP=6; MAIN_W=BTN_W*2+GAP
        self._run_btn=DarkButton(act,"▶  Extraire les frames",self._start_extraction,
                                 style="accent",width=MAIN_W,height=36,font=F_BOLD)
        self._run_btn.grid(row=0,column=0,columnspan=2,pady=(0,5))
        self._cancel_btn=DarkButton(act,"✕  Annuler",self._cancel_extraction,
                                    style="ghost",width=BTN_W,height=30)
        self._cancel_btn.grid(row=1,column=0,padx=(0,GAP)); self._cancel_btn.set_state("disabled")
        self._del_btn=DarkButton(act,"🗑  Supprimer",self._delete_selected,
                                 style="danger",width=BTN_W,height=30)
        self._del_btn.grid(row=1,column=1); self._del_btn.set_state("disabled")
        DarkButton(act,"🗂  Vider le dossier d'extraction",self._clear_output_dir,
                   style="danger",width=MAIN_W,height=30).grid(row=2,column=0,columnspan=2,pady=(5,0))

        chk=tk.Frame(inner,bg=C["sidebar"]); chk.grid(row=row,column=0,sticky="w",padx=PAD,pady=(6,0)); row+=1
        tk.Checkbutton(chk,text="Demander confirmation avant suppression",
                       variable=self.v_confirm_del,bg=C["sidebar"],fg=C["t2"],
                       selectcolor=C["input"],activebackground=C["sidebar"],
                       activeforeground=C["t1"],font=F_SMALL,anchor="w",
                       cursor="hand2").pack(side="left")
        self._prog=DarkProgress(inner,height=4,bg=C["sidebar"])
        self._prog.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(8,2)); row+=1
        self._prog_lbl=tk.Label(inner,text="",font=F_SMALL,fg=C["t3"],
                                bg=C["sidebar"],anchor="w")
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
        vsb=ttk.Scrollbar(cf2,orient="vertical",command=self._cv.yview,
                          style="Vertical.TScrollbar")
        vsb.grid(row=0,column=1,sticky="ns")
        self._cv.configure(yscrollcommand=vsb.set)
        self._gf=tk.Frame(self._cv,bg=C["thumb_bg"],padx=6,pady=8)
        self._gwin=self._cv.create_window((0,0),window=self._gf,anchor="nw")
        self._gf.bind("<Configure>",lambda e: self._cv.configure(scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>",lambda e: self._cv.itemconfig(self._gwin,width=e.width))
        self._cv.bind("<MouseWheel>",self._scroll)
        self._cv.bind("<Button-4>",  self._scroll)
        self._cv.bind("<Button-5>",  self._scroll)
        self._cv.bind("<Button-1>",  lambda e: self.focus_set(),add="+")
        for widget in (self._cv,self._gf):
            widget.bind("<ButtonPress-1>",  self._drag_start)
            widget.bind("<B1-Motion>",      self._drag_motion)
            widget.bind("<ButtonRelease-1>",self._drag_end)

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
                                 fg=C["t3"],bg=C["sidebar"],justify="left",padx=14,pady=8)
        self._prev_info.grid(row=3,column=0,sticky="w")
        HSep(r).grid(row=4,column=0,sticky="ew",padx=8)
        pf=tk.Frame(r,bg=C["sidebar"]); pf.grid(row=5,column=0,sticky="ew",padx=12,pady=(6,10))
        tk.Label(pf,text="Taille :",font=F_SMALL,fg=C["t3"],bg=C["sidebar"]).pack(side="left")
        self._v_psize_var=tk.StringVar(value=str(self.v_psize.get()))
        RoundedCombo(pf,["150","200","250","300","350","400","450","500","550","600","650"],
                     self._v_psize_var,width=80,bg=C["sidebar"]).pack(side="left",padx=(8,0))
        tk.Label(pf,text="px",font=F_SMALL,fg=C["t3"],bg=C["sidebar"]).pack(side="left",padx=(5,0))
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

    def _global_click_deselect(self,event):
        if not self.sel: return
        w=event.widget
        KEEP=(tk.Entry,DarkEntry,DarkButton,tk.Scale,tk.Checkbutton,
              ttk.Scrollbar,tk.Scrollbar,tk.Menu,PillSelector,RoundedCombo)
        if isinstance(w,KEEP): return
        xr,yr=event.x_root,event.y_root
        for wdata in self.thumb_wids.values():
            cell=wdata["frame"]
            try:
                if not cell.winfo_exists(): continue
                if (cell.winfo_rootx()<=xr<=cell.winfo_rootx()+cell.winfo_width() and
                    cell.winfo_rooty()<=yr<=cell.winfo_rooty()+cell.winfo_height()):
                    return
            except Exception: pass
        for i in list(self.sel): self._set_sel(i,False)
        self.sel.clear(); self._upd_badges()
        self._last_click_idx=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")

    def _rebind_mark_key(self):
        if self._mark_binding_id:
            try: self.unbind(self._mark_binding_id[0],self._mark_binding_id[1])
            except Exception: pass
        key=self.v_mark_key.get().strip()
        if not key: return
        bid=self.bind(f"<KeyPress-{key}>",self._on_mark_key,add=True)
        self._mark_binding_id=(f"<KeyPress-{key}>",bid)

    def _scroll_universal(self,e):
        wx=self._cv.winfo_rootx(); wy=self._cv.winfo_rooty()
        if wx<=e.x_root<=wx+self._cv.winfo_width() and wy<=e.y_root<=wy+self._cv.winfo_height():
            if e.num==4:   self._cv.yview_scroll(-1,"units")
            elif e.num==5: self._cv.yview_scroll(1,"units")
            elif hasattr(e,"delta") and e.delta: self._cv.yview_scroll(-int(e.delta/120),"units")

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
        p=filedialog.askdirectory(title="Dossier d'Extraction")
        if p: self.v_outdir.set(p)

    def _pick_workdir(self):
        p=filedialog.askdirectory(title="Dossier de Travail")
        if p: self.v_workdir.set(p)

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

    # ── HDR ───────────────────────────────────────────────────────────────────
    def _detect_hdr_async(self, path):
        """Lance detect_hdr() en thread, puis met à jour l'UI."""
        hdr = detect_hdr(path)
        self._hdr_info = hdr
        self.after(0, self._update_hdr_indicator, hdr)

    def _update_hdr_indicator(self, hdr):
        """Met à jour le bandeau HDR dans la sidebar."""
        if hdr.get("is_hdr"):
            tf  = hdr.get("transfer","")
            prim= hdr.get("primaries","")
            label = "HDR"
            if "2084" in tf or "pq" in tf:   label = "HDR10 (PQ)"
            elif "hlg" in tf or "arib" in tf: label = "HDR HLG"
            self._hdr_badge.config(
                text=f"🌟  {label} détecté — pipeline HDR→SDR actif",
                fg="#ffd54f", bg="#2a2200")
            self._hdr_tonemap_frame.grid()   # affiche le sélecteur
        else:
            self._hdr_badge.config(
                text="SDR — espace colorimétrique standard",
                fg=C["t3"], bg=C["sidebar"])
            self._hdr_tonemap_frame.grid_remove()

    # ── Options affichage ─────────────────────────────────────────────────────
    def _on_tsize_change(self,*a):
        try: self.v_tsize.set(int(self._v_tsize_var.get()))
        except: pass
        self._rebuild_grid(); self._fit_window(animate=True)

    def _on_cols_change(self,*a):
        try: self.v_cols.set(int(self._v_cols_var.get()))
        except: pass
        self._rebuild_grid(); self._fit_window(animate=True)

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
        if not self.v_path.get():
            messagebox.showwarning("Attention","Veuillez choisir une vidéo."); return
        if not self.v_outdir.get():
            messagebox.showwarning("Attention","Veuillez choisir un dossier."); return
        if not self.video_info:
            messagebox.showwarning("Attention","Informations vidéo non chargées."); return
        targets=self._compute_targets()
        if not targets: messagebox.showinfo("Info","Aucune frame à extraire."); return

        self.thumbs.clear(); self.thumb_refs.clear()
        self.thumb_wids.clear(); self.sel.clear(); self.marked.clear()
        self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Extraction en cours…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._run_btn.set_state("disabled")
        self._cancel_btn.set_state("normal"); self._cancel=False
        self._prog.set(0); self._prog_lbl.config(text="Initialisation…")

        threading.Thread(target=self._worker,
                         args=(self.v_path.get(),self.v_outdir.get(),targets),
                         daemon=True).start()

    def _cancel_extraction(self):
        self._cancel=True; self._cancel_btn.set_state("disabled")
        self._prog_lbl.config(text="Annulation…")

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
        tot=len(targets)
        info=self.video_info
        disp_w=info.get("disp_w",info["width"])
        disp_h=info.get("disp_h",info["height"])
        sar_applied=info.get("sar_applied",False)
        do_filter=self.v_black_filter.get()
        base=os.path.splitext(os.path.basename(vpath))[0]
        saved=0

        # Paramètres HDR
        hdr_info   = self._hdr_info
        is_hdr     = hdr_info.get("is_hdr", False)
        tonemap    = self.v_hdr_tonemap.get()

        # Test zscale une seule fois par extraction
        if is_hdr and self._zscale_ok is None:
            self._zscale_ok = zscale_available()

        for i,t in enumerate(targets):
            if self._cancel: break

            tmp_fd,tmp_path=tempfile.mkstemp(suffix=".jpg",prefix="vfe_")
            os.close(tmp_fd)
            try: os.remove(tmp_path)
            except Exception: pass

            ok=False

            if is_hdr:
                # ── Pipeline HDR→SDR ──────────────────────────────────────
                if self._zscale_ok:
                    cmd=build_ffmpeg_cmd_hdr(vpath,t,tmp_path,disp_w,disp_h,
                                             sar_applied,hdr_info,tonemap)
                    try:
                        r=subprocess.run(cmd,capture_output=True,timeout=60)
                        ok=(r.returncode==0 and os.path.exists(tmp_path)
                            and os.path.getsize(tmp_path)>0)
                    except Exception: pass

                if not ok:
                    # Fallback HDR sans zscale (colorspace filter)
                    cmd2=build_ffmpeg_cmd_hdr_fallback(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    try:
                        r2=subprocess.run(cmd2,capture_output=True,timeout=60)
                        ok=(r2.returncode==0 and os.path.exists(tmp_path)
                            and os.path.getsize(tmp_path)>0)
                    except Exception: pass

                if not ok:
                    # Dernier recours : commande SDR standard
                    cmd3=build_ffmpeg_cmd(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    try:
                        r3=subprocess.run(cmd3,capture_output=True,timeout=30)
                        ok=(r3.returncode==0 and os.path.exists(tmp_path)
                            and os.path.getsize(tmp_path)>0)
                    except Exception: pass

            else:
                # ── Pipeline SDR standard (identique v2.9) ────────────────
                cmd=build_ffmpeg_cmd(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                try:
                    r=subprocess.run(cmd,capture_output=True,timeout=30)
                    ok=(r.returncode==0 and os.path.exists(tmp_path)
                        and os.path.getsize(tmp_path)>0)
                except Exception: pass

                if not ok:
                    cmd2=build_ffmpeg_cmd_fallback(vpath,t,tmp_path,disp_w,disp_h,sar_applied)
                    try:
                        r2=subprocess.run(cmd2,capture_output=True,timeout=30)
                        ok=(r2.returncode==0 and os.path.exists(tmp_path)
                            and os.path.getsize(tmp_path)>0)
                    except Exception: pass

            pct=(i+1)/tot*100
            if not ok:
                try: os.remove(tmp_path)
                except Exception: pass
                continue

            # Relire avec Pillow
            try:
                img=Image.open(tmp_path).copy()
            except Exception:
                try: os.remove(tmp_path)
                except Exception: pass
                continue

            # Filtre frame noire
            if do_filter:
                arr=np.array(img)
                if is_black_frame(arr,threshold=5):
                    black_tcs.append(t)
                    try: os.remove(tmp_path)
                    except Exception: pass
                    self.after(0,self._black_skipped,t,i+1,tot,pct)
                    continue

            # Déplacement vers dossier de sortie
            saved+=1
            fname=f"{base}_{saved:04d}_{tc_str(t)}.jpg"
            fpath=os.path.join(outdir,fname)
            try:
                shutil.move(tmp_path,fpath)
            except Exception:
                try: os.remove(tmp_path)
                except Exception: pass
                continue

            self.after(0,self._frame_done,img,fpath,t,i+1,tot,pct)

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
        saved=0
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
            saved+=1
            fname=f"{base}_{saved:04d}_{tc_str(t)}.jpg"
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

    def _frame_done(self,img,fpath,t,done,tot,pct):
        self.thumbs.append({"img":img,"path":fpath,"tc":t})
        idx=len(self.thumbs)-1
        self._prog.set(pct); self._prog_lbl.config(text=f"{done}/{tot}  ·  {hms(t)}")
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._add_thumb(idx)

    def _extract_done(self,black_tcs=None):
        self._run_btn.set_state("normal"); self._cancel_btn.set_state("disabled")
        n=len(self.thumbs); nb=len(black_tcs) if black_tcs else 0
        if self._cancel: self._prog_lbl.config(text=f"Annulé · {n} image(s) sauvegardée(s)")
        else: self._prog.set(100); self._prog_lbl.config(text=f"✔  Terminé · {n} image(s)")
        self._prev_info.config(text="Cliquez sur une\nvignette…" if n else "Aucune image extraite.")
        if nb>0:
            self._status(f"🔲  {nb} frame(s) noire(s) :  "+"  |  ".join(hms(t) for t in black_tcs),duration=0)
        elif black_tcs is not None and self.v_black_filter.get():
            self._status("✔  Aucune frame noire détectée.",duration=6000)

    # ── Grille vignettes ──────────────────────────────────────────────────────
    def _add_thumb(self,idx):
        entry=self.thumbs[idx]; sz=self.v_tsize.get(); cols=self.v_cols.get()
        th=entry["img"].copy(); th.thumbnail((sz,sz),Image.LANCZOS)
        imgtk=ImageTk.PhotoImage(th); self.thumb_refs.append(imgtk)
        ri,ci=divmod(idx,cols)
        cell=tk.Frame(self._gf,bg=C["thumb_bg"],padx=4,pady=4,cursor="hand2")
        cell.grid(row=ri,column=ci,padx=5,pady=5)
        lbl=tk.Label(cell,image=imgtk,bg=C["thumb_bg"],bd=0,relief="flat",
                     cursor="hand2",highlightthickness=2,
                     highlightbackground=C["thumb_bg"],highlightcolor=C["thumb_bg"])
        lbl.image=imgtk; lbl.pack()
        tclbl=tk.Label(cell,text=hms(entry["tc"]),font=("Segoe UI",8),
                       fg=C["t3"],bg=C["thumb_bg"]); tclbl.pack()
        app=self
        for w in (cell,lbl,tclbl):
            w.bind("<ButtonPress-1>",lambda e,i=idx,a=app:(a.focus_set(),a._drag_start_from_thumb(e)))
            w.bind("<Button-1>",lambda e,i=idx,a=app: a._thumb_click(i),add="+")
            w.bind("<Control-Button-1>",lambda e,i=idx,a=app:(a.focus_set(),a._ctrl_click(i)))
            w.bind("<Shift-Button-1>",lambda e,i=idx,a=app:(a.focus_set(),a._shift_click(i)))
            w.bind("<B1-Motion>",lambda e,a=app: a._drag_motion_from_thumb(e))
            w.bind("<ButtonRelease-1>",lambda e,a=app: a._drag_end_from_thumb(e))
            w.bind("<Enter>",lambda e,c=cell,i=idx,a=app: a._thumb_hover(c,i,True))
            w.bind("<Leave>",lambda e,c=cell,i=idx,a=app: a._thumb_hover(c,i,False))
        self.thumb_wids[idx]={"frame":cell,"label":lbl,"tc_lbl":tclbl}
        self._adjust_center_width()

    # ── Redimensionnement ─────────────────────────────────────────────────────
    _fit_job=None
    def _fit_window(self,animate=True):
        SASH_W=5; sz=self.v_tsize.get(); cols=self.v_cols.get()
        center_need=cols*(sz+22)+12+14+10; right_need=self.v_psize.get()+36
        self.update_idletasks()
        try: s0=self._pane.sash_coord(0)[0]
        except Exception: s0=LEFT_MIN_W
        sw=self.winfo_screenwidth()
        win_target=min(max(s0+center_need+right_need+SASH_W*2+4,LEFT_MIN_W+300),sw-40)
        cy=self.winfo_y()
        def _apply(w):
            cx=max(0,(sw-w)//2)
            self.geometry(f"{w}x{self.winfo_height()}+{cx}+{cy}")
            self.update_idletasks()
            try:
                total=self._pane.winfo_width()
                s1_new=max(s0+center_need,total-right_need-SASH_W)
                self._pane.sash_place(1,s1_new,0)
                self._pane.paneconfig(self._rf,minsize=right_need)
                self._pane.paneconfig(self._cf,minsize=center_need)
            except Exception: pass
        if not animate: _apply(win_target); return
        w_start=self.winfo_width(); delta=win_target-w_start
        if abs(delta)<4: _apply(win_target); return
        if self._fit_job: self.after_cancel(self._fit_job); self._fit_job=None
        def _step(i):
            t=i/8; ease=t*(2-t); _apply(int(w_start+delta*ease))
            if i<8: self._fit_job=self.after(15,_step,i+1)
            else:   self._fit_job=None; _apply(win_target)
        _step(1)

    def _adjust_center_width(self): self._fit_window(animate=False)

    def _clear_grid(self):
        for w in self._gf.winfo_children(): w.destroy()
        self.thumb_refs.clear(); self.thumb_wids.clear()

    def _rebuild_grid(self):
        self._clear_grid()
        for i in range(len(self.thumbs)): self._add_thumb(i)
        for i in self.sel:    self._set_sel(i,True)
        for i in self.marked: self._update_mark_overlay(i)
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        self._adjust_center_width()

    # ── Sélection ─────────────────────────────────────────────────────────────
    def _thumb_hover(self,cell,idx,on):
        try:
            if not cell.winfo_exists() or idx in self.sel: return
            bg=C["thumb_hov"] if on else C["thumb_bg"]; cell.config(bg=bg)
            for ch in cell.winfo_children():
                try: ch.config(bg=bg)
                except Exception: pass
        except Exception: pass

    def _thumb_click(self,idx): self._click(idx)

    def _click(self,idx):
        if idx in self.sel:
            self._set_sel(idx,False); self.sel.discard(idx); self._upd_badges()
            if len(self.sel)==1: self._show_preview(next(iter(self.sel))); self._last_click_idx=next(iter(self.sel))
            elif len(self.sel)==0: self._last_click_idx=None; self._prev_info.config(text="Cliquez sur une\nvignette…")
            return
        for i in list(self.sel): self._set_sel(i,False)
        self.sel.clear(); self.sel.add(idx); self._set_sel(idx,True)
        self._last_click_idx=idx; self._upd_badges(); self._show_preview(idx)

    def _ctrl_click(self,idx):
        if idx in self.sel: self.sel.discard(idx); self._set_sel(idx,False)
        else:               self.sel.add(idx);     self._set_sel(idx,True)
        self._upd_badges()
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        elif len(self.sel)>1:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _shift_click(self,idx):
        anchor=self._last_click_idx
        if anchor is None: self._click(idx); return
        lo,hi=min(anchor,idx),max(anchor,idx)
        for i in list(self.sel): self._set_sel(i,False)
        self.sel.clear()
        for i in range(lo,hi+1): self.sel.add(i); self._set_sel(i,True)
        self._upd_badges()
        if len(self.sel)==1: self._show_preview(next(iter(self.sel)))
        else:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _set_sel(self,idx,on):
        if idx not in self.thumb_wids: return
        w=self.thumb_wids[idx]
        bg=C["thumb_sel"] if on else C["thumb_bg"]; brd=C["sel_brd"] if on else C["thumb_bg"]
        w["frame"].config(bg=bg)
        w["label"].config(bg=bg,highlightthickness=2,highlightbackground=brd,highlightcolor=brd)
        w["tc_lbl"].config(bg=bg)
        sync=w.get("mark_sync")
        if sync:
            try: sync(on)
            except Exception: pass

    def _upd_badges(self):
        n=len(self.sel)
        self._badge_sel.config(text=f"{n} sélectionnée(s)" if n else "")
        self._del_btn.set_state("normal" if n else "disabled")
        self._copy_btn.set_state("normal" if n else "disabled")

    # ── Suppression ───────────────────────────────────────────────────────────
    def _delete_selected(self):
        if not self.sel: return
        n=len(self.sel)
        if self.v_confirm_del.get():
            if not messagebox.askyesno("Supprimer",
                    f"Supprimer {n} image(s) sélectionnée(s) ?\nLes fichiers JPG seront supprimés."): return
        marked_paths={self.thumbs[i]["path"] for i in self.marked if i<len(self.thumbs)}
        for idx in sorted(self.sel,reverse=True):
            entry=self.thumbs[idx]
            try:
                if os.path.exists(entry["path"]): os.remove(entry["path"])
            except Exception as ex:
                messagebox.showwarning("Erreur",f"Impossible de supprimer :\n{entry['path']}\n{ex}")
            self.thumbs.pop(idx)
        self.sel.clear()
        self.marked={i for i,e in enumerate(self.thumbs) if e["path"] in marked_paths}
        self._upd_badges(); self._upd_marked_badge()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._rebuild_grid(); self._auto_save_config()

    def _clear_output_dir(self):
        outdir=self.v_outdir.get()
        if not outdir: messagebox.showwarning("Attention","Aucun dossier cible défini."); return
        if not os.path.isdir(outdir): messagebox.showwarning("Attention","Le dossier n'existe pas."); return
        jpgs=[f for f in os.listdir(outdir) if f.lower().endswith((".jpg",".jpeg"))]
        if not jpgs: messagebox.showinfo("Info","Le dossier est déjà vide."); return
        if self.v_confirm_del.get():
            if not messagebox.askyesno("Vider",f"Supprimer {len(jpgs)} fichier(s) JPG ?\nIrréversible."): return
        errors=[]
        for f in jpgs:
            try: os.remove(os.path.join(outdir,f))
            except Exception as ex: errors.append(f"{f}:{ex}")
        if errors: messagebox.showwarning("Erreurs","\n".join(errors))
        self.thumbs.clear(); self.thumb_refs.clear(); self.thumb_wids.clear()
        self.sel.clear(); self.marked.clear(); self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._prog.set(0)
        self._prog_lbl.config(text=f"✔  {len(jpgs)-len(errors)} fichier(s) supprimé(s)")

    # ── Drag-select ───────────────────────────────────────────────────────────
    def _drag_start(self,event):
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
            for i in list(self.sel): self._set_sel(i,False)
            self.sel.clear()
        self._do_drag(event.x_root,event.y_root,ox_cv,oy_cv)

    def _drag_motion_from_thumb(self,event):
        if not self._drag_in_zone: return
        ox_r,oy_r=self._drag_origin_root; ox_cv,oy_cv=self._drag_origin_cv
        if not self._drag_active:
            if abs(event.x_root-ox_r)<5 and abs(event.y_root-oy_r)<5: return
            self._drag_active=True
            for i in list(self.sel): self._set_sel(i,False)
            self.sel.clear()
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
        for idx,w in self.thumb_wids.items():
            cell=w["frame"]
            try:
                if not cell.winfo_exists(): continue
                cx0=cell.winfo_x()+gx; cy0=cell.winfo_y()+gy
                cw=cell.winfo_width(); ch=cell.winfo_height()
                if cx0<x2 and cx0+cw>x1 and cy0<y2 and cy0+ch>y1: new_sel.add(idx)
            except Exception: pass
        for i in new_sel-self.sel:  self.sel.add(i);    self._set_sel(i,True)
        for i in self.sel-new_sel:  self.sel.discard(i);self._set_sel(i,False)
        self._upd_badges()
        if len(self.sel)>1:
            self._prev_lbl.config(image=""); self._prev_ref=None
            self._prev_info.config(text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")

    def _drag_end(self,event): self._finish_drag(event)
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
            for i in list(self.sel): self._set_sel(i,False)
            self.sel.clear(); self._upd_badges(); self._last_click_idx=None
            self._prev_info.config(text="Cliquez sur une\nvignette…")

    # ── Marquage ──────────────────────────────────────────────────────────────
    def _on_mark_key(self,event):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,DarkEntry)): return
        if not self.sel: return
        if self.sel.issubset(self.marked):
            for idx in list(self.sel): self.marked.discard(idx); self._update_mark_overlay(idx)
        else:
            for idx in self.sel: self.marked.add(idx); self._update_mark_overlay(idx)
        self._upd_marked_badge(); self._auto_save_config()

    def _update_mark_overlay(self,idx):
        if idx not in self.thumb_wids: return
        w=self.thumb_wids[idx]; cell=w["frame"]; lbl=w["label"]; marked=idx in self.marked
        ov=w.get("mark_overlay")
        if ov:
            try: ov.destroy()
            except Exception: pass
            w["mark_overlay"]=None
        if not marked: return
        SIDE=22
        ov=tk.Canvas(cell,width=SIDE,height=SIDE,
                     bg=C["thumb_sel"] if idx in self.sel else C["thumb_bg"],
                     highlightthickness=0)
        r=5
        pts=[r,1,SIDE-r,1,SIDE-1,1,SIDE-1,r,SIDE-1,SIDE-r,SIDE-1,SIDE-1,
             SIDE-r,SIDE-1,r,SIDE-1,1,SIDE-1,1,SIDE-r,1,r,1,1]
        ov.create_polygon(pts,smooth=True,fill="#1a6b3a",outline="#14532d")
        m=SIDE//2
        ov.create_line(4,m,8,SIDE-5,fill="white",width=2,capstyle="round",joinstyle="round")
        ov.create_line(8,SIDE-5,SIDE-4,5,fill="white",width=2,capstyle="round",joinstyle="round")
        w["mark_overlay"]=ov
        def _place(e=None,_ov=ov,_lbl=lbl,_SIDE=SIDE):
            try:
                if not _ov.winfo_exists() or not _lbl.winfo_exists(): return
                _ov.place(x=_lbl.winfo_x()+_lbl.winfo_width()-_SIDE-2,y=_lbl.winfo_y()+2)
                _ov.lift()
            except Exception: pass
        lbl.bind("<Configure>",_place,add="+"); cell.bind("<Configure>",_place,add="+")
        self.after(10,_place)
        ov.bind("<Button-1>",lambda e,i=idx: self._toggle_mark(i))
        def _sync(on,_ov=ov,_idx=idx):
            try:
                if not _ov.winfo_exists(): return
                _ov.config(bg=C["thumb_sel"] if _idx in self.sel else C["thumb_bg"])
            except Exception: pass
        w["mark_sync"]=_sync

    def _toggle_mark(self,idx):
        if idx in self.marked: self.marked.discard(idx)
        else: self.marked.add(idx)
        self._update_mark_overlay(idx); self._upd_marked_badge(); self._auto_save_config()

    def _unmark_all(self):
        for idx in list(self.marked): self.marked.discard(idx); self._update_mark_overlay(idx)
        self._upd_marked_badge(); self._auto_save_config()

    def _mark_selection(self):
        if not self.sel: self._status("⚠  Aucune image sélectionnée."); return
        for idx in list(self.sel): self.marked.add(idx); self._update_mark_overlay(idx)
        self._upd_marked_badge(); self._auto_save_config()

    def _upd_marked_badge(self):
        n=len(self.marked)
        self._badge_marked.config(text=f"✓ {n} marquée(s)" if n else "")

    def _auto_save_config(self):
        s0,s1=self._get_sash_positions()
        save_config({
            "video_path":self.v_path.get(),
            "output_dir":self.v_outdir.get(),                     
            "work_dir":self.v_workdir.get(),
            "generic_name":self.v_generic.get(),
            "mode":self.v_mode.get(),
            "count_val":self.v_count.get(),
            "interval_val":self.v_intv.get(),"thumb_size":self.v_tsize.get(),
            "col_count":self.v_cols.get(),"preview_size":self.v_psize.get(),
            "window_size":self.v_winsize.get(),"sash_left":s0,"sash_right":s1,
            "confirm_delete":self.v_confirm_del.get(),"black_filter":self.v_black_filter.get(),
            "mark_key":self.v_mark_key.get(),"hdr_tonemap":self.v_hdr_tonemap.get(),
            "last_video_dir": self._cfg.get("last_video_dir", ""),
            "marked_files":[self.thumbs[i]["path"]            
                            for i in sorted(self.marked) if i<len(self.thumbs)]
        })

    def _restore_marked(self):
        saved=set(self._cfg.get("marked_files",[]))
        if not saved: return
        for idx,entry in enumerate(self.thumbs):
            if entry["path"] in saved: self.marked.add(idx); self._update_mark_overlay(idx)
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
        combined=self.sel|self.marked
        if not combined: self._status("⚠  Aucune image sélectionnée ni marquée."); return
        workdir=self.v_workdir.get().strip()
        if not workdir: self._status("⚠  Dossier de Travail non défini."); return
        if not os.path.isdir(workdir): self._status(f"⚠  Dossier introuvable : {workdir}"); return
        generic=self.v_generic.get().strip() or "capture"
        indices=sorted(combined); n=len(indices); num=self._next_num_in_workdir(workdir,generic)
        moves=[]
        for idx in indices:
            src=self.thumbs[idx]["path"]
            while True:
                digits=2 if num<100 else 3
                dst=os.path.join(workdir,f"{generic}_{num:0{digits}d}.jpg")
                if not os.path.exists(dst): break
                num+=1
            moves.append((src,dst,idx)); num+=1
        ok=0; errors=[]; moved=[]
        for src,dst,idx in moves:
            try: shutil.move(src,dst); ok+=1; moved.append(idx)
            except Exception as ex: errors.append(f"{os.path.basename(src)} → {ex}")
        if errors: messagebox.showwarning("Erreurs","\n".join(errors))
        moved_paths={self.thumbs[i]["path"] for i in moved if i<len(self.thumbs)}
        marked_paths={self.thumbs[i]["path"] for i in self.marked if i<len(self.thumbs)}-moved_paths
        for idx in sorted(moved,reverse=True): self.thumbs.pop(idx)
        self.sel.clear()
        self.marked={i for i,e in enumerate(self.thumbs) if e["path"] in marked_paths}
        self._upd_badges(); self._upd_marked_badge()
        self._prev_lbl.config(image=""); self._prev_ref=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._rebuild_grid(); self._auto_save_config()
        msg=f"✔  {ok}/{n} image(s) déplacée(s) vers {os.path.basename(workdir)}"
        if errors: msg+=f"  ({len(errors)} erreur(s))"
        self._status(msg,duration=6000)

    # ── Aperçu ────────────────────────────────────────────────────────────────
    def _show_preview(self,idx):
        if idx is None or idx>=len(self.thumbs): return
        entry=self.thumbs[idx]; sz=self.v_psize.get()
        p=entry["img"].copy(); p.thumbnail((sz,sz),Image.LANCZOS)
        imgtk=ImageTk.PhotoImage(p); self._prev_ref=imgtk; self._prev_lbl.config(image=imgtk)
        ow,oh=entry["img"].size
        self._prev_info.config(
            text=f"{os.path.basename(entry['path'])}\n\n"
                 f"⏱  {hms(entry['tc'])}\n📐  {ow}×{oh} px\n#{idx+1} / {len(self.thumbs)}")

    # ── Rechargement dossier ──────────────────────────────────────────────────
    def _reload_extraction_folder(self):
        outdir=self.v_outdir.get()
        if not outdir or not os.path.isdir(outdir): return
        jpgs=sorted([f for f in os.listdir(outdir) if f.lower().endswith((".jpg",".jpeg"))],key=str.lower)
        if not jpgs: return
        self.thumbs.clear(); self.thumb_refs.clear(); self.thumb_wids.clear()
        self.sel.clear(); self.marked.clear(); self._upd_marked_badge(); self._clear_grid()
        self._prog_lbl.config(text=f"Chargement de {len(jpgs)} image(s)…")
        def _load():
            loaded=[]
            for fname in jpgs:
                fpath=os.path.join(outdir,fname)
                try: loaded.append((Image.open(fpath).copy(),fpath,_parse_tc_from_filename(fname)))
                except Exception: pass
            self.after(0,self._reload_done,loaded)
        threading.Thread(target=_load,daemon=True).start()

    def _refresh_folder(self):
        """Relance le chargement des images depuis le dossier d'extraction."""
        outdir = self.v_outdir.get()
        if not outdir or not os.path.isdir(outdir):
            self._status("⚠  Aucun dossier d'extraction défini ou inexistant.", duration=4000)
            return
        self._status("🔁 Rafraîchissement en cours…", duration=0)
        self._reload_extraction_folder()

    def _reload_done(self,loaded):
        for img,fpath,tc in loaded: self.thumbs.append({"img":img,"path":fpath,"tc":tc})
        for i in range(len(self.thumbs)): self._add_thumb(i)
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
        self._prog_lbl.config(text=f"✔  {len(self.thumbs)} image(s) rechargée(s)")
        self.after(3000,lambda: self._prog_lbl.config(text=""))
        self.after(50,  lambda: self._fit_window(animate=False))
        self.after(80,  self._restore_marked)

    # ── Sauvegarde config ─────────────────────────────────────────────────────
    def _save_config_action(self):
        s0,s1=self._get_sash_positions()
        save_config({
            "video_path":self.v_path.get(),
            "output_dir":self.v_outdir.get(),                     
            "work_dir":self.v_workdir.get(),
            "generic_name":self.v_generic.get(),
            "mode":self.v_mode.get(),
            "count_val":self.v_count.get(),
            "interval_val":self.v_intv.get(),
            "thumb_size":self.v_tsize.get(),
            "col_count":self.v_cols.get(),
            "preview_size":self.v_psize.get(),
            "window_size":self.v_winsize.get(),
            "sash_left":s0,"sash_right":s1,
            "confirm_delete":self.v_confirm_del.get(),
            "black_filter":self.v_black_filter.get(),
            "mark_key":self.v_mark_key.get(),
            "hdr_tonemap":self.v_hdr_tonemap.get(),
            "last_video_dir": self._cfg.get("last_video_dir", ""),
            "marked_files":[self.thumbs[i]["path"]
                            for i in sorted(self.marked) if i<len(self.thumbs)]
        })
        self._prog_lbl.config(text="✔  Configuration sauvegardée")
        self.after(3000,lambda: self._prog_lbl.config(text=""))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()