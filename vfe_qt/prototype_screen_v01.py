# -*- coding: utf-8 -*-
"""
Cineblast VFE — LOT 2B : prototype écran factice PySide6
Fichier : vfe_qt/prototype_screen_v01.py
Objectif : valider l'assemblage des 5 zones avec le thème validé.
Aucune logique métier ici.
"""

import sys

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

# ─────────────────────────────────────────────────────────────
# Tokens LOT 1C
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
QLabel#mono {{ font-family: Consolas; font-size: 12px; color: {TEXT_SECOND}; }}
QLabel#filename {{ font-family: Consolas; font-size: 12px; color: {ACCENT_TEXT}; }}

QWidget#zoneA {{ background-color: {SURFACE_PANEL}; }}
QWidget#zoneB {{ background-color: {SURFACE_PANEL}; }}
QWidget#zoneC {{ background-color: {BG_APP}; }}
QWidget#zoneD {{ background-color: {SURFACE_PANEL}; }}
QWidget#zoneE {{ background-color: {SURFACE_PANEL}; }}
QWidget#panelInner {{ background: transparent; }}
QFrame#sep {{ background-color: {BORDER_SUBTLE}; border: none; }}

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

QLineEdit {{
    background-color: {INPUT_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 0 8px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QLabel#badge {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    color: {TEXT_SECOND};
    font-size: 11px;
    padding: 2px 8px;
}}
QLabel#badge_sel {{
    background-color: {ACCENT_SUBTLE};
    border: 1px solid {ACCENT_BORDER};
    border-radius: 4px;
    color: {ACCENT_TEXT};
    font-size: 11px;
    padding: 2px 8px;
}}
QLabel#badge_mark {{
    background: transparent;
    border: 1px solid {SUCCESS};
    border-radius: 4px;
    color: {SUCCESS};
    font-size: 11px;
    padding: 2px 8px;
}}
QLabel#badge_success {{
    background: transparent;
    border: 1px solid {SUCCESS};
    border-radius: 4px;
    color: {SUCCESS};
    font-size: 11px;
    padding: 2px 8px;
}}
QLabel#badge_warn {{
    background: transparent;
    border: 1px solid {WARNING};
    border-radius: 4px;
    color: {WARNING};
    font-size: 11px;
    padding: 2px 8px;
}}

QWidget#card {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
}}
QWidget#previewBox {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_BORDER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


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
        p.end()


class Thumb(QWidget):
    """Vignette factice : radius 6, bordure 1, sélection 2 ambre,
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


def sect(text):
    lbl = QLabel(text)
    lbl.setObjectName("sect")
    return lbl


def sep():
    f = QFrame()
    f.setObjectName("sep")
    f.setFixedHeight(1)
    return f() if False else f


class PrototypeScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cineblast VFE — prototype écran (LOT 2B)")
        self.resize(1600, 900)

        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Zone E : barre de statut (en haut, selon mockup LOT 1D) ──
        zone_e = QWidget()
        zone_e.setObjectName("zoneE")
        zone_e.setFixedHeight(28)
        ze = QHBoxLayout(zone_e)
        ze.setContentsMargins(12, 0, 12, 0)
        status = QLabel("481 images chargées · 19 noires filtrées · 0 échec")
        status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        ze.addWidget(status)
        ze.addStretch()
        vbox.addWidget(zone_e)
        vbox.addWidget(sep())

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # ── Zone A : panneau gauche ──
        zone_a = QWidget()
        zone_a.setObjectName("zoneA")
        zone_a.setFixedWidth(320)
        za = QVBoxLayout(zone_a)
        za.setContentsMargins(0, 0, 0, 0)
        za.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("panelInner")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # fichier source
        lay.addWidget(sect("fichier source"))
        row = QHBoxLayout()
        src = QPushButton("Evil Dead Burn (2026).mkv")
        src.setFixedHeight(32)
        row.addWidget(src, 1)
        parc = QPushButton("Parcourir")
        parc.setObjectName("ghost")
        parc.setFixedHeight(32)
        row.addWidget(parc)
        lay.addLayout(row)

        row = QHBoxLayout()
        b_ff = QLabel("FFMPEG")
        b_ff.setObjectName("badge_success")
        row.addWidget(b_ff)
        t_ff = QLabel("Couleurs fidèles")
        t_ff.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        row.addWidget(t_ff)
        row.addStretch()
        lay.addLayout(row)

        row = QHBoxLayout()
        b_hdr = QLabel("HDR10 PQ")
        b_hdr.setObjectName("badge_warn")
        row.addWidget(b_hdr)
        t_hdr = QLabel("Pipeline HDR→SDR actif")
        t_hdr.setStyleSheet(f"color: {WARNING}; font-size: 12px;")
        row.addWidget(t_hdr)
        row.addStretch()
        lay.addLayout(row)

        info = QLabel(
            "Durée : 1h50m31s\n"
            "Résolution : 3840×1608\n"
            "FPS : 23.98\n"
            "Taille : 1.2 Go"
        )
        info.setObjectName("mono")
        lay.addWidget(info)

        lay.addWidget(sep())

        # dossier d'extraction
        lay.addWidget(sect("dossier d'extraction"))
        row = QHBoxLayout()
        out = QPushButton("Extraction Photos Temp")
        out.setFixedHeight(32)
        row.addWidget(out, 1)
        parc2 = QPushButton("Parcourir")
        parc2.setObjectName("ghost")
        parc2.setFixedHeight(32)
        row.addWidget(parc2)
        lay.addLayout(row)

        # dossier de travail
        lay.addWidget(sect("dossier de travail"))
        row = QHBoxLayout()
        work = QPushButton("2026-09-01 Evil Dead Burn/photos")
        work.setFixedHeight(32)
        row.addWidget(work, 1)
        parc3 = QPushButton("Parcourir")
        parc3.setObjectName("ghost")
        parc3.setFixedHeight(32)
        row.addWidget(parc3)
        lay.addLayout(row)

        lay.addWidget(sep())

        # mode de capture
        lay.addWidget(sect("mode de capture"))
        row = QHBoxLayout()
        grp = QButtonGroup(inner)
        grp.setExclusive(True)
        for i, txt in enumerate(["Nombre d'images", "Intervalle (s)"]):
            sb = QPushButton(txt)
            sb.setObjectName("seg")
            sb.setCheckable(True)
            sb.setChecked(i == 0)
            sb.setFixedHeight(28)
            grp.addButton(sb)
            row.addWidget(sb)
        lay.addLayout(row)

        row = QHBoxLayout()
        lbl_count = QLabel("Nombre d'images")
        lbl_count.setStyleSheet(f"color: {TEXT_SECOND}; font-size: 12px;")
        val_count = QLabel("500")
        val_count.setStyleSheet(f"color: {ACCENT_TEXT}; font-weight: 600;")
        row.addWidget(lbl_count)
        row.addStretch()
        row.addWidget(val_count)
        lay.addLayout(row)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(5, 1000)
        slider.setValue(500)
        lay.addWidget(slider)

        row = QHBoxLayout()
        sw = Switch()
        sw.setChecked(True)
        row.addWidget(sw)
        row.addWidget(QLabel("Supprimer les frames noires"))
        row.addStretch()
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addSpacing(44)
        row.addWidget(QLabel("Seuil :"))
        seuil = QLineEdit("5")
        seuil.setFixedWidth(44)
        seuil.setFixedHeight(28)
        row.addWidget(seuil)
        row.addWidget(QLabel("/255"))
        row.addStretch()
        lay.addLayout(row)

        card = QWidget()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        plan = QLabel(
            "Plan : 500 images entre 0h00m00s et 1h50m30s\n"
            "→ une toutes les 0m13s environ"
        )
        plan.setStyleSheet(f"color: {TEXT_SECOND}; font-size: 12px;")
        cl.addWidget(plan)
        lay.addWidget(card)

        lay.addWidget(sep())

        # actions
        lay.addWidget(sect("actions"))
        run = QPushButton("Extraire les frames")
        run.setObjectName("primary")
        run.setFixedHeight(36)
        lay.addWidget(run)

        row = QHBoxLayout()
        cancel = QPushButton("Annuler")
        cancel.setObjectName("ghost")
        cancel.setFixedHeight(30)
        delete = QPushButton("Supprimer")
        delete.setObjectName("danger")
        delete.setFixedHeight(30)
        row.addWidget(cancel)
        row.addWidget(delete)
        lay.addLayout(row)

        clear = QPushButton("Vider le dossier d'extraction")
        clear.setObjectName("danger")
        clear.setFixedHeight(30)
        lay.addWidget(clear)

        retry = QPushButton("Ré-extraire les échecs")
        retry.setFixedHeight(30)
        lay.addWidget(retry)

        row = QHBoxLayout()
        sw2 = Switch()
        sw2.setChecked(True)
        row.addWidget(sw2)
        row.addWidget(QLabel("Demander confirmation avant suppression"))
        row.addStretch()
        lay.addLayout(row)

        lay.addSpacing(12)
        save = QPushButton("Sauvegarder la configuration")
        save.setObjectName("ghost")
        save.setFixedHeight(32)
        lay.addWidget(save)

        scroll.setWidget(inner)
        za.addWidget(scroll)
        hbox.addWidget(zone_a)

        # ── Centre : Zone B + Zone C ──
        mid = QWidget()
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
        bd_total = QLabel("481 image(s)")
        bd_total.setObjectName("badge")
        zb.addWidget(bd_total)
        bd_sel = QLabel("3 sélectionnée(s)")
        bd_sel.setObjectName("badge_sel")
        zb.addWidget(bd_sel)
        bd_mark = QLabel("12 marquée(s)")
        bd_mark.setObjectName("badge_mark")
        zb.addWidget(bd_mark)
        zb.addStretch()

        unmark = QPushButton("Tout démarquer")
        unmark.setObjectName("ghost")
        unmark.setFixedHeight(28)
        zb.addWidget(unmark)
        mark = QPushButton("Marquer")
        mark.setObjectName("ghost")
        mark.setFixedHeight(28)
        zb.addWidget(mark)
        zb.addWidget(QLabel("Marquer :"))
        key = QLineEdit("S")
        key.setFixedWidth(32)
        key.setFixedHeight(28)
        key.setAlignment(Qt.AlignCenter)
        zb.addWidget(key)
        zb.addWidget(QLabel("Vignettes :"))
        c_tsize = QComboBox()
        c_tsize.addItems(["250 px", "100 px", "150 px", "200 px", "300 px"])
        c_tsize.setFixedHeight(28)
        zb.addWidget(c_tsize)
        zb.addWidget(QLabel("Colonnes :"))
        c_cols = QComboBox()
        c_cols.addItems(["5", "3", "4", "6"])
        c_cols.setFixedHeight(28)
        zb.addWidget(c_cols)
        refresh = QPushButton("Rafraîchir")
        refresh.setObjectName("ghost")
        refresh.setFixedHeight(28)
        zb.addWidget(refresh)

        midbox.addWidget(zone_b)
        midbox.addWidget(sep())

        zone_c = QWidget()
        zone_c.setObjectName("zoneC")
        zc = QVBoxLayout(zone_c)
        zc.setContentsMargins(16, 16, 16, 16)
        grid = QGridLayout()
        grid.setSpacing(12)

        tcs = [
            "01h02m34s", "01h02m45s", "01h02m56s", "01h03m07s", "01h03m18s",
            "01h03m29s", "01h03m40s", "01h03m51s", "01h04m02s", "01h04m13s",
            "01h04m24s", "01h04m35s", "01h04m46s", "01h04m57s", "01h05m08s",
        ]
        for i, tc in enumerate(tcs):
            th = Thumb(tc, selected=(i == 0), marked=(i == 1))
            grid.addWidget(th, i // 5, i % 5)
        zc.addLayout(grid)
        zc.addStretch()
        midbox.addWidget(zone_c, 1)

        hbox.addWidget(mid, 1)

        # ── Zone D : aperçu ──
        zone_d = QWidget()
        zone_d.setObjectName("zoneD")
        zone_d.setFixedWidth(340)
        zd = QVBoxLayout(zone_d)
        zd.setContentsMargins(16, 16, 16, 16)
        zd.setSpacing(12)

        zd.addWidget(sect("aperçu"))

        box = QWidget()
        box.setObjectName("previewBox")
        box.setFixedHeight(200)
        bl = QVBoxLayout(box)
        ph = QLabel("Image placeholder\n(aperçu)")
        ph.setAlignment(Qt.AlignCenter)
        ph.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        bl.addWidget(ph)
        zd.addWidget(box)

        fname = QLabel("EvilDB_0042_01h03m29s.jpg")
        fname.setObjectName("filename")
        zd.addWidget(fname)

        m1 = QLabel("01h03m29s")
        m1.setObjectName("mono")
        zd.addWidget(m1)
        m2 = QLabel("3840×1608 px")
        m2.setStyleSheet(f"color: {TEXT_SECOND}; font-size: 12px;")
        zd.addWidget(m2)
        m3 = QLabel("#42 / 481")
        m3.setStyleSheet(f"color: {TEXT_SECOND}; font-size: 12px;")
        zd.addWidget(m3)

        zd.addStretch()

        open_btn = QPushButton("Ouvrir dans le dossier")
        open_btn.setFixedHeight(32)
        zd.addWidget(open_btn)

        hbox.addWidget(zone_d)

        vbox.addLayout(hbox, 1)
        self.setCentralWidget(central)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = PrototypeScreen()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()