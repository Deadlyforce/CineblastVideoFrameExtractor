# -*- coding: utf-8 -*-
"""Cineblast VFE — grille de vignettes Qt virtualisée (LOT 6).
Ne dessine que les cellules visibles ; cache QPixmap borné."""

from collections import OrderedDict

from PySide6.QtCore import Qt, QRect, QRectF, QSize, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImageReader,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from vfe_utils import hms

import theme as TH

PAD = 16     # grid.padding
GAP = 12     # grid.gap
RADIUS = 6   # grid.thumb.radius


class ThumbCanvas(QWidget):
    """Widget contenu dans la QScrollArea : hauteur = contenu total,
    le paintEvent ne dessine que la fenêtre visible."""

    selection_changed = Signal()

    def __init__(self, scroll_area, parent=None):
        super().__init__(parent)
        self._scroll = scroll_area
        self.thumbs = []
        self.thumb_by_path = {}
        self.sel = set()
        self.marked = set()
        self.cols = 5
        self.thumb_w = 250
        self.thumb_h = 140
        self._aspect = None
        self._pix_cache = OrderedDict()
        self._MAX_CACHE = 120
        self._rubber = None
        self._press_pos = None
        self._ctrl = False
        self._shift = False
        self._anchor = None
        self._hover = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    # ── données / réglages ─────────────────────────────────────
    def set_layout(self, thumb_w, cols):
        self.thumb_w = int(thumb_w)
        self.cols = max(1, min(6, int(cols)))
        self.thumb_h = self._thumb_height()
        self.updateGeometry()
        self.update()

    def content_width(self, thumb_w, cols):
        """Largeur totale nécessaire par la grille — sert à la gouverne
        de la fenêtre (mêmes constantes que le paint : GAP et PAD)."""
        cols = max(1, min(6, int(cols)))
        return cols * int(thumb_w) + (cols - 1) * GAP + 2 * PAD

    def set_aspect(self, disp_w, disp_h):
        self._aspect = (disp_w, disp_h) if disp_w and disp_h else None
        self.thumb_h = self._thumb_height()
        self.updateGeometry()
        self.update()

    def _thumb_height(self):
        w, h = self._aspect or (16, 9)
        return max(40, round(self.thumb_w * h / w))

    def set_entries(self, entries):
        self.thumbs = entries
        self.thumb_by_path = {e["path"]: e for e in entries}
        paths = set(self.thumb_by_path)
        self.marked &= paths
        self.sel.clear()
        self._anchor = None
        self._pix_cache.clear()
        self.updateGeometry()
        self.update()
        self.selection_changed.emit()

    def clear_all(self):
        self.thumbs = []
        self.thumb_by_path = {}
        self.sel.clear()
        self.marked.clear()
        self._anchor = None
        self._pix_cache.clear()
        self.updateGeometry()
        self.update()
        self.selection_changed.emit()

    # ── géométrie ──────────────────────────────────────────────
    def _rows(self):
        n = len(self.thumbs)
        return (n + self.cols - 1) // self.cols if n else 0

    def _cell_w(self):
        return self.thumb_w + GAP

    def _cell_h(self):
        return self.thumb_h + GAP

    def _content_height(self):
        rows = self._rows()
        h = rows * self._cell_h() - (GAP if rows else 0) + 2 * PAD
        return max(h, 1)

    def sizeHint(self):
        """La scroll area (widgetResizable) dimensionne le widget d'après
        ce sizeHint : hauteur = contenu, largeur = viewport.
        Plus aucune boucle resize/resizeEvent (cause du stack overflow)."""
        w = self.width() if self.width() > 0 else 100
        return QSize(w, self._content_height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def _rect_for_index(self, idx):
        row, col = divmod(idx, self.cols)
        return QRect(PAD + col * self._cell_w(), PAD + row * self._cell_h(),
                     self.thumb_w, self.thumb_h)

    def _index_at(self, pos):
        if pos.x() < PAD or pos.y() < PAD:
            return -1
        col = (pos.x() - PAD) // self._cell_w()
        row = (pos.y() - PAD) // self._cell_h()
        if col >= self.cols:
            return -1
        idx = row * self.cols + col
        if idx >= len(self.thumbs):
            return -1
        if not self._rect_for_index(idx).contains(pos):
            return -1
        return idx

    def _position_of(self, path):
        e = self.thumb_by_path.get(path)
        if e is None:
            return -1
        try:
            return self.thumbs.index(e)
        except ValueError:
            return -1

    # ── dessin ─────────────────────────────────────────────────
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(e.rect(), QColor(TH.BG_APP))
        if not self.thumbs:
            f = QFont("Segoe UI")
            f.setPixelSize(13)
            p.setFont(f)
            p.setPen(QColor(TH.TEXT_MUTED))
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                       "Aucune image extraite.")
            p.end()
            return
        vis = e.rect()
        r0 = max(0, (vis.top() - PAD) // self._cell_h())
        r1 = min(self._rows() - 1, (vis.bottom() - PAD) // self._cell_h())
        for row in range(r0, r1 + 1):
            for col in range(self.cols):
                idx = row * self.cols + col
                if idx >= len(self.thumbs):
                    break
                self._draw_cell(p, idx)
        if self._rubber is not None:
            p.setPen(QPen(QColor(TH.ACCENT), 2, Qt.PenStyle.DashLine))
            p.setBrush(QBrush(QColor(TH.ACCENT_SUBTLE)))
            p.drawRect(self._rubber)
        p.end()

    def _draw_cell(self, p, idx):
        e = self.thumbs[idx]
        path = e["path"]
        r = self._rect_for_index(idx)
        selected = path in self.sel
        hovered = path == self._hover
        if selected:
            p.setBrush(QColor(TH.ACCENT_SUBTLE))
            p.setPen(QPen(QColor(TH.ACCENT), 2))
        elif hovered:
            p.setBrush(QColor(TH.SURFACE_ELEV))
            p.setPen(QPen(QColor(TH.BORDER_STRONG), 1))
        else:
            p.setBrush(QColor(TH.SURFACE_CARD))
            p.setPen(QPen(QColor(TH.BORDER_SUBTLE), 1))
        p.drawRoundedRect(QRectF(r), RADIUS, RADIUS)
        pix = self._pixmap_for(path)
        if pix is not None:
            ir = r.adjusted(2, 2, -2, -2)
            p.setClipRect(ir)
            p.drawPixmap(ir, pix)
            p.setClipping(False)
        f = QFont("Consolas")
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(TH.TEXT_MUTED))
        p.drawText(QRectF(r.left(), r.bottom() - 22, r.width() - 8, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   hms(e["tc"]))
        if path in self.marked:
            bx = r.right() - 24
            by = r.top() + 8
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(TH.ACCENT))
            p.drawRoundedRect(QRectF(bx, by, 16, 16), 4, 4)
            p.setPen(QPen(QColor(TH.ON_ACCENT), 2))
            p.drawLine(int(bx + 4), int(by + 8), int(bx + 7), int(by + 11))
            p.drawLine(int(bx + 7), int(by + 11), int(bx + 12), int(by + 5))

    def _pixmap_for(self, path):
        key = (path, self.thumb_w, self.thumb_h)
        cached = self._pix_cache.get(key)
        if cached is not None:
            self._pix_cache.move_to_end(key)
            return cached
        try:
            reader = QImageReader(path)
            reader.setScaledSize(QSize(max(1, self.thumb_w - 4),
                                       max(1, self.thumb_h - 4)))
            img = reader.read()
            if img.isNull():
                return None
            pix = QPixmap.fromImage(img)
        except Exception:
            return None
        self._pix_cache[key] = pix
        while len(self._pix_cache) > self._MAX_CACHE:
            self._pix_cache.popitem(last=False)
        return pix

    # ── souris ─────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        self._press_pos = e.position().toPoint()
        self._ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._rubber = None
        e.accept()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._press_pos is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            if self._rubber is None and \
                    (pos - self._press_pos).manhattanLength() > 5:
                self._rubber = QRect(self._press_pos, pos).normalized()
                if not self._ctrl and not self._shift:
                    self.sel.clear()
            if self._rubber is not None:
                self._rubber = QRect(self._press_pos, pos).normalized()
                self._select_rubber()
                self.update()
            return
        idx = self._index_at(pos)
        path = self.thumbs[idx]["path"] if idx >= 0 else None
        if path != self._hover:
            self._hover = path
            self.setCursor(Qt.CursorShape.PointingHandCursor if path
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position().toPoint()
        was_rubber = self._rubber is not None
        self._rubber = None
        self._press_pos = None
        if was_rubber:
            self.update()
            self.selection_changed.emit()
            return
        idx = self._index_at(pos)
        if idx >= 0:
            path = self.thumbs[idx]["path"]
            if self._ctrl:
                if path in self.sel:
                    self.sel.discard(path)
                else:
                    self.sel.add(path)
                self._anchor = path
            elif self._shift and self._anchor in self.thumb_by_path:
                a = self._position_of(self._anchor)
                lo, hi = sorted((a, idx))
                self.sel.clear()
                for i2 in range(lo, hi + 1):
                    self.sel.add(self.thumbs[i2]["path"])
                self._anchor = path
            else:
                if path in self.sel and len(self.sel) == 1:
                    self.sel.clear()
                    self._anchor = None
                else:
                    self.sel.clear()
                    self.sel.add(path)
                    self._anchor = path
        else:
            if not self._ctrl and not self._shift:
                self.sel.clear()
                self._anchor = None
        self.update()
        self.selection_changed.emit()

    def _select_rubber(self):
        new = set()
        r0 = max(0, (self._rubber.top() - PAD) // self._cell_h())
        r1 = min(self._rows() - 1, (self._rubber.bottom() - PAD) // self._cell_h())
        for row in range(r0, r1 + 1):
            for col in range(self.cols):
                idx = row * self.cols + col
                if idx >= len(self.thumbs):
                    break
                if self._rect_for_index(idx).intersects(self._rubber):
                    new.add(self.thumbs[idx]["path"])
        if self._ctrl or self._shift:
            self.sel |= new
        else:
            self.sel = new

    # ── clavier ────────────────────────────────────────────────
    def keyPressEvent(self, e):
        if not self.thumbs:
            return
        k = e.key()
        if k not in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                     Qt.Key.Key_Up, Qt.Key.Key_Down):
            return
        if len(self.sel) == 1:
            cur = self._position_of(next(iter(self.sel)))
        elif self._anchor in self.thumb_by_path:
            cur = self._position_of(self._anchor)
        else:
            cur = -1
        if k == Qt.Key.Key_Right:
            new = cur + 1
        elif k == Qt.Key.Key_Left:
            new = cur - 1
        elif k == Qt.Key.Key_Down:
            new = cur + self.cols
        else:
            new = cur - self.cols
        new = max(0, min(new, len(self.thumbs) - 1))
        if new == cur:
            return
        path = self.thumbs[new]["path"]
        self.sel.clear()
        self.sel.add(path)
        self._anchor = path
        self.update()
        self.selection_changed.emit()
        self._ensure_visible(new)

    def _ensure_visible(self, idx):
        r = self._rect_for_index(idx)
        vsb = self._scroll.verticalScrollBar()
        top = vsb.value()
        vis_h = self._scroll.viewport().height()
        if r.top() < top:
            vsb.setValue(max(0, r.top() - PAD))
        elif r.bottom() > top + vis_h:
            vsb.setValue(r.bottom() + PAD - vis_h)