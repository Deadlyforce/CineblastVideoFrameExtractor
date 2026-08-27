"""Construction des commandes ffmpeg / ffprobe et détection HDR —
extraits de Video Frame Extractor.py (refactor A1). Aucune dépendance tkinter."""
import json
import subprocess

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
    except Exception:
        pass
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


# ── Constructeurs de commandes ───────────────────────────────────────────────
def build_ffmpeg_cmd(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """Commande SDR standard — JPEG full range correct (voir commentaires d'origine v2.9)."""
    if sar_applied:
        vf = f"scale={disp_w}:{disp_h}:out_range=full:flags=lanczos"
    else:
        vf = "scale=iw:ih:out_range=full"
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{t_sec:.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-pix_fmt", "yuvj420p",
        "-q:v", "2",
        out_path
    ]
    return cmd


def build_ffmpeg_cmd_fallback(vpath, t_sec, out_path, disp_w, disp_h, sar_applied):
    """Commande alternative si la première échoue."""
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
    filters.append("format=yuvj420p")
    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{max(0, t_sec - 1):.6f}",
        "-i", vpath,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        out_path
    ]
    return cmd


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
    filters.append("zscale=t=linear:npl=100:p=bt709:m=bt709:r=tv")
    filters.append(f"tonemap=tonemap={tonemap_algo}:desat=0:peak=0")
    filters.append("zscale=t=bt709:p=bt709:m=bt709:r=pc")
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
    """Fallback HDR si zscale est absent."""
    filters = []
    if sar_applied:
        filters.append(f"scale={disp_w}:{disp_h}:flags=lanczos")
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