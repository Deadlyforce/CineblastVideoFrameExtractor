"""Grille de vignettes virtualisée — extraite de Video Frame Extractor.py (Lot 7b).
Dépendances : PIL, collections, vfe_utils.hms, vfe_widgets (C, F_SMALL)."""

from collections import OrderedDict
from PIL import Image, ImageTk

from vfe_utils import hms
from vfe_widgets import C, F_SMALL


class VirtualThumbGrid:
    """Renderer virtualisé : dessine uniquement la fenêtre visible,
    gère un cache PhotoImage borné et un pool de cellules canvas."""
    _MAX_CACHE = 200

    def __init__(self, canvas, app):
        self.canvas = canvas
        self.app = app
        self._photo_cache = OrderedDict()
        self._pool = []
        self._scheduled = False
        self._pad_x = 9
        self._pad_y = 8
        self._text_h = 18

    def reload(self):
        self.refresh()

    def refresh(self):
        if self._scheduled:
            return
        self._scheduled = True
        try:
            self.canvas.after_idle(self._redraw)
        except Exception:
            self._scheduled = False

    def _thumb_height(self, thumb_w):
        info = getattr(self.app, "video_info", {}) or {}
        w = info.get("disp_w") or info.get("width") or 0
        h = info.get("disp_h") or info.get("height") or 0
        try:
            w = int(w)
            h = int(h)
        except Exception:
            w = h = 0
        if w > 0 and h > 0:
            return max(24, int(thumb_w * h / w))
        return max(24, int(thumb_w * 9 / 16))

    def _metrics(self):
        try:
            cols = max(1, int(self.app.v_cols.get()))
        except Exception:
            cols = 4
        try:
            thumb_w = max(40, int(self.app.v_tsize.get()))
        except Exception:
            thumb_w = 150
        thumb_h = self._thumb_height(thumb_w)
        cell_w = thumb_w + 2 * self._pad_x
        cell_h = thumb_h + self._text_h + 2 * self._pad_y
        return cols, thumb_w, thumb_h, cell_w, cell_h

    def _row_count(self, count, cols):
        if count <= 0:
            return 0
        return (count + cols - 1) // cols

    def _update_scrollregion(self):
        try:
            count = len(self.app.thumbs)
        except Exception:
            count = 0
        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()
        rows = self._row_count(count, cols)
        try:
            canvas_w = max(1, self.canvas.winfo_width())
        except Exception:
            canvas_w = 1
        try:
            canvas_h = max(1, self.canvas.winfo_height())
        except Exception:
            canvas_h = 1
        content_h = rows * cell_h + 1
        width = max(canvas_w, cols * cell_w + 1)
        height = max(canvas_h, content_h)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if content_h <= canvas_h:
            try:
                self.canvas.yview_moveto(0)
            except Exception:
                pass

    def _redraw(self):
        self._scheduled = False
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return
        self._update_scrollregion()
        try:
            count = len(self.app.thumbs)
        except Exception:
            count = 0
        if count == 0:
            self._photo_cache.clear()
            self._hide_pool_from(0)
            return
        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()
        try:
            top = self.canvas.canvasy(0)
            bottom = self.canvas.canvasy(max(1, self.canvas.winfo_height()))
        except Exception:
            top, bottom = 0, 1
        buffer = cell_h * 2
        top = max(0, top - buffer)
        bottom += buffer
        first_row = max(0, int(top // cell_h))
        last_row = min(self._row_count(count, cols) - 1, int(bottom // cell_h))
        first_idx = first_row * cols
        last_idx = min(count - 1, (last_row + 1) * cols - 1)
        visible = []
        try:
            sel = self.app.sel
        except Exception:
            sel = set()
        hover = getattr(self, "_hover_path", None)
        cell_i = 0
        for idx in range(first_idx, last_idx + 1):
            try:
                entry = self.app.thumbs[idx]
            except IndexError:
                continue
            path = entry.get("path", "")
            if not path:
                continue
            visible.append(path)
            rect, img, txt = self._get_cell(cell_i)
            cell_i += 1
            row, col = divmod(idx, cols)
            x0 = col * cell_w
            y0 = row * cell_h
            if path in sel:
                fill, outline = C["thumb_sel"], C["sel_brd"]
            elif path == hover:
                fill, outline = C["thumb_hov"], ""
            else:
                fill, outline = C["thumb_bg"], ""
            self.canvas.coords(rect, x0 + 3, y0 + 3, x0 + cell_w - 3, y0 + cell_h - 3)
            self.canvas.itemconfigure(rect, fill=fill, outline=outline, width=1,
                                      tags=("vt", f"vt::{path}", "vtbg", f"vtbg::{path}"))
            imgtk = self._photo_for(entry, thumb_w, thumb_h)
            self.canvas.coords(img, x0 + cell_w // 2, y0 + self._pad_y + thumb_h // 2)
            self.canvas.itemconfigure(img,
                                      image=imgtk if imgtk is not None else "",
                                      tags=("vt", f"vt::{path}"))
            self.canvas.coords(txt, x0 + cell_w // 2, y0 + self._pad_y + thumb_h + 4)
            self.canvas.itemconfigure(txt, text=hms(entry.get("tc", 0)),
                                      tags=("vt", f"vt::{path}"))
        self._hide_pool_from(cell_i)
        self._prune_cache(set(visible))

    def _get_cell(self, i):
        if i < len(self._pool):
            return self._pool[i]
        rect = self.canvas.create_rectangle(-10, -10, -9, -9, fill=C["thumb_bg"],
                                            outline="", width=1, tags="vt")
        img = self.canvas.create_image(-10, -10, image="", anchor="center", tags="vt")
        txt = self.canvas.create_text(-10, -10, text="", font=F_SMALL,
                                      fill=C["t3"], anchor="n", tags="vt")
        cell = (rect, img, txt)
        self._pool.append(cell)
        return cell

    def _hide_pool_from(self, i):
        for rect, img, txt in self._pool[i:]:
            self.canvas.coords(rect, -10, -10, -9, -9)
            self.canvas.itemconfigure(rect, tags="vt")
            self.canvas.coords(img, -10, -10)
            self.canvas.itemconfigure(img, image="", tags="vt")
            self.canvas.coords(txt, -10, -10)
            self.canvas.itemconfigure(txt, text="", tags="vt")

    def _get_check_icon(self):
        if getattr(self, "_check_icon", None) is None:
            try:
                self._check_icon = self.app._make_check_icon(size=22)
            except Exception:
                self._check_icon = None
        return self._check_icon

    def _photo_for(self, entry, thumb_w, thumb_h):
        path = entry.get("path", "")
        marked = path in getattr(self.app, "marked", set())
        key = (thumb_w, thumb_h, marked)
        cached = self._photo_cache.get(path)
        if cached is not None and cached[0] == key:
            self._photo_cache.move_to_end(path)
            return cached[1]
        img = entry.get("img")
        if img is None:
            try:
                im = Image.open(path)
                im.draft("RGB", (thumb_w, thumb_h))
                img = im.copy()
            except Exception:
                return None
        try:
            th = img.copy()
            th.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
            if marked:
                icon = self._get_check_icon()
                if icon is not None and th.width >= icon.width + 4 and th.height >= icon.height + 4:
                    th_rgba = th.convert("RGBA")
                    x = th_rgba.width - icon.width - 2
                    y = 2
                    th_rgba.paste(icon, (x, y), icon)
                    th = th_rgba.convert("RGB")
            imgtk = ImageTk.PhotoImage(th)
        except Exception:
            return None
        self._photo_cache[path] = (key, imgtk)
        self._photo_cache.move_to_end(path)
        return imgtk

    def _prune_cache(self, visible_paths):
        while len(self._photo_cache) > self._MAX_CACHE:
            self._photo_cache.popitem(last=False)

    def update_selection(self):
        if getattr(self, "_sel_scheduled", False):
            return
        self._sel_scheduled = True
        try:
            self.canvas.after_idle(self._update_selection_now)
        except Exception:
            self._sel_scheduled = False

    def _update_selection_now(self):
        self._sel_scheduled = False
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return
        try:
            sel = self.app.sel
        except Exception:
            sel = set()
        hover = getattr(self, "_hover_path", None)
        for iid in self.canvas.find_withtag("vtbg"):
            path = None
            for tag in self.canvas.gettags(iid):
                if tag.startswith("vt::"):
                    path = tag[4:]
                    break
            if not path:
                continue
            if path in sel:
                self.canvas.itemconfigure(iid, fill=C["thumb_sel"],
                                          outline=C["sel_brd"], width=1)
            elif path == hover:
                self.canvas.itemconfigure(iid, fill=C["thumb_hov"],
                                          outline="", width=1)
            else:
                self.canvas.itemconfigure(iid, fill=C["thumb_bg"],
                                          outline="", width=1)

    def set_hover(self, path):
        old = getattr(self, "_hover_path", None)
        if old == path:
            return
        self._hover_path = path
        try:
            sel = self.app.sel
        except Exception:
            sel = set()
        if old:
            if old in sel:
                self.canvas.itemconfigure(f"vtbg::{old}", fill=C["thumb_sel"],
                                          outline=C["sel_brd"], width=1)
            else:
                self.canvas.itemconfigure(f"vtbg::{old}", fill=C["thumb_bg"],
                                          outline="", width=1)
        if path and path not in sel:
            self.canvas.itemconfigure(f"vtbg::{path}", fill=C["thumb_hov"],
                                      outline="", width=1)

    def scroll_to_path(self, path):
        try:
            idx = self.app._position_of(path)
        except Exception:
            idx = -1
        if idx < 0:
            return
        self._update_scrollregion()
        cols, thumb_w, thumb_h, cell_w, cell_h = self._metrics()
        row = idx // cols
        y0 = row * cell_h
        y1 = y0 + cell_h
        try:
            top = self.canvas.canvasy(0)
            canvas_h = max(1, self.canvas.winfo_height())
        except Exception:
            top, canvas_h = 0, 1
        bottom = top + canvas_h
        if y0 >= top and y1 <= bottom:
            self.refresh()
            return
        count = len(self.app.thumbs)
        rows = self._row_count(count, cols)
        content_h = rows * cell_h + 1
        total_h = max(content_h, canvas_h)
        target = max(0, y0 - canvas_h // 3)
        target = min(target, max(0, total_h - canvas_h))
        try:
            self.canvas.yview_moveto(target / max(1, total_h))
            self.canvas.update_idletasks()
        except Exception:
            pass
        self.refresh()