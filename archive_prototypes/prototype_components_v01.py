# -*- coding: utf-8 -*-
"""
Cineblast VFE — LOT 2A : prototype composants PySide6
Fichier : vfe_qt/prototype_components_v01.py
Objectif : valider visuellement le thème (LOT 1C) dans Qt.
Aucune logique métier ici.
"""

import sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

# ─────────────────────────────────────────────────────────────
# Tokens LOT 1C-A (palette) / LOT 1C-C (mesures)
# ─────────────────────────────────────────────────────────────
BG_APP        = "#181512"
SURFACE_PANEL = "#1E1A16"
SURFACE_CARD  = "#242019"
SURFACE_ELEV  = "#2A241D"
INPUT_BG      = "#322A22"
BORDER_SUBTLE = "#3B332A"
BORDER_STRONG = "#4C4135"
TEXT_PRIMARY  = "#EFE7DB"
TEXT_SECOND   = "#C0B3A2"
TEXT_MUTED    = "#8D8070"
TEXT_DISABLED = "#6E6357"
ON_ACCENT     = "#241407"
ACCENT        = "#E0975A"
ACCENT_HOVER  = "#ECAB6E"
ACCENT_PRESSED= "#C97F42"
ACCENT_SUBTLE = "#3B2A1B"
ACCENT_BORDER = "#A6683B"
ACCENT_TEXT   = "#F2B277"
SUCCESS       = "#9CB883"
WARNING       = "#D6B25A"
DANGER        = "#C86455"

QSS = f"""
QMainWindow {{ background-color: {BG_APP}; }}
QWidget {{ background-color: {BG_APP}; color: {TEXT_PRIMARY};
           font-family: "Segoe UI"; font-size: 13px; }}
QLabel {{ background: transparent; }}
QLabel#sect {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#title {{ color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 600; }}

QPushButton {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 0 12px;
}}
QPushButton:hover {{ background-color: {SURFACE_ELEV}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background-color: {SURFACE_CARD}; }}
QPushButton:disabled {{ color: {TEXT_DISABLED}; background-color: {SURFACE_CARD}; }}

QPushButton#primary {{
    background-color: {ACCENT};
    color: {ON_ACCENT};
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background-color: {ACCENT_PRESSED}; }}

QPushButton#danger {{
    background-color: {DANGER};
    color: {ON_ACCENT};
    border: none;
}}
QPushButton#danger:hover {{ background-color: #D4796B; }}

QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {BORDER_SUBTLE};
    color: {TEXT_SECOND};
}}

QPushButton#seg:checked {{
    background-color: {ACCENT_SUBTLE};
    color: {ACCENT_TEXT};
    border: 1px solid {ACCENT_BORDER};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {INPUT_BG};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: {ACCENT};
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}

QComboBox {{
    background-color: {INPUT_BG};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 0 10px;
}}
QComboBox:hover {{ border-color: {BORDER_STRONG}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {ACCENT_SUBTLE};
    selection-color: {ACCENT_TEXT};
}}

QLabel#badge {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    color: {TEXT_SECOND};
    font-size: 11px;
    padding: 2px 8px;
}}
QLabel#badge_accent {{
    background-color: {ACCENT_SUBTLE};
    border: 1px solid {ACCENT_BORDER};
    border-radius: 4px;
    color: {ACCENT_TEXT};
    font-size: 11px;
    padding: 2px 8px;
}}

QWidget#card {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
}}
"""


class Switch(QAbstractButton):
    """Interrupteur custom — remplace les checkboxes natives."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(lambda *_: self.update())

    def sizeHint(self):
        return QSize(36, 20)

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
        p.end()


class Sandbox(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cineblast VFE — prototype composants (LOT 2A)")
        self.resize(720, 900)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(20)

        titre = QLabel("Prototype de composants — thème darkroom ambre")
        titre.setObjectName("title")
        lay.addWidget(titre)

        # ── Boutons ──
        lay.addWidget(self._sect("boutons"))
        row = QHBoxLayout()
        row.setSpacing(8)
        b1 = QPushButton("Extraire les frames")
        b1.setObjectName("primary")
        b1.setFixedHeight(36)
        b2 = QPushButton("Parcourir")
        b2.setFixedHeight(32)
        b3 = QPushButton("Supprimer")
        b3.setObjectName("danger")
        b3.setFixedHeight(32)
        b4 = QPushButton("Annuler")
        b4.setObjectName("ghost")
        b4.setFixedHeight(32)
        b5 = QPushButton("Désactivé")
        b5.setFixedHeight(32)
        b5.setEnabled(False)
        for b in (b1, b2, b3, b4, b5):
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        # ── Slider ──
        lay.addWidget(self._sect("slider"))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(5, 1000)
        slider.setValue(500)
        lay.addWidget(slider)

        # ── Switches ──
        lay.addWidget(self._sect("switches"))
        row = QHBoxLayout()
        row.setSpacing(8)
        s1 = Switch()
        s1.setChecked(True)
        row.addWidget(s1)
        row.addWidget(QLabel("Filtrer les images noires"))
        row.addSpacing(16)
        s2 = Switch()
        row.addWidget(s2)
        row.addWidget(QLabel("Confirmation avant suppression"))
        row.addStretch()
        lay.addLayout(row)

        # ── Segmented + combo ──
        lay.addWidget(self._sect("segmented / combo"))
        row = QHBoxLayout()
        row.setSpacing(8)
        grp = QButtonGroup(root)
        grp.setExclusive(True)
        for i, txt in enumerate(["Toutes", "Sélectionnées", "Marquées"]):
            sb = QPushButton(txt)
            sb.setObjectName("seg")
            sb.setCheckable(True)
            sb.setChecked(i == 0)
            sb.setFixedHeight(28)
            grp.addButton(sb)
            row.addWidget(sb)
        row.addSpacing(16)
        combo = QComboBox()
        combo.addItems(["250 px", "100 px", "150 px", "200 px", "300 px"])
        combo.setFixedHeight(32)
        row.addWidget(combo)
        row.addStretch()
        lay.addLayout(row)

        # ── Badges ──
        lay.addWidget(self._sect("badges"))
        row = QHBoxLayout()
        row.setSpacing(8)
        bd1 = QLabel("481 images")
        bd1.setObjectName("badge")
        bd2 = QLabel("3 sélectionnées")
        bd2.setObjectName("badge_accent")
        bd3 = QLabel("12 marquées")
        bd3.setObjectName("badge")
        row.addWidget(bd1)
        row.addWidget(bd2)
        row.addWidget(bd3)
        row.addStretch()
        lay.addLayout(row)

        # ── Carte ──
        lay.addWidget(self._sect("carte"))
        card = QWidget()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(6)
        ct = QLabel("source")
        ct.setObjectName("sect")
        cv = QLabel("Evil Dead Burn (2026).mkv")
        cm = QLabel("1h 50m 31s · 3840×1608 · 23.98 fps · HDR")
        cm.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        cl.addWidget(ct)
        cl.addWidget(cv)
        cl.addWidget(cm)
        lay.addWidget(card)

        lay.addStretch()
        self.setCentralWidget(root)

    @staticmethod
    def _sect(text):
        lbl = QLabel(text)
        lbl.setObjectName("sect")
        return lbl


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = Sandbox()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()