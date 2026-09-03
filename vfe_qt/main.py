# -*- coding: utf-8 -*-
"""Cineblast VFE — shell principal Qt (LOT 3).
Charge VFE_Config.json en LECTURE SEULE. Aucune sauvegarde.
Aucune logique vidéo (LOT 4)."""

import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

import logging
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.path.join(_BASE, "VFE_Log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  [Qt] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RotatingFileHandler(_LOG_FILE, maxBytes=512 * 1024,
                                  backupCount=2, encoding="utf-8")],
)
log = logging.getLogger("vfe.qt")

# LOT 6 (diag) : rend les plantages visibles dans la console + journal
import faulthandler
import traceback

faulthandler.enable()

def _qt_excepthook(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.error("Exception non gérée :\n%s", msg)
    print(msg, file=sys.stderr)

sys.excepthook = _qt_excepthook

# LOT 7 (fix) : flèches globales — imports nécessaires
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QAbstractItemView, QDialog

import re

try:
    from send2trash import send2trash
    _TRASH_OK = True
except ImportError:
    send2trash = None
    _TRASH_OK = False


def trash_files(paths):
    """LOT 8 : envoi groupé à la corbeille, fallback os.remove
    (même comportement que l'ancienne app, chemins Windows normalisés)."""
    existing = [p for p in paths if os.path.exists(p)]
    if not existing:
        return []
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


# LOT 10B (fix) : import explicite placé juste avant les classes,
# quel que soit l'ordre du reste du fichier (imports dupliqués = sans danger).
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)


class BlackThumb(QLabel):
    """LOT 10B : vignette 150 px d'une frame noire — clic = visionneuse."""

    def __init__(self, path, tc, parent=None):
        super().__init__(parent)
        self._path = path
        self._tc = tc
        self.setFixedSize(150, 84)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {TH.SURFACE_CARD};"
            f"border: 1px solid {TH.BORDER_SUBTLE};"
            "border-radius: 6px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.setPixmap(pix.scaled(146, 80, Qt.KeepAspectRatio,
                                          Qt.SmoothTransformation))
        self.setToolTip(hms(tc))

    def mousePressEvent(self, e):
        if self._path:
            BlackViewer(self, self._path, self._tc).exec()
        super().mousePressEvent(e)


class BlackViewer(QDialog):
    """LOT 10B : visionneuse de frame noire — image 800 px encadrée dans
    une carte grise (même style que l'aperçu Zone D), fond opaque sombre.
    Fermeture : clic sur l'image, hors image, ×, ou Échap."""

    def __init__(self, parent, path, tc=0):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"QDialog {{ background-color: {TH.BG_APP}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)
        title = QLabel(f"Frame noire — {hms(tc)}" if tc else "Frame noire")
        title.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        top.addWidget(title)
        top.addStretch()
        xbtn = QPushButton("×")
        xbtn.setFixedSize(28, 28)
        xbtn.setStyleSheet(
            f"background-color: {TH.SURFACE_ELEV}; color: {TH.TEXT_PRIMARY};"
            f"border: 1px solid {TH.BORDER_STRONG}; border-radius: 6px;"
            "font-size: 16px;")
        xbtn.clicked.connect(self.close)
        top.addWidget(xbtn)
        lay.addLayout(top)

        card = QWidget()
        card.setStyleSheet(
            f"background-color: {TH.SURFACE_CARD};"
            f"border: 1px solid {TH.BORDER_SUBTLE};"
            "border-radius: 6px;")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        img = QLabel(card)
        pix = QPixmap(path)
        if not pix.isNull():
            img.setPixmap(pix.scaled(800, 520, Qt.KeepAspectRatio,
                                     Qt.SmoothTransformation))
        img.setStyleSheet("background: transparent; border: none;")
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(img)
        lay.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)

        self.resize(920, 680)
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.center().x() - self.width() // 2,
                  geo.center().y() - self.height() // 2)

    def mousePressEvent(self, e):
        self.close()
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(e)

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImageReader, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import cv2
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import numpy as np

from vfe_config import load_config, save_config
from vfe_ffmpeg import (
    build_ffmpeg_cmd,
    build_ffmpeg_cmd_fallback,
    build_ffmpeg_cmd_hdr,
    build_ffmpeg_cmd_hdr_fallback,
    detect_hdr,
    ffmpeg_available,
    get_display_size,
    run_ffmpeg,
    tmp_ok,
    zscale_available,
)
from vfe_plan import compute_targets
from vfe_utils import (_parse_tc_from_filename, dir_parent_label, frame_filename,
                       hms, is_black_frame, tc_str)

import theme as TH
from theme import QSS
from widgets import PathButton, Switch, align_badge_widths, sect, sep
from grid_qt import ThumbCanvas


def sep_a():
    """Séparateur Zone A : ligne 1 px avec 7 px d'espace intégré en dessous.
    L'espace au-dessus (10 px) est ajouté par lay.addSpacing(10)."""
    f = QFrame()
    f.setObjectName("sepA")
    f.setFixedHeight(8)
    return f


class HdrWorker(QThread):
    finished_hdr = Signal(dict, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        self.finished_hdr.emit(detect_hdr(self._path), self._path)


class ExtractWorker(QThread):
    """LOT 5 : pool de 3 workers ffmpeg — mêmes commandes et même cascade
    de fallbacks que l'ancienne app (vfe_ffmpeg). Résultats émis vers le
    thread principal, qui fait le flush ordonné."""
    result_ready = Signal(int, str, str, str, float)
    finished_all = Signal()

    def __init__(self, parent, vpath, outdir, targets, do_filter, black_thresh,
                 tonemap, is_cancelled, black_dir=""):
        super().__init__(parent)
        self._vpath = vpath
        self._outdir = outdir
        self._targets = targets
        self._do_filter = do_filter
        self._black_thresh = black_thresh
        self._tonemap = tonemap
        self._is_cancelled = is_cancelled
        self._black_dir = black_dir

    def run(self):
        app = self.parent()
        info = app.video_info
        disp_w = info.get("disp_w", info["width"])
        disp_h = info.get("disp_h", info["height"])
        sar_applied = info.get("sar_applied", False)
        base = os.path.splitext(os.path.basename(self._vpath))[0]
        # attendre la fin de la détection HDR (max 20 s)
        t0 = time.time()
        while not app._hdr_event.wait(timeout=0.1):
            if self._is_cancelled():
                return
            if time.time() - t0 > 20:
                log.warning("Détection HDR non terminée sous 20 s")
                break
        hdr_info = app._hdr_info
        is_hdr = hdr_info.get("is_hdr", False)
        if is_hdr and app._zscale_ok is None:
            app._zscale_ok = zscale_available()
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(self._task, i, t, disp_w, disp_h, sar_applied,
                              base, hdr_info, is_hdr)
                    for (i, t) in self._targets]
            for f in futs:
                try:
                    f.result()
                except Exception:
                    log.exception("Worker inattendu")
        self.finished_all.emit()

    def _cascade(self, t, tmp_path, disp_w, disp_h, sar_applied, hdr_info, is_hdr):
        app = self.parent()
        ok = False
        last_reason = ""
        rc = -1
        if is_hdr:
            if app._zscale_ok:
                cmd = build_ffmpeg_cmd_hdr(self._vpath, t, tmp_path, disp_w, disp_h,
                                           sar_applied, hdr_info, self._tonemap)
                rc, last_reason = run_ffmpeg(cmd, 60, self._is_cancelled)
                ok = rc == 0 and tmp_ok(tmp_path)
            if not ok and not self._is_cancelled():
                rc, r2 = run_ffmpeg(build_ffmpeg_cmd_hdr_fallback(
                    self._vpath, t, tmp_path, disp_w, disp_h, sar_applied),
                    60, self._is_cancelled)
                if rc == 0 and tmp_ok(tmp_path):
                    ok = True
                else:
                    last_reason = r2 or last_reason
            if not ok and not self._is_cancelled():
                rc, r3 = run_ffmpeg(build_ffmpeg_cmd(
                    self._vpath, t, tmp_path, disp_w, disp_h, sar_applied),
                    30, self._is_cancelled)
                if rc == 0 and tmp_ok(tmp_path):
                    ok = True
                else:
                    last_reason = r3 or last_reason
        else:
            rc, last_reason = run_ffmpeg(build_ffmpeg_cmd(
                self._vpath, t, tmp_path, disp_w, disp_h, sar_applied),
                30, self._is_cancelled)
            ok = rc == 0 and tmp_ok(tmp_path)
            if not ok and not self._is_cancelled():
                rc, r2 = run_ffmpeg(build_ffmpeg_cmd_fallback(
                    self._vpath, t, tmp_path, disp_w, disp_h, sar_applied),
                    30, self._is_cancelled)
                if rc == 0 and tmp_ok(tmp_path):
                    ok = True
                else:
                    last_reason = r2 or last_reason
        return ok, last_reason, rc

    def _task(self, i, t, disp_w, disp_h, sar_applied, base, hdr_info, is_hdr):
        if self._is_cancelled():
            self.result_ready.emit(i, "fail", "", "annulé", t)
            return
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="vfe_")
        os.close(tmp_fd)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        ok, last_reason, rc = self._cascade(
            t, tmp_path, disp_w, disp_h, sar_applied, hdr_info, is_hdr)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            self.result_ready.emit(i, "fail", "", last_reason or "raison inconnue", t)
            return
        try:
            img = Image.open(tmp_path).copy()
        except Exception as ex:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            self.result_ready.emit(i, "fail", "", f"décodage image : {ex}", t)
            return
        if self._do_filter and is_black_frame(np.array(img), threshold=self._black_thresh):
            bpath = ""
            try:
                os.makedirs(self._black_dir, exist_ok=True)
                bpath = os.path.join(self._black_dir, f"black_{tc_str(t)}.jpg")
                shutil.move(tmp_path, bpath)
            except Exception:
                bpath = ""
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            self.result_ready.emit(i, "black", bpath, "", t)
            return
        fname = frame_filename(base, i + 1, t)
        fpath = os.path.join(self._outdir, fname)
        try:
            shutil.move(tmp_path, fpath)
        except Exception as ex:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            self.result_ready.emit(i, "fail", "", f"déplacement : {ex}", t)
            return
        self.result_ready.emit(i, "ok", fpath, "", t)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cineblast VFE")
        self.cfg = load_config()
        self._ffmpeg_ok = ffmpeg_available()
        self.video_info = {}
        self._video_path = ""
        self._hdr_worker = None
        self._hdr_info = {}
        self._hdr_event = threading.Event()
        self._hdr_event.set()
        self._zscale_ok = None
        self._extracting = False
        self._cancel = False
        self._retrying = False
        self._failed_frames = []
        self._failed_tcs = []

        geo = QApplication.primaryScreen().availableGeometry()
        self._geo_w = geo.width()
        h = int(self.cfg.get("window_h", 1080))
        h = max(700, min(h, geo.height()))
        self.resize(1600, h)
        # LOT 4 (fix marges) : minimum explicite — désactive le "minimum
        # automatique" calculé par Qt, qui bloquait le rétrécissement
        # de la fenêtre et créait les marges lors des réductions.
        self.setMinimumWidth(400)

        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        self._build_zone_a(hbox)
        self._build_center(hbox)
        self._build_zone_d(hbox)

        vbox.addLayout(hbox, 1)
        vbox.addWidget(sep())

        # ── Zone E : statut en bas ──
        zone_e = QWidget()
        zone_e.setObjectName("zoneE")
        zone_e.setFixedHeight(28)
        ze = QHBoxLayout(zone_e)
        ze.setContentsMargins(12, 0, 12, 0)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        ze.addWidget(self._status_lbl)
        ze.addStretch()
        vbox.addWidget(zone_e)

        self.setCentralWidget(central)

        # gouverne : les réglages décident, la fenêtre suit
        self._c_tsize.currentIndexChanged.connect(lambda *_: self._apply_grid_params())
        self._c_cols.currentIndexChanged.connect(lambda *_: self._apply_grid_params())
        self._c_psize.currentIndexChanged.connect(lambda *_: self._apply_grid_params())
        self._apply_grid_params()

        vp = self.cfg.get("video_path", "")
        if vp and os.path.exists(vp):
            self._load_video_info(vp)

        self._preview_path = None
        self._preview_cache = {}
        self._black_paths = {}
        self._black_dir = os.path.join(tempfile.gettempdir(), "vfe_black_frames")
        self._mark_shortcut = None
        self._rebind_mark_key()
        self._reload_extraction_folder()
        QApplication.instance().installEventFilter(self)

        # LOT 10 : auto-save debouncé (400 ms) sur tous les réglages
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)
        for w in (self._sl_count, self._sl_intv):
            w.valueChanged.connect(lambda *_: self._auto_save())
        self._mode_count.clicked.connect(lambda *_: self._auto_save())
        self._mode_intv.clicked.connect(lambda *_: self._auto_save())
        self._sw_black.toggled.connect(lambda *_: self._auto_save())
        self._confirm_switch.toggled.connect(lambda *_: self._auto_save())
        self._seuil.textChanged.connect(lambda *_: self._auto_save())
        self._generic_entry.textChanged.connect(lambda *_: self._auto_save())
        self._mark_key_entry.textChanged.connect(lambda *_: self._auto_save())
        for algo, btn in self._tm_buttons.items():
            btn.toggled.connect(lambda *_: self._auto_save())
        for c in (self._c_tsize, self._c_cols, self._c_psize):
            c.currentIndexChanged.connect(lambda *_: self._auto_save())

        self._status("Configuration chargée depuis VFE_Config.json (lecture seule).")

    # ── helpers ────────────────────────────────────────────────
    def _status(self, msg, duration=4000):
        self._status_lbl.setText(msg)
        if getattr(self, "_status_timer", None) is not None:
            self._status_timer.stop()
        if duration:
            self._status_timer = QTimer(self)
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(lambda: self._status_lbl.setText(""))
            self._status_timer.start(duration)

    def _not_yet(self, what, lot):
        self._status(f"{what} : disponible au {lot}.")

    def _apply_grid_params(self):
        tsize = int(self._c_tsize.currentText().replace("px", "").strip())
        cols = int(self._c_cols.currentText())
        psize = int(self._c_psize.currentText().replace("px", "").strip())
        self._grid_widget.set_layout(tsize, cols)
        content_w = self._grid_widget.content_width(tsize, cols)
        self._mid.setFixedWidth(content_w)
        # LOT 4 (fix plafond écran) : la colonne droite ne mord JAMAIS
        # sur la grille. Sous le plafond : colonne pleine (psize + 52).
        # Au plafond : colonne compressée par la droite (espace restant),
        # minimum 220 px — même philosophie que l'ancienne app.
        avail_right = self._geo_w - 340 - content_w
        right_w = max(220, min(psize + 52, avail_right))
        self._zone_d.setFixedWidth(right_w)
        self._preview_box.setFixedHeight(max(120, round(psize * 9 / 16)))
        # LOT 4 : avertissement de troncature (pixels perdus gauche / droite)
        avail_prev = right_w - 32
        lost = psize - avail_prev
        if lost > 0:
            left = lost // 2
            right = lost - left
            self._trunc_lbl.setText(
                f"Aperçu tronqué : {left} px perdus à gauche · {right} px perdus à droite")
            self._trunc_lbl.setVisible(True)
        else:
            self._trunc_lbl.setVisible(False)
        self._target_w = min(340 + content_w + psize + 52, self._geo_w)
        self._do_resize()
        # 2e passe : laisse Qt rafraîchir ses contraintes, puis réapplique
        # la taille → le rétrécissement n'est plus jamais refusé.
        QTimer.singleShot(0, self._do_resize)

    def _do_resize(self):
        self.updateGeometry()
        self.resize(self._target_w, max(self.height(), 700))

    def _on_mode_change(self):
        count_on = self._mode_count.isChecked()
        self._count_block.setVisible(count_on)
        self._intv_block.setVisible(not count_on)
        self._update_plan()

    def _on_count_changed(self, v):
        snapped = max(5, min(1000, round(v / 5) * 5))
        if snapped != v:
            self._sl_count.blockSignals(True)
            self._sl_count.setValue(snapped)
            self._sl_count.blockSignals(False)
            v = snapped
        self._val_count.setText(str(v))
        self._update_plan()

    def _on_intv_changed(self, v):
        self._val_intv.setText(hms(v) if v >= 60 else f"{v} s")
        self._update_plan()

    def _on_black_filter_toggled(self, on):
        self._seuil.setEnabled(bool(on))
        col = TH.TEXT_SECOND if on else TH.TEXT_DISABLED
        self._lbl_seuil.setStyleSheet(f"color: {col}; font-size: 12px;")
        self._lbl_255.setStyleSheet(f"color: {col}; font-size: 12px;")

    def _open_outdir(self):
        od = self.cfg.get("output_dir", "")
        if od and os.path.isdir(od):
            QDesktopServices.openUrl(QUrl.fromLocalFile(od))
        else:
            self._status("Dossier d'extraction introuvable.")

    # ── LOT 4 : source vidéo ───────────────────────────────────
    def _pick_video(self):
        initial = self.cfg.get("last_video_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            initial,
            "Vidéos (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.m4v *.ts *.webm);;Tous (*.*)",
        )
        if p:
            self._load_video_info(p)
            self.cfg["video_path"] = p
            self.cfg["last_video_dir"] = os.path.dirname(p)
            self._auto_save()
            self._status(f"Vidéo chargée : {os.path.basename(p)}", 4000)

    def _load_video_info(self, path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self._info_lbl.setText("Fichier invalide")
            self._status("Impossible d'ouvrir la vidéo.")
            return
        self._video_path = path
        # les échecs appartiennent à l'ancienne vidéo → on les oublie
        self._failed_frames = []
        self._failed_tcs = []
        self._retry_btn.setEnabled(False)
        self._retry_btn.setText("Ré-extraire les échecs")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        fc = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        raw_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        raw_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur = fc / fps
        cap.release()
        disp_w, disp_h = get_display_size(path, raw_w, raw_h)
        sar_applied = (disp_w != raw_w)
        self.video_info = {
            "fps": fps, "frames": fc, "width": raw_w, "height": raw_h,
            "disp_w": disp_w, "disp_h": disp_h,
            "sar_applied": sar_applied, "duration": dur,
        }
        self._grid_widget.set_aspect(disp_w, disp_h)
        self._src_btn.set_full_text(os.path.basename(path))
        mb = os.path.getsize(path) / 1_048_576
        sar_note = f"\nAffiché     {disp_w}×{disp_h} (SAR)" if sar_applied else ""
        self._info_lbl.setText(
            f"Durée       {hms(dur)}\nRésolution  {raw_w}×{raw_h}{sar_note}\n"
            f"FPS         {fps:.2f}\nTaille      {mb:.1f} Mo"
        )
        self._update_plan()
        # détection HDR en arrière-plan
        self._hdr_label.setText("Analyse couleur en cours…")
        self._hdr_label.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        self._tm_block.setVisible(False)
        self._hdr_info = {}
        self._hdr_event.clear()
        self._hdr_worker = HdrWorker(path, self)
        self._hdr_worker.finished_hdr.connect(self._update_hdr_ui)
        self._hdr_worker.start()

    def _update_hdr_ui(self, hdr, path=""):
        if path and path != getattr(self, "_video_path", ""):
            return
        self._hdr_info = hdr
        self._hdr_event.set()
        is_hdr = bool(hdr.get("is_hdr"))
        transfer = str(hdr.get("transfer", "")).lower()
        self._hdr_badge.setObjectName("badge_warn" if is_hdr else "badge_off")
        self._hdr_badge.style().unpolish(self._hdr_badge)
        self._hdr_badge.style().polish(self._hdr_badge)
        if is_hdr:
            self._tm_block.setVisible(True)
            if "smpte2084" in transfer or "pq" in transfer:
                txt = "Pipeline HDR→SDR actif"
            elif "hlg" in transfer or "arib" in transfer:
                txt = "HLG détecté"
            else:
                txt = "HDR détecté (non PQ)"
            self._hdr_label.setText(txt)
            self._hdr_label.setStyleSheet(f"color: {TH.WARNING}; font-size: 12px;")
        else:
            self._tm_block.setVisible(False)
            self._hdr_label.setText("SDR — espace standard")
            self._hdr_label.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")

    def _update_plan(self):
        if not hasattr(self, "_plan_lbl"):
            return
        dur = self.video_info.get("duration", 0)
        if not dur:
            self._plan_lbl.setText("Chargez une vidéo pour prévisualiser le plan.")
            return
        mode = "count" if self._mode_count.isChecked() else "interval"
        targets = compute_targets(
            duration=dur,
            fps=self.video_info.get("fps"),
            mode=mode,
            count=self._sl_count.value(),
            interval=self._sl_intv.value(),
        )
        if not targets:
            self._plan_lbl.setText("Aucune frame à extraire.")
            return
        n = len(targets)
        first, last = targets[0], targets[-1]
        if mode == "count":
            if n == 1:
                txt = "Plan : 1 image au début de la vidéo."
            else:
                avg = (last - first) / (n - 1)
                txt = (f"Plan : {n} images entre {hms(first)} et {hms(last)}\n"
                       f"→ une toutes les {hms(avg)} environ")
        else:
            iv = self._sl_intv.value()
            txt = (f"Plan : {n} image(s) toutes les {iv} s\n"
                   f"→ de {hms(first)} à {hms(last)}")
        self._plan_lbl.setText(txt)

    # ── LOT 5 : dossiers ───────────────────────────────────────
    def _pick_output(self):
        initial = self.cfg.get("last_output_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        p = QFileDialog.getExistingDirectory(self, "Dossier d'extraction", initial)
        if p:
            self.cfg["output_dir"] = p
            self.cfg["last_output_dir"] = p
            self._out_btn.set_full_text(os.path.basename(p.rstrip("/\\")))
            self._auto_save()
            self._status("Dossier d'extraction défini.", 4000)

    def _pick_workdir(self):
        initial = self.cfg.get("last_work_dir", "")
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        p = QFileDialog.getExistingDirectory(self, "Dossier de travail", initial)
        if p:
            self.cfg["work_dir"] = p
            self.cfg["last_work_dir"] = p
            self._work_btn.set_full_text(dir_parent_label(p))
            self._auto_save()
            self._status("Dossier de travail défini.", 4000)

    def _current_tonemap(self):
        for algo, btn in self._tm_buttons.items():
            if btn.isChecked():
                return algo
        return "hable"

    # ── LOT 6 : grille réelle ──────────────────────────────────
    def _reload_extraction_folder(self):
        outdir = self.cfg.get("output_dir", "")
        if not outdir or not os.path.isdir(outdir):
            self._grid_widget.set_entries([])
            self._upd_badges()
            return
        jpgs = sorted((f for f in os.listdir(outdir)
                       if f.lower().endswith((".jpg", ".jpeg"))), key=str.lower)
        entries = [{"path": os.path.join(outdir, f),
                    "tc": _parse_tc_from_filename(f)} for f in jpgs]
        if not entries:
            vp = getattr(self, "_video_path", "") or self.cfg.get("video_path", "")
            if vp and os.path.exists(vp):
                self._grid_widget.set_empty_message(
                    "Aucune image extraite.\nLancez une extraction pour remplir la grille.")
            else:
                self._grid_widget.set_empty_message(
                    "Aucune vidéo chargée.\n"
                    "Choisissez un fichier source dans le panneau de gauche.")
        self._grid_widget.set_entries(entries)
        self._upd_badges()
        self._restore_marked()
        self._restore_preview()
        self._zone_c.verticalScrollBar().setValue(0)
        self._grid_widget.update()
        log.info("Grille rechargée : %d image(s)", len(entries))
        self._status(f"{len(entries)} image(s) chargée(s).", 4000)

    def _refresh_folder(self):
        outdir = self.cfg.get("output_dir", "")
        if not outdir or not os.path.isdir(outdir):
            self._status("Aucun dossier d'extraction défini ou inexistant.", 4000)
            return
        self._reload_extraction_folder()

    def _upd_badges(self):
        g = self._grid_widget
        self._badge_total.setText(f"{len(g.thumbs)} image(s)")
        n = len(g.sel)
        self._badge_sel.setText(f"{n} sélectionnée(s)")
        m = len(g.marked)
        self._badge_mark.setText(f"{m} marquée(s)")
        if hasattr(self, "_del_btn"):
            self._del_btn.setEnabled(bool(n))
        if hasattr(self, "_move_btn"):
            self._move_btn.setEnabled(bool(n or m))

    def _on_selection_changed(self):
        self._upd_badges()
        sel = self._grid_widget.sel
        if len(sel) == 1:
            self._show_preview(next(iter(sel)))
        elif not sel:
            self._reset_preview()
        else:
            self._prev_img.setPixmap(QPixmap())
            self._prev_img.setText(f"Sélection multiple\n({len(sel)} images)")

    def _show_preview(self, path):
        entry = self._grid_widget.thumb_by_path.get(path)
        if entry is None:
            return
        self._preview_path = path
        pix = self._preview_cache.get(path)
        if pix is None:
            pix = QPixmap(path)
            if pix.isNull():
                return
            self._preview_cache[path] = pix
            while len(self._preview_cache) > 8:
                self._preview_cache.pop(next(iter(self._preview_cache)))
        box_w = max(60, self._preview_box.width() - 8)
        box_h = max(60, self._preview_box.height() - 8)
        scaled = pix.scaled(box_w, box_h, Qt.KeepAspectRatio,
                            Qt.SmoothTransformation)
        self._prev_img.setText("")
        self._prev_img.setPixmap(scaled)
        self._fname_lbl.setText(os.path.basename(path))
        self._m1_lbl.setText(hms(entry["tc"]))
        self._m2_lbl.setText(f"{pix.width()}×{pix.height()} px")
        pos = self._grid_widget._position_of(path) + 1
        self._m3_lbl.setText(f"#{pos} / {len(self._grid_widget.thumbs)}")

    def _reshow_preview(self):
        """LOT 7 : redessine l'aperçu courant après un changement
        de taille d'aperçu (ou de gouverne de la colonne)."""
        pp = getattr(self, "_preview_path", None)
        if pp and pp in self._grid_widget.thumb_by_path:
            self._show_preview(pp)

    def _reset_preview(self):
        self._preview_path = None
        self._prev_img.setPixmap(QPixmap())
        self._prev_img.setText("Image placeholder\n(aperçu)")
        self._fname_lbl.setText("—")
        self._m1_lbl.setText("—")
        self._m2_lbl.setText("—")
        self._m3_lbl.setText("—")

    def eventFilter(self, obj, e):
        """LOT 7 (fix) + LOT 8 + LOT 9A : flèches, Suppr/Retour arrière,
        Ctrl+A (tout sélectionner) et Échap (désélectionner) globaux via
        un filtre applicatif. Exception : saisie réelle dans un champ,
        un combo ou une liste déroulante."""
        if e.type() == QEvent.Type.KeyPress:
            fw = QApplication.focusWidget()
            typing = isinstance(fw, (QLineEdit, QComboBox, QAbstractItemView))
            if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                           Qt.Key.Key_Up, Qt.Key.Key_Down):
                if not typing:
                    self._grid_widget.keyPressEvent(e)
                    return True
            elif e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                if not typing:
                    self._delete_selected()
                    return True
            elif (e.key() == Qt.Key.Key_A
                  and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
                if not typing:
                    self._select_all()
                    return True
            elif e.key() == Qt.Key.Key_Escape:
                if not typing:
                    self._clear_selection()
                    return True
        return super().eventFilter(obj, e)

    def _select_all(self):
        g = self._grid_widget
        if not g.thumbs:
            return
        g.sel = {en["path"] for en in g.thumbs}
        g._anchor = g.thumbs[0]["path"]
        g.update()
        g.selection_changed.emit()

    def _clear_selection(self):
        g = self._grid_widget
        if not g.sel:
            return
        g.sel.clear()
        g._anchor = None
        g.update()
        g.selection_changed.emit()

    def _mark_selection(self):
        g = self._grid_widget
        if not g.sel:
            self._status("Aucune image sélectionnée.")
            return
        if g.sel.issubset(g.marked):
            g.marked -= set(g.sel)
        else:
            g.marked |= set(g.sel)
        g.update()
        self._upd_badges()
        self._auto_save()

    def _unmark_all(self):
        g = self._grid_widget
        g.marked.clear()
        g.update()
        self._upd_badges()
        self._auto_save()

    def _rebind_mark_key(self):
        if getattr(self, "_mark_shortcut", None) is not None:
            self._mark_shortcut.setEnabled(False)
            self._mark_shortcut.deleteLater()
            self._mark_shortcut = None
        key = (self._mark_key_entry.text() or "").strip()
        if not key:
            return
        self._mark_shortcut = QShortcut(QKeySequence(key), self)
        self._mark_shortcut.activated.connect(self._on_mark_key_guarded)

    def _on_mark_key_guarded(self):
        fw = QApplication.focusWidget()
        if isinstance(fw, QLineEdit):
            return
        self._mark_selection()

    # ── LOT 8 : suppression / vider / déplacement ──────────────
    def _delete_selected(self):
        from PySide6.QtWidgets import QMessageBox
        g = self._grid_widget
        if not g.sel:
            return
        n = len(g.sel)
        if self.cfg.get("confirm_delete", True):
            r = QMessageBox.question(
                self, "Supprimer",
                f"Supprimer {n} image(s) sélectionnée(s) ?\n"
                "Les fichiers seront déplacés vers la corbeille.")
            if r != QMessageBox.StandardButton.Yes:
                return
        deleted = list(g.sel)
        first_pos = min(g._position_of(p) for p in deleted)
        errors = trash_files(deleted)
        log.info("Suppression : %d image(s) → corbeille%s",
                 len(deleted), f" ({len(errors)} erreur(s))" if errors else "")
        dset = set(deleted)
        for p in deleted:
            g.marked.discard(p)
            g.thumb_by_path.pop(p, None)
            self._preview_cache.pop(p, None)
        g.thumbs = [e for e in g.thumbs if e["path"] not in dset]
        g.sel.clear()
        g._anchor = None
        if errors:
            QMessageBox.warning(
                self, "Erreurs",
                "Fichier(s) non supprimé(s) :\n" +
                "\n".join(f"{os.path.basename(p)} : {ex}" for p, ex in errors))
        if not g.thumbs:
            g.clear_all()
            self._reset_preview()
            self._upd_badges()
            return
        new_pos = min(first_pos, len(g.thumbs) - 1)
        new_path = g.thumbs[new_pos]["path"]
        g.sel.add(new_path)
        g._anchor = new_path
        g.update()
        g.selection_changed.emit()
        g._ensure_visible(new_pos)
        self._status(f"{n} image(s) supprimée(s) → corbeille", 6000)
        self._auto_save()

    def _clear_output_dir(self):
        from PySide6.QtWidgets import QMessageBox
        if getattr(self, "_extracting", False):
            self._status("Attendez la fin de l'extraction en cours.", 4000)
            return
        outdir = self.cfg.get("output_dir", "")
        if not outdir or not os.path.isdir(outdir):
            self._status("Aucun dossier d'extraction défini ou inexistant.", 4000)
            return
        jpgs = [f for f in os.listdir(outdir)
                if f.lower().endswith((".jpg", ".jpeg"))]
        if not jpgs:
            self._status("Le dossier est déjà vide.", 4000)
            return
        r = QMessageBox.question(
            self, "Vider le dossier",
            f"Déplacer {len(jpgs)} fichier(s) JPG vers la corbeille ?")
        if r != QMessageBox.StandardButton.Yes:
            return
        errors = trash_files([os.path.join(outdir, f) for f in jpgs])
        log.info("Vider le dossier : %d fichier(s) → corbeille",
                 len(jpgs) - len(errors))
        self._grid_widget.clear_all()
        self._failed_frames = []
        self._failed_tcs = []
        self._retry_btn.setEnabled(False)
        self._retry_btn.setText("Ré-extraire les échecs")
        self._reset_preview()
        self._prog.setValue(0)
        self._prog_lbl.setText(
            f"{len(jpgs) - len(errors)} fichier(s) déplacé(s) vers la corbeille")
        self._upd_badges()

    def _next_num_in_workdir(self, workdir, generic):
        pat = re.compile(r"^" + re.escape(generic) + r"_(\d+)\.jpe?g$",
                         re.IGNORECASE)
        max_n = 0
        try:
            for f in os.listdir(workdir):
                m = pat.match(f)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        except Exception as ex:
            log.debug("_next_num_in_workdir : %s", ex)
        return max_n + 1

    def _move_to_workdir(self):
        g = self._grid_widget
        combined = g.sel | g.marked
        if not combined:
            self._status("Aucune image sélectionnée ni marquée.")
            return
        workdir = (self.cfg.get("work_dir", "") or "").strip()
        if not workdir or not os.path.isdir(workdir):
            self._status(f"Dossier de travail introuvable : {workdir}")
            return
        generic = (self._generic_entry.text() or "").strip() or "capture"
        paths = sorted(combined)
        n = len(paths)
        num = self._next_num_in_workdir(workdir, generic)
        moves = []
        for src in paths:
            while True:
                dst = os.path.join(workdir, f"{generic}_{num:04d}.jpg")
                if not os.path.exists(dst):
                    break
                num += 1
            moves.append((src, dst))
            num += 1
        ok = 0
        errors = []
        moved = set()
        for src, dst in moves:
            try:
                shutil.move(src, dst)
                ok += 1
                moved.add(src)
            except Exception as ex:
                errors.append(f"{os.path.basename(src)} → {ex}")
        log.info("Déplacement : %d/%d image(s) → %s", ok, n, workdir)
        for p in moved:
            g.sel.discard(p)
            g.marked.discard(p)
            g.thumb_by_path.pop(p, None)
            self._preview_cache.pop(p, None)
        g.thumbs = [e for e in g.thumbs if e["path"] not in moved]
        g._anchor = None
        g.update()
        self._reset_preview()
        self._upd_badges()
        msg = f"{ok}/{n} image(s) déplacée(s) vers {os.path.basename(workdir)}"
        if errors:
            msg += f"  ({len(errors)} erreur(s))"
        self._status(msg, 6000)
        self._auto_save()

    # ── LOT 10 : persistance de la configuration ───────────────
    def _collect_config(self):
        g = self._grid_widget
        try:
            thresh = int(self._seuil.text())
        except ValueError:
            thresh = 5
        return {
            "video_path": getattr(self, "_video_path", "") or self.cfg.get("video_path", ""),
            "output_dir": self.cfg.get("output_dir", ""),
            "work_dir": self.cfg.get("work_dir", ""),
            "generic_name": (self._generic_entry.text() or "").strip() or "capture",
            "mode": "count" if self._mode_count.isChecked() else "interval",
            "count_val": self._sl_count.value(),
            "interval_val": self._sl_intv.value(),
            "thumb_size": int(self._c_tsize.currentText().replace("px", "").strip()),
            "col_count": int(self._c_cols.currentText()),
            "preview_size": int(self._c_psize.currentText().replace("px", "").strip()),
            "window_size": self.cfg.get("window_size", "auto"),
            "sash_left": self.cfg.get("sash_left", 310),
            "sash_right": self.cfg.get("sash_right", 700),
            "confirm_delete": self._confirm_switch.isChecked(),
            "black_filter": self._sw_black.isChecked(),
            "black_threshold": thresh,
            "mark_key": (self._mark_key_entry.text() or "").strip(),
            "hdr_tonemap": self._current_tonemap(),
            "last_video_dir": self.cfg.get("last_video_dir", ""),
            "last_output_dir": self.cfg.get("last_output_dir", ""),
            "last_work_dir": self.cfg.get("last_work_dir", ""),
            "marked_files": sorted(os.path.basename(p) for p in g.marked),
            "last_preview_file": os.path.basename(self._preview_path)
            if getattr(self, "_preview_path", None) else "",
            "window_h": self.height(),
        }

    def _auto_save(self):
        self._save_timer.stop()
        self._save_timer.start(400)

    def _do_save(self):
        save_config(self._collect_config())

    def _save_action(self):
        self._do_save()
        self._status("Configuration sauvegardée.", 3000)

    def _restore_marked(self):
        saved = set(os.path.basename(p) for p in self.cfg.get("marked_files", []))
        if not saved:
            return
        g = self._grid_widget
        for e in g.thumbs:
            if os.path.basename(e["path"]) in saved:
                g.marked.add(e["path"])
        if g.marked:
            g.update()
            self._upd_badges()

    def _show_black_panel(self):
        """LOT 10B : panneau des frames noires exclues — vignettes 150 px
        cliquables (visionneuse lightbox 650 px)."""
        from PySide6.QtWidgets import (QGridLayout, QPushButton, QScrollArea,
                                       QVBoxLayout, QWidget)
        dlg = QDialog(self)
        dlg.setWindowTitle("Frames noires exclues")
        dlg.resize(720, 560)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)
        t = QLabel(f"{len(self._black_tcs)} frame(s) noire(s) exclue(s) de l'extraction.")
        t.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        v.addWidget(t)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        gridw = QWidget()
        gl = QGridLayout(gridw)
        gl.setContentsMargins(4, 4, 4, 4)
        gl.setSpacing(12)
        cols = 4
        for idx, tc in enumerate(self._black_tcs):
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            thumb = BlackThumb(self._black_paths.get(tc), tc)
            cl.addWidget(thumb, 0, Qt.AlignmentFlag.AlignHCenter)
            tl = QLabel(hms(tc))
            tl.setStyleSheet("color: %s; font-size: 12px; font-family: Consolas;"
                             % TH.TEXT_MUTED)
            tl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            cl.addWidget(tl)
            gl.addWidget(cell, idx // cols, idx % cols)
        # LOT 10B (fix) : rangées aimantées en haut, espacement 12 px de la
        # charte — l'espace vide part en bas au lieu d'écarter les rangées.
        gl.setRowStretch(gl.rowCount(), 1)
        scroll.setWidget(gridw)
        v.addWidget(scroll, 1)
        b = QPushButton("Fermer")
        b.setObjectName("ghost")
        b.setFixedHeight(30)
        b.clicked.connect(dlg.close)
        v.addWidget(b)
        dlg.exec()

    def _restore_preview(self):
        """LOT 10A : restaure la dernière image aperçue (persistée en
        nom de fichier, comme le marquage)."""
        saved = self.cfg.get("last_preview_file", "")
        if not saved:
            return
        g = self._grid_widget
        for e in g.thumbs:
            if os.path.basename(e["path"]) == saved:
                g.sel.clear()
                g.sel.add(e["path"])
                g._anchor = e["path"]
                g.update()
                g.selection_changed.emit()
                g._ensure_visible(g._position_of(e["path"]))
                return

    def closeEvent(self, e):
        self._cancel = True
        self._do_save()
        super().closeEvent(e)

    # ── LOT 5 : extraction ─────────────────────────────────────
    def _start_extraction(self, retry=False):
        if getattr(self, "_extracting", False):
            return
        if not self._ffmpeg_ok:
            self._status("ffmpeg absent — extraction impossible dans la version Qt.", 6000)
            return
        vp = getattr(self, "_video_path", "") or self.cfg.get("video_path", "")
        if not vp or not os.path.exists(vp):
            self._status("Veuillez choisir une vidéo.")
            return
        od = self.cfg.get("output_dir", "")
        if not od or not os.path.isdir(od):
            self._status("Veuillez choisir un dossier d'extraction.")
            return
        if not self.video_info:
            self._status("Informations vidéo non chargées.")
            return
        if retry:
            targets = list(self._failed_frames)
        else:
            flat = compute_targets(
                duration=self.video_info["duration"],
                fps=self.video_info.get("fps"),
                mode="count" if self._mode_count.isChecked() else "interval",
                count=self._sl_count.value(),
                interval=self._sl_intv.value(),
            )
            targets = list(enumerate(flat))
        if not targets:
            self._status("Aucune frame à extraire.")
            return
        self._extracting = True
        self._cancel = False
        self._retrying = retry
        if not retry:
            self._failed_frames = []
            self._failed_tcs = []
        self._run_btn.setEnabled(False)
        self._retry_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._prog.setValue(0)
        self._pending_results = {}
        self._next_flush = 0
        self._flushed = 0
        self._flush_tot = len(targets)
        self._black_tcs = []
        self._black_btn.setEnabled(False)
        self._extract_start = time.time()
        self._retry_recovered = 0
        self._extract_start = time.time()
        if not retry:
            self._grid_widget.clear_all()
            self._upd_badges()
            self._reset_preview()
            self._black_paths = {}
            shutil.rmtree(self._black_dir, ignore_errors=True)
        log.info("%s : %d frame(s) ciblée(s) — %s",
                 "Ré-extraction" if retry else "Extraction lancée",
                 len(targets), os.path.basename(vp))
        self._prog_lbl.setText("Initialisation…")
        self._worker = ExtractWorker(
            self, vp, od, targets,
            self._sw_black.isChecked(),
            int(self._seuil.text() or 5),
            self._current_tonemap(),
            lambda: self._cancel,
            self._black_dir,
        )
        self._worker.result_ready.connect(self._on_worker_result)
        self._worker.finished_all.connect(self._extract_done)
        self._worker.start()

    def _cancel_extraction(self):
        self._cancel = True
        self._cancel_btn.setEnabled(False)
        self._prog_lbl.setText("Annulation…")

    def _retry_failed(self):
        if getattr(self, "_extracting", False) or not self._failed_frames:
            return
        self._start_extraction(retry=True)

    def _progress_text(self, done, tot, t, extra=""):
        base = f"{done}/{tot} · {hms(t)}"
        if extra:
            base += f" · {extra}"
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
        return f"{base} · reste ~{eta}"

    def _on_worker_result(self, i, kind, fpath, reason, t):
        # Ré-extraction : traitement immédiat (pas de flush ordonné :
        # les indices sont ceux du plan d'origine, pas 0..n)
        if self._retrying:
            self._flushed += 1
            pct = int(self._flushed / max(1, self._flush_tot) * 100)
            self._prog.setValue(pct)
            if kind == "ok":
                self._retry_recovered += 1
                self._failed_frames = [(fi, ft) for (fi, ft) in self._failed_frames
                                       if not (fi == i and ft == t)]
                self._failed_tcs = [ft for (_, ft) in self._failed_frames]
                self._prog_lbl.setText(self._progress_text(self._flushed, self._flush_tot, t))
            else:
                log.warning("Ré-extraction échouée : frame %d (%s) : %s",
                            i + 1, hms(t), reason or "raison inconnue")
                self._prog_lbl.setText(self._progress_text(self._flushed, self._flush_tot, t, "échec"))
            return
        # Extraction normale : flush strictement ordonné
        self._pending_results[i] = (kind, fpath, reason, t)
        while self._next_flush in self._pending_results:
            k, fp, inf, tc = self._pending_results.pop(self._next_flush)
            self._flushed += 1
            pct = int(self._flushed / max(1, self._flush_tot) * 100)
            self._prog.setValue(pct)
            if k == "ok":
                g = self._grid_widget
                if fp and fp not in g.thumb_by_path:
                    g.thumbs.append({"path": fp, "tc": tc})
                    g.thumb_by_path[fp] = g.thumbs[-1]
                    g.updateGeometry()
                    g.update()
                    self._badge_total.setText(f"{len(g.thumbs)} image(s)")
                self._prog_lbl.setText(self._progress_text(self._flushed, self._flush_tot, tc))
            elif k == "black":
                self._black_tcs.append(tc)
                if fp:
                    self._black_paths[tc] = fp
                self._prog_lbl.setText(self._progress_text(self._flushed, self._flush_tot, tc, "noire"))
            else:
                self._failed_tcs.append(tc)
                self._failed_frames.append((self._next_flush, tc))
                log.warning("Échec frame %d (%s) : %s",
                            self._next_flush + 1, hms(tc), inf or "raison inconnue")
                self._prog_lbl.setText(self._progress_text(self._flushed, self._flush_tot, tc, "échec"))
            self._next_flush += 1

    def _extract_done(self):
        self._extracting = False
        retrying = self._retrying
        self._retrying = False
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        nf = len(self._failed_tcs)
        if retrying:
            log.info("Ré-extraction terminée : %d récupérée(s), %d échec(s) restant(s)%s",
                     self._retry_recovered, nf, "  [ANNULÉE]" if self._cancel else "")
            if self._cancel:
                self._prog_lbl.setText("Ré-extraction annulée")
            elif nf:
                self._retry_btn.setText(f"Ré-extraire les échecs  ({nf})")
                self._retry_btn.setEnabled(True)
                self._prog.setValue(100)
                self._prog_lbl.setText(f"Ré-extraction terminée · {nf} échec(s) restant(s)")
                self._status("Échec(s) restant(s) : " + " | ".join(hms(t) for t in self._failed_tcs), 0)
            else:
                self._retry_btn.setText("Ré-extraire les échecs")
                self._retry_btn.setEnabled(False)
                self._prog.setValue(100)
                self._prog_lbl.setText("Tous les échecs ont été récupérés")
                self._status("Ré-extraction terminée : tous les échecs récupérés.", 6000)
            return
        ok = self._flushed - len(self._black_tcs) - nf
        log.info("Extraction terminée : %d image(s), %d noire(s) filtrée(s), %d échec(s)%s",
                 ok, len(self._black_tcs), nf, "  [ANNULÉE]" if self._cancel else "")
        self._badge_total.setText(f"{ok} image(s)")
        if retrying:
            if nf:
                self._retry_btn.setText(f"Ré-extraire les échecs  ({nf})")
                self._retry_btn.setEnabled(True)
                self._prog.setValue(100)
                self._prog_lbl.setText(f"Ré-extraction terminée · {nf} échec(s) restant(s)")
                self._status("Échec(s) restant(s) : " + " | ".join(hms(t) for t in self._failed_tcs), 0)
            else:
                self._retry_btn.setText("Ré-extraire les échecs")
                self._retry_btn.setEnabled(False)
                self._prog.setValue(100)
                self._prog_lbl.setText("Tous les échecs ont été récupérés")
                self._status("Ré-extraction terminée : tous les échecs récupérés.", 6000)
            return
        self._reload_extraction_folder()
        if self._cancel:
            self._prog_lbl.setText(f"Annulé · {ok} image(s) sauvegardée(s)")
        elif nf:
            self._prog.setValue(100)
            self._prog_lbl.setText(f"Terminé · {ok} image(s) · {nf} échec(s)")
            self._retry_btn.setText(f"Ré-extraire les échecs  ({nf})")
            self._retry_btn.setEnabled(True)
            self._status(f"{nf} échec(s) d'extraction : " + " | ".join(hms(t) for t in self._failed_tcs), 0)
        else:
            self._prog.setValue(100)
            self._prog_lbl.setText(f"Terminé · {ok} image(s)")
            if self._black_tcs:
                self._status(
                    f"{len(self._black_tcs)} frame(s) noire(s) exclue(s) de l'extraction.",
                    6000)
        nb = len(self._black_tcs)
        self._black_btn.setText(
            f"Afficher les frames noires  ({nb})" if nb else "Afficher les frames noires")
        self._black_btn.setEnabled(nb > 0 and not self._cancel)

    # ── Zone A ─────────────────────────────────────────────────
    def _build_zone_a(self, hbox):
        cfg = self.cfg
        zone_a = QWidget()
        zone_a.setObjectName("zoneA")
        zone_a.setFixedWidth(340)
        za = QVBoxLayout(zone_a)
        za.setContentsMargins(0, 0, 0, 0)
        za.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("panelInner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # fichier source
        lay.addWidget(sect("fichier source"))
        vp = cfg.get("video_path", "")
        self._src_btn = PathButton(
            os.path.basename(vp) if vp and os.path.exists(vp) else "Parcourir")
        self._src_btn.setFixedHeight(32)
        self._src_btn.clicked.connect(self._pick_video)
        lay.addWidget(self._src_btn)

        # badges FFMPEG / HDR — écart vertical FIXE 20 px, indépendant du film
        badges_box = QVBoxLayout()
        badges_box.setContentsMargins(0, 0, 0, 0)
        badges_box.setSpacing(15)

        row = QHBoxLayout()
        row.setSpacing(8)
        ff_badge = QLabel("FFMPEG")
        ff_label = QLabel()
        if self._ffmpeg_ok:
            ff_badge.setObjectName("badge_success")
            ff_label.setText("Couleurs fidèles")
            ff_label.setStyleSheet(f"color: {TH.SUCCESS}; font-size: 12px;")
        else:
            ff_badge.setObjectName("badge_danger")
            ff_label.setText("ffmpeg absent — couleurs approximatives")
            ff_label.setStyleSheet(f"color: {TH.DANGER}; font-size: 12px;")
        row.addWidget(ff_badge)
        row.addWidget(ff_label)
        row.addStretch()
        badges_box.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._hdr_badge = QLabel("HDR10 PQ")
        self._hdr_badge.setObjectName("badge_off")
        self._hdr_label = QLabel("En attente d'analyse…")
        self._hdr_label.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        row.addWidget(self._hdr_badge)
        row.addWidget(self._hdr_label)
        row.addStretch()
        badges_box.addLayout(row)

        lay.addLayout(badges_box)

        align_badge_widths(ff_badge, self._hdr_badge)

        # tone mapping — visible uniquement si HDR (LOT 4)
        self._tm_block = QWidget()
        tmb = QVBoxLayout(self._tm_block)
        tmb.setContentsMargins(0, 0, 0, 0)
        tmb.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        tm_lbl = QLabel("Tone mapping")
        tm_lbl.setStyleSheet(f"color: {TH.WARNING}; font-size: 12px;")
        row.addWidget(tm_lbl)
        row.addStretch()
        tmb.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(8)
        tm_grp = QButtonGroup(self._tm_block)
        tm_grp.setExclusive(True)
        tm_cur = cfg.get("hdr_tonemap", "hable")
        self._tm_buttons = {}
        for algo in ["hable", "mobius", "reinhard"]:
            ab = QPushButton(algo.capitalize())
            ab.setObjectName("seg")
            ab.setCheckable(True)
            ab.setChecked(algo == tm_cur)
            ab.setFixedHeight(28)
            tm_grp.addButton(ab)
            self._tm_buttons[algo] = ab
            row.addWidget(ab, 1)
        tmb.addLayout(row)
        lay.addWidget(self._tm_block)
        self._tm_block.setVisible(False)

        self._info_lbl = QLabel("Aucun fichier chargé")
        self._info_lbl.setObjectName("mono")
        lay.addWidget(self._info_lbl)

        lay.addSpacing(10)
        lay.addWidget(sep_a())

        # dossier d'extraction
        lay.addWidget(sect("dossier d'extraction"))
        od = cfg.get("output_dir", "")
        self._out_btn = PathButton(
            os.path.basename(od.rstrip("/\\")) if od and os.path.isdir(od) else "Parcourir")
        self._out_btn.setFixedHeight(32)
        self._out_btn.clicked.connect(self._pick_output)
        lay.addWidget(self._out_btn)

        # dossier de travail
        lay.addWidget(sect("dossier de travail"))
        wd = cfg.get("work_dir", "")
        self._work_btn = PathButton(
            dir_parent_label(wd) if wd and os.path.isdir(wd) else "Parcourir")
        self._work_btn.setFixedHeight(32)
        self._work_btn.clicked.connect(self._pick_workdir)
        lay.addWidget(self._work_btn)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._generic_entry = QLineEdit(str(cfg.get("generic_name", "capture")))
        self._generic_entry.setFixedHeight(28)
        self._generic_entry.setToolTip(
            "Nom générique des fichiers déplacés : "
            "<nom>_0001.jpg, <nom>_0002.jpg, …")
        row.addWidget(self._generic_entry, 1)
        suf = QLabel("_0001.jpg")
        suf.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        row.addWidget(suf)
        lay.addLayout(row)

        self._move_btn = QPushButton("Déplacer sélection / marquées → travail")
        self._move_btn.setFixedHeight(30)
        self._move_btn.clicked.connect(self._move_to_workdir)
        self._move_btn.setEnabled(False)
        lay.addWidget(self._move_btn)

        lay.addSpacing(10)
        lay.addWidget(sep_a())

        # mode de capture
        lay.addWidget(sect("mode de capture"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._mode_grp = QButtonGroup(inner)
        self._mode_grp.setExclusive(True)
        self._mode_count = QPushButton("Nombre d'images")
        self._mode_intv = QPushButton("Intervalle (s)")
        for b in (self._mode_count, self._mode_intv):
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setFixedHeight(28)
            self._mode_grp.addButton(b)
            row.addWidget(b)
        lay.addLayout(row)
        mode = cfg.get("mode", "count")
        self._mode_count.setChecked(mode == "count")
        self._mode_intv.setChecked(mode == "interval")
        self._mode_count.clicked.connect(lambda: self._on_mode_change())
        self._mode_intv.clicked.connect(lambda: self._on_mode_change())

        # bloc slider nombre
        self._count_block = QWidget()
        cb = QVBoxLayout(self._count_block)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(4)
        row = QHBoxLayout()
        lbl_count = QLabel("Nombre d'images")
        lbl_count.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        self._val_count = QLabel("")
        self._val_count.setStyleSheet(f"color: {TH.ACCENT_TEXT}; font-weight: 600;")
        row.addWidget(lbl_count)
        row.addStretch()
        row.addWidget(self._val_count)
        cb.addLayout(row)
        self._sl_count = QSlider(Qt.Horizontal)
        self._sl_count.setRange(5, 1000)
        self._sl_count.setSingleStep(5)
        self._sl_count.setPageStep(50)
        self._sl_count.setValue(int(cfg.get("count_val", 20)))
        self._sl_count.valueChanged.connect(self._on_count_changed)
        cb.addWidget(self._sl_count)
        lay.addWidget(self._count_block)

        # bloc slider intervalle
        self._intv_block = QWidget()
        ib = QVBoxLayout(self._intv_block)
        ib.setContentsMargins(0, 0, 0, 0)
        ib.setSpacing(4)
        row = QHBoxLayout()
        lbl_intv = QLabel("Intervalle entre captures")
        lbl_intv.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        self._val_intv = QLabel("")
        self._val_intv.setStyleSheet(f"color: {TH.ACCENT_TEXT}; font-weight: 600;")
        row.addWidget(lbl_intv)
        row.addStretch()
        row.addWidget(self._val_intv)
        ib.addLayout(row)
        self._sl_intv = QSlider(Qt.Horizontal)
        self._sl_intv.setRange(5, 1800)
        self._sl_intv.setValue(int(cfg.get("interval_val", 30)))
        self._sl_intv.valueChanged.connect(self._on_intv_changed)
        ib.addWidget(self._sl_intv)
        lay.addWidget(self._intv_block)

        self._on_mode_change()
        self._on_count_changed(self._sl_count.value())
        self._on_intv_changed(self._sl_intv.value())

        # carte plan (réelle au LOT 4)
        card = QWidget()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        self._plan_lbl = QLabel("Chargez une vidéo pour prévisualiser le plan.")
        self._plan_lbl.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        cl.addWidget(self._plan_lbl)
        lay.addWidget(card)

        # filtre frames noires + seuil rapprochés, alignés à gauche
        black_box = QVBoxLayout()
        black_box.setContentsMargins(0, 0, 0, 0)
        black_box.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._sw_black = Switch()
        self._sw_black.setChecked(bool(cfg.get("black_filter", True)))
        row.addWidget(self._sw_black)
        row.addWidget(QLabel("Supprimer les frames noires"))
        row.addStretch()
        black_box.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._lbl_seuil = QLabel("Seuil :")
        self._lbl_seuil.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        row.addWidget(self._lbl_seuil)
        self._seuil = QLineEdit(str(int(cfg.get("black_threshold", 5))))
        self._seuil.setFixedWidth(44)
        self._seuil.setFixedHeight(28)
        self._seuil.setToolTip(
            "Seuil de noir : une image dont la luminance moyenne est sous "
            "cette valeur est considérée noire et filtrée.")
        row.addWidget(self._seuil)
        self._lbl_255 = QLabel("/255")
        self._lbl_255.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        row.addWidget(self._lbl_255)
        row.addStretch()
        black_box.addLayout(row)

        lay.addLayout(black_box)

        self._sw_black.toggled.connect(self._on_black_filter_toggled)
        self._on_black_filter_toggled(self._sw_black.isChecked())
        # row.addWidget(QLabel("/255"))
        # row.addStretch()
        # lay.addLayout(row)

        lay.addWidget(sep())

        # actions
        lay.addWidget(sect("actions"))
        self._run_btn = QPushButton("Extraire les frames")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._start_extraction)
        lay.addWidget(self._run_btn)

        row = QHBoxLayout()
        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setObjectName("ghost")
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.clicked.connect(self._cancel_extraction)
        self._cancel_btn.setEnabled(False)
        self._del_btn = QPushButton("Supprimer")
        self._del_btn.setObjectName("danger")
        self._del_btn.setFixedHeight(30)
        self._del_btn.clicked.connect(self._delete_selected)
        self._del_btn.setEnabled(False)
        row.addWidget(self._cancel_btn)
        row.addWidget(self._del_btn)
        lay.addLayout(row)

        self._clear_btn = QPushButton("Vider le dossier d'extraction")
        self._clear_btn.setObjectName("danger")
        self._clear_btn.setFixedHeight(30)
        self._clear_btn.clicked.connect(self._clear_output_dir)
        lay.addWidget(self._clear_btn)

        self._black_btn = QPushButton("Afficher les frames noires")
        self._black_btn.setFixedHeight(30)
        self._black_btn.clicked.connect(self._show_black_panel)
        self._black_btn.setEnabled(False)
        lay.addWidget(self._black_btn)

        self._retry_btn = QPushButton("Ré-extraire les échecs")
        self._retry_btn.setFixedHeight(30)
        self._retry_btn.clicked.connect(self._retry_failed)
        self._retry_btn.setEnabled(False)
        lay.addWidget(self._retry_btn)

        self._prog = QProgressBar()
        self._prog.setFixedHeight(4)
        self._prog.setRange(0, 100)
        self._prog.setValue(0)
        self._prog.setTextVisible(False)
        lay.addWidget(self._prog)
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        lay.addWidget(self._prog_lbl)

        row = QHBoxLayout()
        self._confirm_switch = Switch()
        self._confirm_switch.setChecked(bool(cfg.get("confirm_delete", True)))
        # LOT 8 (fix) : le switch pilote la confirmation en mémoire
        # (le fichier VFE_Config.json reste inchangé jusqu'au LOT 10)
        self._confirm_switch.toggled.connect(
            lambda on: self.cfg.update({"confirm_delete": bool(on)}))
        row.addWidget(self._confirm_switch)
        row.addWidget(QLabel("Demander confirmation avant suppression"))
        row.addStretch()
        lay.addLayout(row)

        lay.addSpacing(12)
        self._save_btn = QPushButton("Sauvegarder la configuration")
        self._save_btn.setObjectName("ghost")
        self._save_btn.setFixedHeight(32)
        self._save_btn.clicked.connect(self._save_action)
        lay.addWidget(self._save_btn)

        scroll.setWidget(inner)
        za.addWidget(scroll)
        hbox.addWidget(zone_a)

    # ── Centre : Zone B + Zone C ───────────────────────────────
    def _build_center(self, hbox):
        cfg = self.cfg
        mid = QWidget()
        self._mid = mid
        midbox = QVBoxLayout(mid)
        midbox.setContentsMargins(0, 0, 0, 0)
        midbox.setSpacing(0)

        zone_b = QWidget()
        zone_b.setObjectName("zoneB")
        zone_b.setFixedHeight(44)
        zb = QHBoxLayout(zone_b)
        zb.setContentsMargins(12, 0, 12, 0)
        zb.setSpacing(8)

        titre = QLabel("Vignettes")
        titre.setStyleSheet("font-weight: 600;")
        zb.addWidget(titre)
        self._badge_total = QLabel("0 image(s)")
        self._badge_total.setObjectName("badge")
        self._badge_total.setFixedHeight(28)
        zb.addWidget(self._badge_total)
        self._badge_sel = QLabel("")
        self._badge_sel.setObjectName("badge_sel")
        self._badge_sel.setFixedHeight(28)
        zb.addWidget(self._badge_sel)
        self._badge_mark = QLabel("")
        self._badge_mark.setObjectName("badge_mark")
        self._badge_mark.setFixedHeight(28)
        zb.addWidget(self._badge_mark)
        zb.addStretch()

        unmark = QPushButton("Tout démarquer")
        unmark.setObjectName("ghost")
        unmark.setFixedHeight(28)
        unmark.clicked.connect(self._unmark_all)
        zb.addWidget(unmark)
        mark = QPushButton("Marquer")
        mark.setObjectName("ghost")
        mark.setFixedHeight(28)
        mark.clicked.connect(self._mark_selection)
        zb.addWidget(mark)
        zb.addWidget(QLabel("Marquer :"))
        self._mark_key_entry = QLineEdit(str(cfg.get("mark_key", "s")))
        self._mark_key_entry.setFixedWidth(32)
        self._mark_key_entry.setFixedHeight(28)
        self._mark_key_entry.setAlignment(Qt.AlignCenter)
        self._mark_key_entry.setToolTip(
            "Touche de marquage de la sélection (1 caractère).")
        self._mark_key_entry.textChanged.connect(lambda *_: self._rebind_mark_key())
        zb.addWidget(self._mark_key_entry)
        zb.addWidget(QLabel("Vignettes :"))
        self._c_tsize = QComboBox()
        self._c_tsize.addItems(["150 px", "200 px", "250 px", "300 px"])
        i = self._c_tsize.findText(f"{int(cfg.get('thumb_size', 150))} px")
        if i >= 0:
            self._c_tsize.setCurrentIndex(i)
        self._c_tsize.setFixedHeight(28)
        self._c_tsize.setToolTip("Taille des vignettes — gouverne la grille.")
        zb.addWidget(self._c_tsize)
        zb.addWidget(QLabel("Colonnes :"))
        self._c_cols = QComboBox()
        self._c_cols.addItems(["3", "4", "5", "6"])
        i = self._c_cols.findText(str(int(cfg.get("col_count", 4))))
        if i >= 0:
            self._c_cols.setCurrentIndex(i)
        self._c_cols.setFixedHeight(28)
        self._c_cols.setToolTip("Nombre de colonnes — gouverne la grille.")
        zb.addWidget(self._c_cols)
        refresh = QPushButton("Rafraîchir")
        refresh.setObjectName("ghost")
        refresh.setFixedHeight(28)
        refresh.clicked.connect(self._refresh_folder)
        zb.addWidget(refresh)

        midbox.addWidget(zone_b)
        midbox.addWidget(sep())

        self._zone_c = QScrollArea()
        self._zone_c.setObjectName("zoneC")
        self._zone_c.setWidgetResizable(True)
        self._zone_c.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._zone_c.setFrameShape(QScrollArea.NoFrame)
        self._grid_widget = ThumbCanvas(self._zone_c)
        self._grid_widget.selection_changed.connect(self._on_selection_changed)
        self._zone_c.setWidget(self._grid_widget)
        midbox.addWidget(self._zone_c, 1)

        hbox.addWidget(mid, 1)

    # ── Zone D ─────────────────────────────────────────────────
    def _build_zone_d(self, hbox):
        cfg = self.cfg
        zone_d = QWidget()
        zone_d.setObjectName("zoneD")
        self._zone_d = zone_d
        zd = QVBoxLayout(zone_d)
        zd.setContentsMargins(16, 16, 16, 16)
        zd.setSpacing(12)

        zd.addWidget(sect("aperçu"))

        box = QWidget()
        box.setObjectName("previewBox")
        self._preview_box = box
        bl = QVBoxLayout(box)
        self._prev_img = QLabel("Image placeholder\n(aperçu)")
        self._prev_img.setAlignment(Qt.AlignCenter)
        self._prev_img.setStyleSheet(f"color: {TH.TEXT_MUTED}; font-size: 12px;")
        self._prev_img.setScaledContents(False)
        bl.addWidget(self._prev_img)
        zd.addWidget(box)

        # LOT 4 : avertissement de troncature de l'aperçu (orange charte)
        self._trunc_lbl = QLabel("")
        self._trunc_lbl.setStyleSheet(f"color: {TH.WARNING}; font-size: 12px;")
        self._trunc_lbl.setWordWrap(True)
        self._trunc_lbl.setVisible(False)
        zd.addWidget(self._trunc_lbl)

        self._fname_lbl = QLabel("—")
        self._fname_lbl.setObjectName("filename")
        zd.addWidget(self._fname_lbl)

        self._m1_lbl = QLabel("—")
        self._m1_lbl.setObjectName("mono")
        zd.addWidget(self._m1_lbl)
        self._m2_lbl = QLabel("—")
        self._m2_lbl.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        zd.addWidget(self._m2_lbl)
        self._m3_lbl = QLabel("—")
        self._m3_lbl.setStyleSheet(f"color: {TH.TEXT_SECOND}; font-size: 12px;")
        zd.addWidget(self._m3_lbl)

        zd.addStretch()

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Taille :"))
        self._c_psize = QComboBox()
        self._c_psize.addItems([f"{v} px" for v in range(200, 701, 50)])
        i = self._c_psize.findText(f"{int(cfg.get('preview_size', 280))} px")
        if i >= 0:
            self._c_psize.setCurrentIndex(i)
        self._c_psize.setFixedHeight(28)
        self._c_psize.setToolTip("Largeur de l'aperçu — gouverne la colonne de droite.")
        row.addWidget(self._c_psize)
        self._c_psize.currentIndexChanged.connect(
            lambda *_: QTimer.singleShot(0, self._reshow_preview))
        row.addStretch()
        zd.addLayout(row)

        open_btn = QPushButton("Ouvrir dans le dossier")
        open_btn.setFixedHeight(32)
        open_btn.clicked.connect(self._open_outdir)
        zd.addWidget(open_btn)

        hbox.addWidget(zone_d)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "app_icon.png")
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()