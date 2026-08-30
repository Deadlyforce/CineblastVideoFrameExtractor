"""Configuration persistée de VFE — extraite de Video Frame Extractor.py (refactor A1).
Aucune dépendance tkinter ici."""
import os
import json
import logging
from dataclasses import dataclass, field, asdict

log = logging.getLogger("vfe")

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_APP_DIR, "VFE_Config.json")


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
    black_threshold: int  = 5
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