"""Construction des commandes ffmpeg / ffprobe et détection HDR —
extraits de Video Frame Extractor.py (refactor A1). Aucune dépendance tkinter."""
import json
import logging
import os
import subprocess
import tempfile
import time as _time

log = logging.getLogger("vfe")

# ── Détection HDR ────────────────────────────────────────────────────────────
HDR_TRANSFERS   = {"smpte2084", "arib-std-b67", "smpte428", "bt2020-10", "bt2020-12"}
HDR_PRIMARIES   = {"bt2020"}
HDR_COLORSPACES = {"bt2020nc", "bt2020c", "smpte2085", "ictcp"}


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
    except Exception as ex:
        log.debug("get_display_size : %s", ex)
    return raw_w, raw_h


def detect_hdr(vpath):
    """Analyse le flux vidéo avec ffprobe et retourne un dict is_hdr/transfer/…"""
    info = {"is_hdr": False, "transfer": "", "primaries": "", "colorspace": "", "color_range": ""}
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
            data = json.loads(r.stdout)
            streams = data.get("streams", [{}])
            s = streams[0] if streams else {}
            transfer    = s.get("color_transfer",  "").lower()
            primaries   = s.get("color_primaries", "").lower()
            colorspace  = s.get("color_space",     "").lower()
            color_range = s.get("color_range",     "").lower()
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
    except Exception as ex:
        log.debug("detect_hdr : %s", ex)
    return info


def zscale_available():
    """Vérifie que le build ffmpeg inclut libzimg (nécessaire pour zscale)."""
    try:
        r = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=10)
        return "zscale" in r.stdout
    except Exception as ex:
        log.debug("zscale_available : %s", ex)
        return False


# ── Constructeurs de commandes ───────────────────────────────────────────────
def _assemble_cmd(vpath, ss, vf, out_path, pix_fmt=None):
    """D1 : squelette commun des commandes ffmpeg d'extraction d'une frame.
    ss     : timestamp de seek (secondes, float)
    vf     : chaîne du filtre -vf
    pix_fmt: ajouté seulement si fourni (seul le builder SDR standard l'utilise)."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{ss:.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
    ]
    if pix_fmt:
        cmd += ["-pix_fmt", pix_fmt]
    cmd += ["-q:v", "2", out_path]
    return cmd


def build_ffmpeg_cmd(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """Commande SDR standard — JPEG full range correct (voir commentaires d'origine v2.9)."""
    if sar_applied:
        vf = f"scale={disp_w}:{disp_h}:out_range=full:flags=lanczos"
    else:
        vf = "scale=iw:ih:out_range=full"
    return _assemble_cmd(vpath, t_sec, vf, out_path, pix_fmt="yuvj420p")


def build_ffmpeg_cmd_fallback(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """Commande alternative si la première échoue."""
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
    filters.append("format=yuvj420p")
    vf = ",".join(filters)
    return _assemble_cmd(vpath, max(0, t_sec - 1), vf, out_path)


def build_ffmpeg_cmd_hdr(vpath, t_sec, out_path, disp_w, disp_h, sar_applied,
                          hdr_info, tonemap_algo="hable"):
    """Pipeline HDR→SDR via zscale + tonemap + zscale (v3.0)."""
    transfer_in = hdr_info.get("transfer", "smpte2084")
    if "hlg" in transfer_in or "arib" in transfer_in:
        zscale_tin = "arib-std-b67"
    else:
        zscale_tin = "smpte2084"  # PQ (HDR10)
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
    filters.append(f"zscale=t=linear:npl=100:p=bt709:m=bt709:r=tv:tin={zscale_tin}")
    filters.append(f"tonemap=tonemap={tonemap_algo}:desat=0:peak=0")
    filters.append("zscale=t=bt709:p=bt709:m=bt709:r=pc")
    filters.append("format=rgb24")
    vf = ",".join(filters)
    return _assemble_cmd(vpath, t_sec, vf, out_path)


def build_ffmpeg_cmd_hdr_fallback(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """Fallback HDR si zscale est absent."""
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
    filters.append("colorspace=bt709:iall=bt2020:fast=1")
    filters.append("scale=iw:ih:out_range=full")
    filters.append("format=yuvj420p")
    vf = ",".join(filters)
    return _assemble_cmd(vpath, t_sec, vf, out_path)


# ── Exécution ffmpeg avec gestion cancel / timeout (Lot 7c) ─────────────────
import tempfile
import time as _time


def run_ffmpeg(cmd, timeout, is_cancelled):
    """Lance ffmpeg via Popen et surveille is_cancelled / le timeout.
    is_cancelled : callable () -> bool.
    Retourne (returncode, raison). rc=0 → succès, -1 → échec/annulation/timeout.
    La raison est la queue filtrée du stderr de ffmpeg."""
    err_fd, err_path = tempfile.mkstemp(suffix=".txt", prefix="vfe_err_")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err_fd)
    except Exception as ex:
        os.close(err_fd)
        try: os.remove(err_path)
        except Exception: pass
        return -1, f"lancement impossible : {ex}"
    os.close(err_fd)
    deadline = _time.time() + timeout
    rc, reason = -1, ""
    try:
        while True:
            if is_cancelled():
                proc.terminate()
                try: proc.wait(timeout=3)
                except Exception: proc.kill()
                rc, reason = -1, "annulé"
                break
            if _time.time() > deadline:
                proc.terminate()
                try: proc.wait(timeout=3)
                except Exception: proc.kill()
                rc, reason = -1, f"timeout après {timeout}s"
                break
            try:
                rc = proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
    except Exception as ex:
        try: proc.kill()
        except Exception: pass
        rc, reason = -1, f"erreur : {ex}"
    # Filtrage des lignes utiles du stderr
    tail = ""
    try:
        with open(err_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        skip_prefixes = (
            "ffmpeg version", "built with", "configuration:",
            "libav", "libsw", "Press [q]", "Stream mapping",
            "  Stream #", "Output #", "frame=", "speed=",
            "Last message repeated", "Metadata:",
        )
        kept = [
            ln for ln in lines
            if ln.strip() and not any(ln.lstrip().startswith(p) for p in skip_prefixes)
        ]
        tail = "\n".join(kept[-8:])
    except Exception:
        pass
    try: os.remove(err_path)
    except Exception: pass
    return rc, (reason or tail)


def tmp_ok(tmp_path):
    """Le fichier temporaire existe et n'est pas vide."""
    try:
        return os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0
    except Exception:
        return False