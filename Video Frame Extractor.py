#!/usr/bin/env python3
"""
Video Frame Extractor  —  v4.5
Nouveautés v4.5 : identité des images par chemin (plus d'indices) —
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
from collections import OrderedDict
# ── Modules extraits (refactor A1) ──────────────────────────────────────────
from vfe_config import (CONFIG_FILE, AppConfig, DEFAULT_CONFIG,
                        load_config, save_config, _coerce_config)
from vfe_utils import (hms, tc_str, dir_parent_label,
                       _parse_tc_from_filename, is_black_frame)
from vfe_ffmpeg import (ffmpeg_available, get_display_size, detect_hdr,
                         zscale_available, build_ffmpeg_cmd,
                         build_ffmpeg_cmd_fallback, build_ffmpeg_cmd_hdr,
                         build_ffmpeg_cmd_hdr_fallback,
                         run_ffmpeg, tmp_ok)
from vfe_plan import compute_targets
from vfe_widgets import (C, F_HEAD, F_TITLE, F_UI, F_BOLD, F_SMALL, F_MONO, F_SECT,
                         DarkButton, PillSelector, DarkSlider, RoundedCombo,
                         DarkEntry, DarkProgress, ModernScrollbar, HSep,
                         SectLabel, Tooltip, setup_style)
from vfe_grid import VirtualThumbGrid
from vfe_workers import detect_limited_range_opencv, expand_limited_range
try:
    from send2trash import send2trash          # v4.4 : suppression vers la corbeille
    _TRASH_OK = True
except ImportError:
    send2trash = None
    _TRASH_OK = False

# ── Journal (v4.5) ───────────────────────────────────────────────────────────
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(_APP_DIR, "VFE_Log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=512*1024,
                                  backupCount=2, encoding="utf-8")],
)
log = logging.getLogger("vfe")

# ─────────────────────────────────────────────────────────────────────────────
#  Constantes applicatives
# ─────────────────────────────────────────────────────────────────────────────
APP_VERSION  = "4.5"
LEFT_MIN_W   = 300
WINDOW_SIZES = ["auto", "1920x1200", "1920x1080", "1280x800", "1280x720"]
FFMPEG_WORKERS = 3

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
#  Application
# ─────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Video Frame Extractor  —  v{APP_VERSION}")
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

        self.video_info={}; self.thumbs=[]      # v4 : refs PhotoImage par chemin
        self.thumb_by_path={}                                       # v4 : accès O(1) par chemin
        self.sel=set(); self.marked=set()       # v4 : sets de CHEMINS
        self._cancel=False; self._prev_ref=None; self._last_click_path=None
        self._preview_path=None   # dernier chemin affiché dans l'aperçu (survit à _global_click_deselect)
        self._extracting=False; self._failed_frames=[]    # U1 : couples (index_plan, timecode) des échecs
        self._hdr_info={}          # résultat detect_hdr() pour la vidéo courante
        self._zscale_ok=None       # cache du test zscale_available()
        self._hdr_detect_done=threading.Event()   # v4.8 (point 9)
        self._hdr_detect_done.set()               # prêt tant qu'aucune détection n'est en cours

        self.minsize(LEFT_MIN_W+400,560)
        setup_style(self)
        self._geometry_ready = False
        self._save_config_job = None   # P4 : debounce de la sauvegarde
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
        right_need  = preview_size + 52

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

        # Grille virtualisée — seul système de rendu (refactor A2)
        self._vg = VirtualThumbGrid(self._cv, self)
        self._vg_drag = None
        self._center_scrollbar.command = self._vg_yview
        self._cv.bind("<Configure>", lambda e: self._vg.refresh(), add="+")
        self._cv.bind("<MouseWheel>", lambda e: self._vg.refresh(), add="+")
        self._cv.bind("<Button-4>", lambda e: self._vg.refresh(), add="+")
        self._cv.bind("<Button-5>", lambda e: self._vg.refresh(), add="+")
        self._cv.bind("<ButtonPress-1>", self._vg_on_press, add="+")
        self._cv.bind("<B1-Motion>", self._vg_on_drag, add="+")
        self._cv.bind("<ButtonRelease-1>", self._vg_on_release, add="+")
        self._cv.bind("<Motion>", self._vg_on_motion, add="+")

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
        tk.Label(hdr,text=f" v{APP_VERSION}",font=("Segoe UI",9),
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
        """M3 : orchestrateur — chaque section UI est dans sa propre méthode."""
        PAD = 12
        row = 0
        self._build_info_block(inner, PAD)
        row += 1
        row = self._build_source_section(inner, PAD, row)
        row = self._build_dirs_section(inner, PAD, row)
        row = self._build_capture_section(inner, PAD, row)
        row = self._build_window_section(inner, PAD, row)
        row = self._build_actions_section(inner, PAD, row)

    # ── M3 : sections du panneau gauche ────────────────────────────────────────
    def _build_source_section(self, inner, PAD, row):

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

        # D5 : tooltip unifié (style gris centré, comme l'ancien _show_full_tooltip)
        self._src_tooltip = Tooltip(self._src_btn, lambda: self.v_path.get(),
                                    bg=C["panel2"], fg=C["t1"], border="",
                                    dx=10, dy=5, padx=8, pady=8, anchor="center")

        # D8 : synchronisation texte ↔ chemin
        self._sync_path_button(self.v_path, self._src_btn,
                               os.path.exists, lambda p: os.path.basename(p))

        self._src_name_lbl = None

        self._info_lbl=tk.Label(inner,text="Aucun fichier chargé",font=F_MONO,
                                fg=C["t2"],bg=C["panel"],justify="left",
                                anchor="w",padx=10,pady=8)
        self._info_lbl.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(0,6)); row+=1

        return row

    def _build_dirs_section(self, inner, PAD, row):
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

        # D8 : synchronisation texte ↔ chemin
        self._sync_path_button(self.v_outdir, self._outdir_btn,
                               os.path.isdir, lambda p: os.path.basename(p.rstrip("/\\")))

        # D5 : tooltip unifié
        self._outdir_tooltip = Tooltip(self._outdir_btn, lambda: self.v_outdir.get(),
                                       bg=C["panel2"], fg=C["t1"], border="",
                                       dx=10, dy=5, padx=8, pady=8, anchor="center")

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

        # D8 : synchronisation texte ↔ chemin
        self._sync_path_button(self.v_workdir, self._workdir_btn,
                               os.path.isdir, lambda p: dir_parent_label(p))

        # D5 : tooltip unifié
        self._workdir_tooltip = Tooltip(self._workdir_btn, lambda: self.v_workdir.get(),
                                        bg=C["panel2"], fg=C["t1"], border="",
                                        dx=10, dy=5, padx=8, pady=8, anchor="center")

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

        return row

    def _build_capture_section(self, inner, PAD, row):
        # Mode capture
        row=self._sect(inner,row,"Mode de capture")
        self._pill=PillSelector(inner,[("Nombre d'images","count"),("Intervalle (s)","interval")],
                                self.v_mode,command=self._on_mode_change,bg=C["bg"])
        self._pill.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(2,6)); row+=1
        self._sl_count=DarkSlider(inner,from_=5,to=1000,resolution=5,variable=self.v_count,
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
        # v4.14 (UX7) : aperçu du plan de capture avant extraction
        self._plan_lbl=tk.Label(inner,text="",font=F_SMALL,fg=C["t2"],
                                bg=C["panel"],justify="left",anchor="w",
                                padx=10,pady=6)
        self._plan_lbl.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(4,2)); row+=1
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        return row

    def _build_window_section(self, inner, PAD, row):
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
                width=0,height=28,anchor="center").grid(row=0,column=1,sticky="ew",padx=(8,0))
        HSep(inner).grid(row=row,column=0,sticky="ew",padx=PAD,pady=6); row+=1

        return row

    def _build_actions_section(self, inner, PAD, row):
        # Actions
        row=self._sect(inner,row,"Actions")
        act=tk.Frame(inner,bg=C["bg"]); act.grid(row=row,column=0,sticky="ew",padx=PAD,pady=(4,4)); row+=1
        act.columnconfigure(0,weight=1); act.columnconfigure(1,weight=1)   # v4.6 : les 2 colonnes absorbent l'espace
        GAP=6
        self._run_btn=DarkButton(act,"▶  Extraire les frames",self._start_extraction,
                                 style="accent",width=0,height=36,font=F_BOLD,anchor="center")
        self._run_btn.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,5))

        self._cancel_btn=DarkButton(act,"✕  Annuler",self._cancel_extraction,
                                   style="ghost",width=0,height=30,anchor="center")
        self._cancel_btn.grid(row=1,column=0,sticky="ew",padx=(0,GAP)); self._cancel_btn.set_state("disabled")

        self._del_btn=DarkButton(act,"🗑  Supprimer",self._delete_selected,
                                 style="danger",width=0,height=30,anchor="center")
        self._del_btn.grid(row=1,column=1,sticky="ew"); self._del_btn.set_state("disabled")

        DarkButton(act,"🗂  Vider le dossier d'extraction",self._clear_output_dir,
                style="danger",width=0,height=30,anchor="center").grid(row=2,column=0,columnspan=2,sticky="ew",pady=(5,0))
        self._retry_btn=DarkButton(act,"🔁  Ré-extraire les échecs",self._retry_failed,
                                style="default",width=0,height=30,anchor="center")
        self._retry_btn.grid(row=3,column=0,columnspan=2,sticky="ew",pady=(5,0))
        self._retry_btn.set_state("disabled")

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
        return row

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
        vcmd = (self.register(self._validate_mark_key_input), '%P')
        self._mark_key_entry=DarkEntry(mtb,textvariable=self.v_mark_key,
                                        width=3,font=F_BOLD,justify="center",
                                        validate="key", validatecommand=vcmd)
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

        self._cv.bind("<MouseWheel>",self._scroll)
        self._cv.bind("<Button-4>",  self._scroll)
        self._cv.bind("<Button-5>",  self._scroll)
        self._cv.bind("<Button-1>",  lambda e: self.focus_set(),add="+")

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

    def _vg_on_press(self, event):
        if getattr(self, "_vg", None) is None:
            return

        self.focus_set()

        self._vg_drag = {
            "active": False,
            "x0": self._cv.canvasx(event.x),
            "y0": self._cv.canvasy(event.y),
            "wx": event.x,
            "wy": event.y,
            "ctrl": bool(event.state & 0x0004),
            "shift": bool(event.state & 0x0001),
            "before": set(self.sel),
        }

        self._vg_cancel_autoscroll()

        return "break"

    def _vg_on_drag(self, event):
        st = getattr(self, "_vg_drag", None)
        if not st:
            return

        st["wx"] = event.x
        st["wy"] = event.y

        x = self._cv.canvasx(event.x)
        y = self._cv.canvasy(event.y)

        if not st["active"]:
            if abs(x - st["x0"]) < 5 and abs(y - st["y0"]) < 5:
                return

            st["active"] = True

            if not st["ctrl"]:
                self._clear_selection()
                self._upd_badges()

        st["x1"] = x
        st["y1"] = y

        self._vg_draw_rubber()
        self._vg_select_rubber()
        self._vg_schedule_autoscroll()

        return "break"

    def _vg_draw_rubber(self):
        st = getattr(self, "_vg_drag", None)
        if not st or "x1" not in st:
            return

        x1, x2 = sorted((st["x0"], st["x1"]))
        y1, y2 = sorted((st["y0"], st["y1"]))

        self._cv.delete("rb")
        self._cv.create_rectangle(
            x1, y1, x2, y2,
            outline="",
            fill=C["accent_bg"],
            stipple="gray25",
            tags="rb",
        )
        self._cv.create_rectangle(
            x1, y1, x2, y2,
            outline=C["accent"],
            fill="",
            width=2,
            dash=(6, 3),
            tags="rb",
        )
        self._cv.tag_raise("rb")

    def _vg_select_rubber(self):
        st = getattr(self, "_vg_drag", None)
        if not st or "x1" not in st:
            return

        x1, x2 = sorted((st["x0"], st["x1"]))
        y1, y2 = sorted((st["y0"], st["y1"]))

        new = set()

        for iid in self._cv.find_withtag("vtbg"):
            try:
                bx1, by1, bx2, by2 = self._cv.coords(iid)
            except Exception:
                continue

            if bx1 < x2 and bx2 > x1 and by1 < y2 and by2 > y1:
                path = None
                for tag in self._cv.gettags(iid):
                    if tag.startswith("vt::"):
                        path = tag[4:]
                        break

                if path and path in self.thumb_by_path:
                    new.add(path)

        if st["ctrl"]:
            target = st["before"] | new
        else:
            target = new

        target = {p for p in target if p in self.thumb_by_path}

        self.sel = set(target)

        if getattr(self, "_vg", None) is not None:
            self._vg.update_selection()

        self._upd_badges()

    def _vg_on_release(self, event):
        st = getattr(self, "_vg_drag", None)
        self._vg_cancel_autoscroll()

        if not st:
            return

        self._cv.delete("rb")

        if not st["active"]:
            self._vg_on_click(event)
        else:
            self._upd_badges()

            if len(self.sel) == 1:
                p = next(iter(self.sel))
                self._last_click_path = p
                self._show_preview(p)
            elif len(self.sel) > 1:
                self._last_click_path = None
                self._prev_lbl.config(image="")
                self._prev_ref = None
                self._prev_info.config(
                    text=f"Sélection multiple\n({len(self.sel)} images)\n\nAperçu désactivé.")
            else:
                self._last_click_path = None
                self._prev_lbl.config(image="")
                self._prev_ref = None
                self._prev_info.config(text="Cliquez sur une\nvignette…")

        self._vg_drag = None

        return "break"

    def _vg_on_release_all(self, event):
        if getattr(self, "_vg_drag", None) is None:
            return

        try:
            if event.widget is self._cv:
                return
        except Exception:
            pass

        self._vg_cancel_autoscroll()

        try:
            self._cv.delete("rb")
        except Exception:
            pass

        self._vg_drag = None

    def _vg_cancel_autoscroll(self):
        job = getattr(self, "_vg_autoscroll_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass

        self._vg_autoscroll_job = None

    def _vg_schedule_autoscroll(self):
        if getattr(self, "_vg_autoscroll_job", None) is None:
            self._vg_autoscroll_job = self.after(50, self._vg_autoscroll_tick)

    def _vg_autoscroll_tick(self):
        self._vg_autoscroll_job = None

        st = getattr(self, "_vg_drag", None)
        if not st or not st.get("active"):
            return

        if getattr(self, "_vg", None) is None:
            return

        try:
            if not self._cv.winfo_exists():
                return

            canvas_h = max(1, self._cv.winfo_height())
        except Exception:
            return

        wx = st.get("wx", 0)
        wy = st.get("wy", 0)

        edge = 40

        top_before = self._cv.canvasy(0)

        if wy < edge:
            step = max(1, (edge - wy) // 8)
            self._cv.yview_scroll(-step, "units")
        elif wy > canvas_h - edge:
            step = max(1, (wy - (canvas_h - edge)) // 8)
            self._cv.yview_scroll(step, "units")
        else:
            return

        self._cv.update_idletasks()

        if self._cv.canvasy(0) == top_before:
            return

        self._vg.refresh()

        x = self._cv.canvasx(wx)
        y = self._cv.canvasy(wy)

        st["x1"] = x
        st["y1"] = y

        self._vg_draw_rubber()
        self._vg_select_rubber()

        self._vg_schedule_autoscroll()

    def _vg_on_motion(self, event):
        if getattr(self, "_vg", None) is None:
            return

        st = getattr(self, "_vg_drag", None)
        if st and st.get("active"):
            return

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

        if path and path not in self.thumb_by_path:
            path = None

        self._vg.set_hover(path)
        self._cv.config(cursor="hand2" if path else "")

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
        self.bind_all("<ButtonRelease-1>",self._vg_on_release_all,add="+")
        self.bind("<Left>",  self._on_arrow_key)
        self.bind("<Right>", self._on_arrow_key)
        self.bind("<Up>",    self._on_arrow_key)
        self.bind("<Down>",  self._on_arrow_key)

    def _on_close(self):
        self._cfg["window_h"] = self.winfo_height()
        self._cancel = True          # v4.5 : interrompt l'extraction en cours → sortie propre
        # P4 : flush immédiat du debounce (sinon la dernière modif est perdue)
        if self._save_config_job is not None:
            try: self.after_cancel(self._save_config_job)
            except Exception: pass
            self._save_config_job = None
        save_config(self._collect_config())
        self.destroy()

    def _on_arrow_key(self, event):
        fw = self.focus_get()
        if isinstance(fw, (tk.Entry, DarkEntry)):
            return
        if not self.thumbs:
            return
        cols = self.v_cols.get()
        total = len(self.thumbs)
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
        new_path = self.thumbs[new]["path"]
        self._clear_selection()
        self.sel.add(new_path)
        self._set_sel(new_path, True)
        self._last_click_path = new_path
        self._upd_badges()
        self._show_preview(new_path)
        self._scroll_to_thumb(new_path)

    def _scroll_to_thumb(self, path):
        if getattr(self, "_vg", None) is not None:
            self._vg.scroll_to_path(path)

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
            self._mark_binding_id = None

        key = self.v_mark_key.get().strip()
        if not key:
            return

        try:
            bid = self.bind(f"<KeyPress-{key}>", self._on_mark_key, add=True)
            self._mark_binding_id = (f"<KeyPress-{key}>", bid)
        except tk.TclError:
            # v4.12 (UX8) : filet de sécurité si le caractère n'est pas un keysym valide
            self._status(f"⚠  Touche non supportée : '{key}'", duration=4000)

    def _validate_mark_key_input(self, value_if_allowed):
        """v4.12 (UX8) : limite la saisie du raccourci à un seul caractère."""
        return len(value_if_allowed) <= 1

    # D5 : _show_full_tooltip et _hide_tooltip supprimés —
    # remplacés par des instances Tooltip (vfe_widgets) créées dans _build_left_content.

    def _scroll_universal(self, e):
        # P7 : si l'événement vise directement un canvas géré, son binding
        # propre a déjà scrollé → on s'arrête (supprime le double défilement).
        if e.widget is self._cv or e.widget is getattr(self, "_left_canvas", None):
            return
        # Canvas central
        wx = self._cv.winfo_rootx()

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
        # v4.15 (E81) : les infos sous les sliders sont supprimées car
        # redondantes avec le bloc "Plan" unifié (_update_capture_plan).
        self._update_capture_plan()

    def _update_capture_plan(self):
        """v4.14 (UX7) : affiche un résumé du plan de capture courant."""
        if not hasattr(self, "_plan_lbl"):
            return

        dur = self.video_info.get("duration", 0)
        if not dur:
            self._plan_lbl.config(text="Chargez une vidéo pour prévisualiser le plan.")
            return

        try:
            targets = self._compute_targets()
        except Exception:
            self._plan_lbl.config(text="")
            return

        if not targets:
            self._plan_lbl.config(text="Aucune frame à extraire.")
            return

        n = len(targets)
        first = targets[0]
        last = targets[-1]

        if self.v_mode.get() == "count":
            if n == 1:
                txt = f"📋  Plan : 1 image au début de la vidéo."
            else:
                span = last - first
                avg = span / (n - 1) if n > 1 else 0
                txt = (f"📋  Plan : {n} images entre {hms(first)} et {hms(last)}\n"
                       f"      → une toutes les {hms(avg)} environ")
        else:
            iv = self.v_intv.get()
            txt = (f"📋  Plan : {n} image(s) toutes les {iv} s\n"
                   f"      → de {hms(first)} à {hms(last)}")

        self._plan_lbl.config(text=txt)

    # ── Fichiers ──────────────────────────────────────────────────────────────
    def _sync_path_button(self, var, btn, validate_fn, format_fn):
        """D8 : synchronise le texte d'un bouton avec un chemin.
        validate_fn(path) -> bool : vérifie la validité du chemin.
        format_fn(path)   -> str  : formate le chemin pour l'affichage."""
        def _update(*args):
            path = var.get()
            if path and validate_fn(path):
                btn.set_text(format_fn(path))
            else:
                btn.set_text("Parcourir")
        var.trace_add("write", _update)
        _update()

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
        # v4.8 (point 9) : réinitialise l'état HDR et signale une détection en cours
        self._hdr_info={}
        self._hdr_detect_done.clear()
        # Détection HDR en arrière-plan pour ne pas bloquer l'UI
        threading.Thread(target=self._detect_hdr_async, args=(path,), daemon=True).start()
        log.info("Vidéo chargée : %s | %s | %dx%d | %.2f fps",
                 os.path.basename(path), hms(dur), raw_w, raw_h, fps)
        self._update_capture_plan()   # v4.14 (UX7) : rafraîchit le plan avec la nouvelle durée
        # U1 : les échecs appartiennent à l'ancienne vidéo → on les oublie
        self._failed_frames=[]; self._failed_tcs=[]
        self._retry_btn.set_state("disabled")
        self._retry_btn.set_text("🔁  Ré-extraire les échecs")    


    # ── HDR ───────────────────────────────────────────────────────────────────
    def _detect_hdr_async(self, path):
        """Lance detect_hdr() en thread, puis met à jour l'UI."""
        hdr = detect_hdr(path)
        # v4.8 (point 9) : publie le résultat puis signale qu'il est prêt.
        # L'Event sert de barrière mémoire : un lecteur qui voit l'event "set"
        # voit aussi _hdr_info peuplé.
        self._hdr_info = hdr
        self._hdr_detect_done.set()
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
        # self.sel peut être vide si le clic sur le combo a déclenché
        # _global_click_deselect → on utilise le dernier chemin aperçu.
        p = self._preview_path
        if p and p in self.thumb_by_path:
            self._show_preview(p)

    def _compute_targets(self):
        return compute_targets(
            duration=self.video_info["duration"],
            fps=self.video_info.get("fps"),
            mode=self.v_mode.get(),
            count=self.v_count.get(),
            interval=self.v_intv.get(),
        )

    # ── Extraction ────────────────────────────────────────────────────────────
    def _start_extraction(self):
        self._loading_thumbs = False
        if self._extracting:
             return
        if not self.v_path.get():
            messagebox.showwarning("Attention","Veuillez choisir une vidéo."); return
        if not self.v_outdir.get():
            messagebox.showwarning("Attention","Veuillez choisir un dossier."); return
        if not self.video_info:
            messagebox.showwarning("Attention","Informations vidéo non chargées."); return
        targets=self._compute_targets()
        if not targets: messagebox.showinfo("Info","Aucune frame à extraire."); return

        self.thumbs.clear(); self.thumb_by_path.clear()
        self.sel.clear(); self.marked.clear()
        self._last_click_path=None
        self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None; self._preview_path=None
        self._prev_info.config(text="Extraction en cours…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._run_btn.set_state("disabled")
        self._cancel_btn.set_state("normal"); self._cancel=False; self._extracting=True
        self._retry_btn.set_state("disabled"); self._retry_btn.set_text("🔁  Ré-extraire les échecs")
        self._extract_start=time.time()   # v4.10 (UX3) : départ du calcul d'ETA
        # v4.1 : état du flush ordonné (les workers terminent dans le désordre)
        self._next_flush=0; self._flushed=0; self._flush_tot=len(targets)
        self._pending_results={}; self._failed_tcs=[]; self._failed_frames=[]
        log.info("Extraction lancée : %d frame(s) ciblée(s) — %s",
                 len(targets), os.path.basename(self.v_path.get()))
        self._prog.set(0); self._prog_lbl.config(text="Initialisation…")

        # A3 : capturer les Tk vars dans le thread principal — les workers
        # ne doivent JAMAIS appeler .get() sur une variable Tkinter.
        _do_filter = self.v_black_filter.get()
        _tonemap   = self.v_hdr_tonemap.get()
        threading.Thread(target=self._worker,
                         args=(self.v_path.get(),self.v_outdir.get(),targets,
                               _do_filter,_tonemap),
                         daemon=True).start()

    def _cancel_extraction(self):
        self._cancel=True; self._cancel_btn.set_state("disabled")
        self._prog_lbl.config(text="Annulation…")

    # ── U1 : ré-extraction des échecs ────────────────────────────────────────
    def _retry_failed(self):
        """Ré-extrait uniquement les frames ayant échoué lors de la dernière extraction."""
        if not self._failed_frames or self._extracting:
            return
        if not self.v_path.get() or not self.video_info:
            self._status("⚠  Vidéo non chargée.", duration=4000); return
        if not self.v_outdir.get() or not os.path.isdir(self.v_outdir.get()):
            self._status("⚠  Dossier d'extraction introuvable.", duration=4000); return
        if not self._ffmpeg_ok:
            self._status("⚠  Ré-extraction impossible sans ffmpeg.", duration=4000); return
        self._extracting = True
        self._cancel = False
        self._run_btn.set_state("disabled")
        self._retry_btn.set_state("disabled")
        self._cancel_btn.set_state("normal")
        self._prog.set(0)
        n = len(self._failed_frames)
        self._prog_lbl.config(text=f"Ré-extraction de {n} échec(s)…")
        # A3 : capturer les Tk vars dans le thread principal
        _do_filter = self.v_black_filter.get()
        _tonemap   = self.v_hdr_tonemap.get()
        threading.Thread(target=self._retry_worker,
                         args=(self.v_path.get(), self.v_outdir.get(),
                               list(self._failed_frames), _do_filter, _tonemap),
                         daemon=True).start()

    def _retry_worker(self, vpath, outdir, failed, do_filter, tonemap):
        """Ré-extraction séquentielle (les échecs sont rares — pas besoin de pool).
        Même pipeline et même cascade de fallback que l'extraction normale.
        A3 : do_filter et tonemap capturés côté main thread."""
        info = self.video_info
        disp_w = info.get("disp_w", info["width"])
        disp_h = info.get("disp_h", info["height"])
        sar_applied = info.get("sar_applied", False)
        base = os.path.splitext(os.path.basename(vpath))[0]
        hdr_info = self._hdr_info
        is_hdr = hdr_info.get("is_hdr", False)
        if is_hdr and self._zscale_ok is None:
            self._zscale_ok = zscale_available()
        tot = len(failed)
        for done, (i, t) in enumerate(failed, start=1):
            if self._cancel:
                break
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="vfe_")
            os.close(tmp_fd)
            try: os.remove(tmp_path)
            except Exception: pass
            # D2 : cascade d'extraction factorisée (méthode _run_extraction_cascade)
            ok, last_reason, _rc = self._run_extraction_cascade(
                vpath, t, tmp_path, disp_w, disp_h, sar_applied,
                is_hdr, hdr_info, tonemap)
            img = None
            fpath = ""
            if ok:
                try:
                    img = Image.open(tmp_path).copy()
                except Exception as ex:
                    ok = False
                    last_reason = f"décodage image : {ex}"
            if ok and do_filter and is_black_frame(np.array(img), threshold=5):
                ok = False
                last_reason = "frame noire détectée (décochez le filtre pour la garder)"
            if ok:
                fname = f"{base}_{i+1:04d}_{tc_str(t)}.jpg"
                fpath = os.path.join(outdir, fname)
                try:
                    shutil.move(tmp_path, fpath)
                except Exception as ex:
                    ok = False
                    fpath = ""
                    last_reason = f"déplacement : {ex}"
            if not ok:
                try: os.remove(tmp_path)
                except Exception: pass
            self.after(0, self._on_retry_result, i, t,
                       "ok" if ok else "fail", img, fpath, last_reason)
            self.after(0, self._prog.set, int(done / tot * 100))
        self.after(0, self._retry_done)

    def _on_retry_result(self, i, t, kind, img, fpath, info=""):
        """Résultat d'une frame ré-extraite : retirée des échecs si OK,
        et insérée à sa position chronologique dans la grille."""
        if kind == "ok":
            self._failed_frames = [(fi, ft) for (fi, ft) in self._failed_frames
                                   if not (fi == i and ft == t)]
            self._failed_tcs = [ft for (fi, ft) in self._failed_frames]
            entry = {"img": img, "path": fpath, "tc": t}
            pos = len(self.thumbs)
            for idx, e in enumerate(self.thumbs):
                if e["tc"] > t:
                    pos = idx
                    break
            self.thumbs.insert(pos, entry)
            self.thumb_by_path[fpath] = entry
            self._reindex()
            self._badge_total.config(text=f"{len(self.thumbs)} image(s)")
            if getattr(self, "_vg", None) is not None:
                self._vg.refresh()
            log.info("Ré-extraction réussie : frame %d (%s)", i + 1, hms(t))
        else:
            log.warning("Ré-extraction échouée : frame %d (%s) : %s",
                        i + 1, hms(t), info or "raison inconnue")

    def _retry_done(self):
        self._extracting = False
        self._run_btn.set_state("normal")
        self._cancel_btn.set_state("disabled")
        nf = len(self._failed_frames)
        if self._cancel:
            self._prog_lbl.config(text="Ré-extraction annulée")
        if nf:
            self._retry_btn.set_text(f"🔁  Ré-extraire les échecs  ({nf})")
            self._retry_btn.set_state("normal")
            if not self._cancel:
                self._prog.set(100)
                self._prog_lbl.config(text=f"⚠  Ré-extraction terminée · {nf} échec(s) restant(s)")
                self._status("⚠  Échec(s) restant(s) :  " +
                             "  |  ".join(hms(t) for (_, t) in self._failed_frames), duration=0)
        else:
            self._retry_btn.set_text("🔁  Ré-extraire les échecs")
            self._retry_btn.set_state("disabled")
            if not self._cancel:
                self._prog.set(100)
                self._prog_lbl.config(text="✔  Tous les échecs ont été récupérés")
                self._status("✔  Ré-extraction terminée : tous les échecs récupérés.", duration=6000)

    def _run_ffmpeg(self, cmd, timeout):
        return run_ffmpeg(cmd, timeout, lambda: self._cancel)

    @staticmethod
    def _tmp_ok(tmp_path):
        return tmp_ok(tmp_path)

    def _run_extraction_cascade(self, vpath, t, tmp_path, disp_w, disp_h,
                                sar_applied, is_hdr, hdr_info, tonemap):
        """D2 : cascade d'extraction unique pour une frame, utilisée à la fois par
        l'extraction normale (task() de _worker_ffmpeg) et la ré-extraction des
        échecs (_retry_worker). Retourne (ok, last_reason, last_rc).
        ok      : True si une des étapes a produit un fichier valide.
        last_rc : returncode de la dernière commande tentée.
        Lit self._cancel et self._zscale_ok. Thread-safe (aucun accès Tk)."""
        ok = False
        last_reason = ""
        rc = -1
        if is_hdr:
            if self._zscale_ok:
                cmd = build_ffmpeg_cmd_hdr(vpath, t, tmp_path, disp_w, disp_h,
                                           sar_applied, hdr_info, tonemap)
                rc, last_reason = self._run_ffmpeg(cmd, timeout=60)
                ok = rc == 0 and self._tmp_ok(tmp_path)
            if not ok and not self._cancel:
                cmd2 = build_ffmpeg_cmd_hdr_fallback(vpath, t, tmp_path, disp_w,
                                                     disp_h, sar_applied)
                rc, r2 = self._run_ffmpeg(cmd2, timeout=60)
                if rc == 0 and self._tmp_ok(tmp_path): ok = True
                else: last_reason = r2 or last_reason
            if not ok and not self._cancel:
                cmd3 = build_ffmpeg_cmd(vpath, t, tmp_path, disp_w, disp_h, sar_applied)
                rc, r3 = self._run_ffmpeg(cmd3, timeout=30)
                if rc == 0 and self._tmp_ok(tmp_path): ok = True
                else: last_reason = r3 or last_reason
        else:
            cmd = build_ffmpeg_cmd(vpath, t, tmp_path, disp_w, disp_h, sar_applied)
            rc, last_reason = self._run_ffmpeg(cmd, timeout=30)
            ok = rc == 0 and self._tmp_ok(tmp_path)
            if not ok and not self._cancel:
                cmd2 = build_ffmpeg_cmd_fallback(vpath, t, tmp_path, disp_w,
                                                 disp_h, sar_applied)
                rc, r2 = self._run_ffmpeg(cmd2, timeout=30)
                if rc == 0 and self._tmp_ok(tmp_path): ok = True
                else: last_reason = r2 or last_reason
        return ok, last_reason, rc

    def _worker(self,vpath,outdir,targets,do_filter,tonemap):
        black_tcs=[]
        if self._ffmpeg_ok:
            self._worker_ffmpeg(vpath,outdir,targets,black_tcs,do_filter,tonemap)
        else:
            self._worker_opencv(vpath,outdir,targets,black_tcs,do_filter)
        self.after(0,self._extract_done,black_tcs)

    # ══════════════════════════════════════════════════════════════════════════
    #  WORKER FFMPEG — v3.0 : pipeline HDR→SDR si HDR détecté
    # ══════════════════════════════════════════════════════════════════════════
    def _worker_ffmpeg(self,vpath,outdir,targets,black_tcs,do_filter,tonemap):
        # v4.1 : le flush ordonné (thread principal) alimente cette liste
        self._flush_black_tcs = black_tcs
        info=self.video_info
        disp_w=info.get("disp_w",info["width"])
        disp_h=info.get("disp_h",info["height"])
        sar_applied=info.get("sar_applied",False)
        # A3 : do_filter et tonemap reçus en paramètres (capturés côté main thread)
        base=os.path.splitext(os.path.basename(vpath))[0]
        # v4.8 (point 9) : on est dans un thread → on peut attendre la fin de la
        # détection HDR sans figer l'UI. Supprime la race "extraction lancée avant
        # la fin de detect_hdr()" qui faisait partir une vidéo HDR en pipeline SDR.
        t0=time.time()
        while not self._hdr_detect_done.wait(timeout=0.1):
            if self._cancel:
                return
            if time.time()-t0>20:
                log.warning("Détection HDR non terminée sous 20 s — pipeline choisi sans garantie")
                break
        hdr_info   = self._hdr_info
        is_hdr     = hdr_info.get("is_hdr", False)
        # A3 : tonemap déjà reçu en paramètre — plus de .get() Tk ici
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
            # D2 : cascade d'extraction factorisée (méthode _run_extraction_cascade)
            ok, last_reason, rc = self._run_extraction_cascade(
                vpath, t, tmp_path, disp_w, disp_h, sar_applied,
                is_hdr, hdr_info, tonemap)
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
    def _worker_opencv(self,vpath,outdir,targets,black_tcs,do_filter):
        cap=cv2.VideoCapture(vpath)
        tot=len(targets)
        info=self.video_info
        disp_w=info.get("disp_w",info["width"])
        disp_h=info.get("disp_h",info["height"])
        sar_applied=info.get("sar_applied",False)
        # A3 : do_filter reçu en paramètre
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

    def _detect_limited_range_opencv(self, vpath, cap):
        return detect_limited_range_opencv(vpath, cap, self.video_info)

    @staticmethod
    def _expand_limited_range(frame):
        return expand_limited_range(frame)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _extract_progress_text(self, done, tot, t, extra=""):
        base = f"{done}/{tot}  ·  {hms(t)}"

        if extra:
            base += f"  {extra}"

        start = getattr(self, "_extract_start", None)
        if not start or done <= 0 or tot <= 0:
            return base

        elapsed = time.time() - start
        if elapsed <= 0:
            return base

        remaining = max(0.0, (tot - done) * (elapsed / done))

        if remaining < 60:
            eta = f"{int(remaining)} s"
        else:
            eta = f"{int(remaining // 60)}m{int(remaining % 60):02d}s"

        return f"{base}  ·  ⏳ {eta}"

    def _black_skipped(self,t,done,tot,pct):
        self._prog.set(pct)
        self._prog_lbl.config(text=self._extract_progress_text(done, tot, t, "🔲 noire"))

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
                self._failed_frames.append((i, tc))
                log.warning("Échec frame %d (%s) : %s", i + 1, hms(tc), inf or "raison inconnue")

                if not self._cancel:
                    self._prog.set(pct)
                    self._prog_lbl.config(
                        text=self._extract_progress_text(self._flushed, self._flush_tot, tc, "⚠ échec"))

            self._next_flush += 1

    def _frame_done(self,img,fpath,t,done,tot,pct):
        entry={"img":img,"path":fpath,"tc":t,"_pos":len(self.thumbs)}
        self.thumbs.append(entry)
        self.thumb_by_path[fpath]=entry            # v4
        pos=len(self.thumbs)-1

        self._prog.set(pct)
        self._prog_lbl.config(text=self._extract_progress_text(done, tot, t))
        self._badge_total.config(text=f"{len(self.thumbs)} image(s)")

        self._add_thumb(fpath,pos)
        self._adjust_center_width()

    def _extract_done(self,black_tcs=None):
        self._run_btn.set_state("normal"); self._cancel_btn.set_state("disabled")
        self._extracting=False
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
            self._retry_btn.set_text(f"🔁  Ré-extraire les échecs  ({nf})")
            self._retry_btn.set_state("normal")
        elif nb>0:
            self._status(f"🔲  {nb} frame(s) noire(s) :  "+"  |  ".join(hms(t) for t in black_tcs),duration=0)
        elif black_tcs is not None and self.v_black_filter.get():
            self._status("✔  Aucune frame noire détectée.",duration=6000)

    # ── Grille vignettes ──────────────────────────────────────────────────────
    def _add_thumb(self, path, pos):
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    # ── Redimensionnement ─────────────────────────────────────────────────────
    _fit_job=None
    def _fit_window(self, animate=True, target_h=None):
        """D6 : redimensionne la fenêtre pour ajuster aux vignettes + aperçu.
        target_h=None  → conserve la hauteur courante (comportement historique).
        target_h=<int> → impose une hauteur cible, bornée à [560, écran-40]."""
        SASH_W = 5
        sz = self.v_tsize.get()
        cols = self.v_cols.get()
        center_need = cols * (sz + 22) + 12 + 14 + 10
        right_need = self.v_psize.get() + 52
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
        sh = self.winfo_screenheight()
        win_target = min(max(s0 + center_need + right_need + SASH_W * 2 + 4,
                            LEFT_MIN_W + 300), sw - 40)
        # Hauteur : courante par défaut, ou cible imposée (bornée)
        if target_h is not None:
            use_h = int(target_h)
            use_h = max(560, use_h)
            use_h = min(use_h, max(560, sh - 40))
        else:
            use_h = self.winfo_height()
        cy = self.winfo_y()
        cx0 = self.winfo_x()
        def _apply(w):
            cx = max(0, min(cx0, sw - w))
            self.geometry(f"{w}x{use_h}+{cx}+{cy}")
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

    def _clear_grid(self):
        if hasattr(self, "_preview_cache"):
            self._preview_cache.clear()
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    def _clear_all_thumb_state(self):
        """Réinitialise complètement l'état des vignettes (zéro image)."""
        self._clear_grid()
        self.thumbs.clear()
        self.thumb_by_path.clear()
        self.sel.clear()
        self.marked.clear()
        self._last_click_path=None
        self._upd_marked_badge()
        self._prev_lbl.config(image="")
        self._prev_ref = None
        self._preview_path = None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text="0 image(s)")
        self._badge_sel.config(text="")
        self._del_btn.set_state("disabled")
        self._copy_btn.set_state("disabled")

    def _rebuild_grid(self):
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _clear_selection(self):
        """v4 : efface toute la sélection (les sets contiennent des chemins)."""
        for p in list(self.sel):
            self._set_sel(p, False)
        self.sel.clear()
        self._last_click_path = None

    def _position_of(self, path):
        """Position d'affichage d'un chemin dans self.thumbs, ou -1 si absent.
        P5 : O(1) — l'index est stocké dans l'entry et maintenu par _reindex()."""
        entry = self.thumb_by_path.get(path)
        if entry is None:
            return -1
        return entry.get("_pos", -1)

    def _reindex(self):
        """P5 : recalcule les positions après insertion / suppression / déplacement."""
        for idx, entry in enumerate(self.thumbs):
            entry["_pos"] = idx

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

    def _set_sel(self, path, on):
        if getattr(self, "_vg", None) is not None:
            self._vg.update_selection()

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
            self.marked.discard(path)
            self.thumb_by_path.pop(path, None)
        # 3) Reconstruire la liste ordonnée sans les supprimés
        self.thumbs = [e for e in self.thumbs if e["path"] not in deleted_set]
        self._reindex()
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
        if self._extracting:
            self._status("⚠  Attendez la fin de l'extraction en cours.", duration=4000); return
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
        self.thumbs.clear(); self.thumb_by_path.clear()
        self._failed_frames=[]; self._failed_tcs=[]
        self._retry_btn.set_state("disabled"); self._retry_btn.set_text("🔁  Ré-extraire les échecs")
        self.sel.clear(); self.marked.clear(); self._last_click_path=None; self._upd_marked_badge(); self._clear_grid()
        self._prev_lbl.config(image=""); self._prev_ref=None; self._preview_path=None
        self._prev_info.config(text="Cliquez sur une\nvignette…")
        self._badge_total.config(text="0 image(s)"); self._badge_sel.config(text="")
        self._del_btn.set_state("disabled"); self._prog.set(0)
        self._prog_lbl.config(text=f"✔  {len(jpgs)-len(errors)} fichier(s) déplacé(s) vers la corbeille")

    
    # ── Marquage ──────────────────────────────────────────────────────────────
    def _toggle_mark_selection(self):
        """D7 : bascule le marquage de la sélection courante (tout marquer / tout démarquer)."""
        if self.sel.issubset(self.marked):
            for p in list(self.sel):
                self.marked.discard(p)
                self._update_mark_overlay(p)
        else:
            for p in list(self.sel):
                self.marked.add(p)
                self._update_mark_overlay(p)

    def _on_mark_key(self,event):
        fw=self.focus_get()
        if isinstance(fw,(tk.Entry,DarkEntry)): return
        if not self.sel: return
        self._toggle_mark_selection()
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
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    def _unmark_all(self):
        for p in list(self.marked): self.marked.discard(p); self._update_mark_overlay(p)
        self._upd_marked_badge(); self._auto_save_config()

    def _mark_selection(self):
        if not self.sel:
            self._status("⚠  Aucune image sélectionnée.")
            return
        self._toggle_mark_selection()
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
            # S4 : noms de fichier uniquement → les marques survivent à un
            # changement de dossier d'extraction.
            "marked_files":    sorted(os.path.basename(p) for p in self.marked),
            "window_h":        self.winfo_height(),
        }
        return _coerce_config(raw)

    def _auto_save_config(self):
        """P4 : debounce 400 ms — une seule écriture disque après un burst de changements
        (ex. drag du slider). Les sauvegardes explicites (_save_config_action) restent
        immédiates et ne passent pas par ici."""
        if self._save_config_job is not None:
            try:
                self.after_cancel(self._save_config_job)
            except Exception:
                pass
        self._save_config_job = self.after(400, self._do_auto_save)

    def _do_auto_save(self):
        self._save_config_job = None
        save_config(self._collect_config())

    def _restore_marked(self):
        # S4 : les marques sont persistées en noms de fichier. os.path.basename()
        # sur les valeurs sauvegardées assure la rétro-compatibilité avec les
        # anciennes configs qui contenaient des chemins absolus.
        saved = set(os.path.basename(p) for p in self._cfg.get("marked_files", []))
        if not saved:
            return
        for entry in self.thumbs:
            p = entry["path"]
            if os.path.basename(p) in saved:
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
            self.sel.discard(path)
            self.marked.discard(path)
            self.thumb_by_path.pop(path, None)
        self.thumbs = [e for e in self.thumbs if e["path"] not in moved_paths]
        self._reindex()
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
        self._preview_path = path
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
        self.thumb_by_path.clear()
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
        if getattr(self, "_vg", None) is not None:
            self._vg.refresh()

    def _refresh_folder(self):
        """Relance le chargement des images depuis le dossier d'extraction."""
        outdir = self.v_outdir.get()
        if not outdir or not os.path.isdir(outdir):
            self._status("⚠  Aucun dossier d'extraction défini ou inexistant.", duration=4000)
            return
        self._status("🔁 Rafraîchissement en cours…", duration=0)
        self._reload_extraction_folder()

    def _reload_done_lazy(self, entries):
        """Stocke les métadonnées sans charger les pixels, puis construit les vignettes une par une."""
        for idx, (fpath, tc) in enumerate(entries):
            entry = {"img": None, "path": fpath, "tc": tc, "_pos": idx}
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
        for i in range(start_idx, end_idx):
            entry = self.thumbs[i]
            self._add_thumb(entry["path"], i)
        self._prog_lbl.config(text=f"Chargement des vignettes… {end_idx} / {len(self.thumbs)}")
        if end_idx < len(self.thumbs):
            self.after(1, self._build_thumbs_async, end_idx)
        else:
            self._loading_thumbs = False
            self._prog_lbl.config(text=f"✔  {len(self.thumbs)} image(s) rechargée(s)")
            self.after(3000, lambda: self._prog_lbl.config(text=""))
            # ↓ on passe la hauteur cible explicitement
            target_h = int(self._cfg.get("window_h", self.winfo_height()))
            self.after(50, lambda: self._fit_window(animate=False, target_h=target_h))
            self.after(80, self._restore_marked)

    # D6 : _fit_window_with_height supprimé — remplacé par _fit_window(target_h=…)

    # ── Sauvegarde config ─────────────────────────────────────────────────────
    def _save_config_action(self):
        save_config(self._collect_config())
        self._prog_lbl.config(text="✔  Configuration sauvegardée")
        self.after(3000, lambda: self._prog_lbl.config(text=""))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()