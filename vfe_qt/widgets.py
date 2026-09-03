# -*- coding: utf-8 -*-
"""Cineblast VFE — widgets custom Qt (LOT 3)."""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from theme import (
    ACCENT,
    ACCENT_BORDER,
    BORDER_SUBTLE,
    INPUT_BG,
    ON_ACCENT,
    SURFACE_CARD,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


class Switch(QAbstractButton):
    """Interrupteur custom — remplace les checkboxes natives."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(lambda *_: self.update())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT))
        else:
            p.setPen(QColor(BORDER_SUBTLE))
            p.setBrush(QColor(INPUT_BG))
        p.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 10, 10)
        d = 14
        y = (self.height() - d) // 2
        x = 3 if not on else self.width() - d - 3
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TEXT_PRIMARY))
        p.drawEllipse(x, y, d, d)
        if self.hasFocus():
            p.setPen(QPen(QColor(ACCENT_BORDER), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 2, self.height() - 2),
                              10, 10)
        p.end()


class PathButton(QPushButton):
    """Bouton de chemin : ellipse (…) si trop long, tooltip = chemin complet."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.set_full_text(text)

    def set_full_text(self, t):
        self._full = t
        self.setToolTip(t)
        self._elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        fm = self.fontMetrics()
        self.setText(fm.elidedText(self._full, Qt.ElideRight, max(40, self.width() - 24)))


class Thumb(QWidget):
    """Vignette : radius 6, bordure 1, sélection 2 ambre,
    badge marqué plein ambre, timecode Consolas 12 en bas à droite."""

    def __init__(self, tc, selected=False, marked=False, parent=None):
        super().__init__(parent)
        self.tc = tc
        self.selected = selected
        self.marked = marked
        self.setFixedSize(250, 140)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setBrush(QColor(SURFACE_CARD))
        if self.selected:
            p.setPen(QPen(QColor(ACCENT), 2))
        else:
            p.setPen(QPen(QColor(BORDER_SUBTLE), 1))
        p.drawRoundedRect(rect, 6, 6)

        if self.marked:
            bx = self.width() - 24
            by = 8
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(QRectF(bx, by, 16, 16), 4, 4)
            p.setPen(QPen(QColor(ON_ACCENT), 2))
            p.drawLine(int(bx + 4), int(by + 8), int(bx + 7), int(by + 11))
            p.drawLine(int(bx + 7), int(by + 11), int(bx + 12), int(by + 5))

        f = QFont("Consolas")
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(TEXT_MUTED))
        p.drawText(
            QRectF(0, self.height() - 24, self.width() - 8, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            self.tc,
        )
        p.end()


class ThumbGrid(QWidget):
    """Grille gouvernée par les réglages (colonnes + taille), jamais par la fenêtre."""

    SPACING = 12
    MARGIN  = 16

    def __init__(self, thumbs, thumb_w=250, cols=5, parent=None):
        super().__init__(parent)
        self.setObjectName("panelInner")
        self._grid = QGridLayout(self)
        self._grid.setSpacing(self.SPACING)
        self._grid.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self._grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._widgets = [Thumb(tc, selected=sel, marked=mk) for (tc, sel, mk) in thumbs]
        self._cols = -1
        self._thumb_w = -1
        self.set_layout(thumb_w, cols)

    @staticmethod
    def thumb_height(thumb_w):
        return max(56, round(thumb_w * 9 / 16))

    def content_width(self, thumb_w, cols):
        return cols * thumb_w + (cols - 1) * self.SPACING + 2 * self.MARGIN

    def set_layout(self, thumb_w, cols):
        cols = max(1, min(6, cols))
        if cols == self._cols and thumb_w == self._thumb_w:
            return
        self._cols = cols
        self._thumb_w = thumb_w
        h = self.thumb_height(thumb_w)
        for wgt in self._widgets:
            wgt.setFixedSize(thumb_w, h)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        for i, wgt in enumerate(self._widgets):
            self._grid.addWidget(wgt, i // cols, i % cols)
            wgt.show()


def sect(text):
    lbl = QLabel(text)
    lbl.setObjectName("sect")
    return lbl


def sep():
    f = QFrame()
    f.setObjectName("sep")
    f.setFixedHeight(1)
    return f


def align_badge_widths(*badges):
    """Largeur identique, calée sur le texte le plus large ; hauteur 28 px."""
    f = QFont("Segoe UI")
    f.setPixelSize(11)
    fm = QFontMetrics(f)
    w = max(fm.horizontalAdvance(b.text()) for b in badges) + 18
    for b in badges:
        b.setFixedWidth(w)
        b.setFixedHeight(28)
        b.setAlignment(Qt.AlignCenter)