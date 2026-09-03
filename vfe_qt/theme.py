# -*- coding: utf-8 -*-
"""Cineblast VFE — thème Qt (LOT 3).
Tokens LOT 1C + QSS. Aucune logique."""

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
QFrame#sepA {{
    background: transparent;
    border: none;
    border-top: 1px solid {BORDER_SUBTLE};
}}

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
QPushButton#ghost:hover {{
    background-color: {SURFACE_ELEV};
    border-color: {BORDER_STRONG};
}}
QPushButton#ghost:pressed {{ background-color: {SURFACE_CARD}; }}
QPushButton:focus {{ border-color: {ACCENT_BORDER}; }}
QPushButton#primary:focus {{ border: none; }}
QPushButton#seg {{ color: {TEXT_MUTED}; }}
QPushButton#seg:hover {{ border-color: {BORDER_STRONG}; }}
QComboBox:focus {{ border-color: {ACCENT_BORDER}; }}

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
QLineEdit:disabled {{
    color: {TEXT_DISABLED};
    background-color: {SURFACE_CARD};
    border-color: {BORDER_SUBTLE};
}}
QProgressBar {{
    background: {INPUT_BG};
    border: none;
    border-radius: 2px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}

QLabel#badge {{
    background-color: {SURFACE_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 3px;
    color: {TEXT_SECOND};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_sel {{
    background-color: {ACCENT_SUBTLE};
    border: 1px solid {ACCENT_BORDER};
    border-radius: 3px;
    color: {ACCENT_TEXT};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_mark {{
    background: transparent;
    border: 1px solid {SUCCESS};
    border-radius: 3px;
    color: {SUCCESS};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_success {{
    background: transparent;
    border: 1px solid {SUCCESS};
    border-radius: 3px;
    color: {SUCCESS};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_warn {{
    background: transparent;
    border: 1px solid {WARNING};
    border-radius: 3px;
    color: {WARNING};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_danger {{
    background: transparent;
    border: 1px solid {DANGER};
    border-radius: 3px;
    color: {DANGER};
    font-size: 11px;
    padding: 1px 6px;
}}
QLabel#badge_off {{
    background: transparent;
    border: 1px solid {BORDER_STRONG};
    border-radius: 3px;
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 1px 6px;
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