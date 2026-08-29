"""Widgets custom + palette + fonts — extraits de Video Frame Extractor.py (Lot 7a).
Dépendances : tkinter, vfe_utils.hms (pour DarkSlider)."""

import os
import tkinter as tk
from tkinter import ttk
from tkinter.font import Font

from vfe_utils import hms

# ─────────────────────────────────────────────────────────────────────────────
#  Palette
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#1e1e1e",
    "sidebar":   "#252526",
    "panel":     "#2d2d2d",
    "panel2":    "#333333",
    "input":     "#3a3a3a",
    "border":    "#3f3f3f",
    "border2":   "#505050",
    "accent":    "#4fc3f7",
    "accent_dk": "#0288d1",
    "accent_bg": "#1a3a4a",
    "danger":    "#f48771",
    "danger_dk": "#a83225",
    "ok":        "#89d185",
    "info_bg":   "#2a2a2a",
    "t1":        "#d4d4d4",
    "t2":        "#9d9d9d",
    "t3":        "#6e6e6e",
    "sel_bg":    "#264f78",
    "sel_brd":   "#4fc3f7",
    "thumb_bg":  "#1e1e1e",
    "thumb_sel": "#1a3a4a",
    "thumb_hov": "#2a2a2a",
}

F_HEAD  = ("Segoe UI Light",    20)
F_TITLE = ("Segoe UI Semibold", 11)
F_UI    = ("Segoe UI",          10)
F_BOLD  = ("Segoe UI Semibold", 10)
F_SMALL = ("Segoe UI",           9)
F_MONO  = ("Consolas",           9)
F_SECT  = ("Segoe UI",           8)

# ─────────────────────────────────────────────────────────────────────────────
#  Cache de polices
# ─────────────────────────────────────────────────────────────────────────────
_FONT_CACHE = {}

def _get_font(font_tuple):
    key = (font_tuple[0], font_tuple[1], font_tuple[2] if len(font_tuple) > 2 else "normal")
    f = _FONT_CACHE.get(key)
    if f is None:
        f = Font(family=key[0], size=key[1], weight=key[2])
        _FONT_CACHE[key] = f
    return f

# ─────────────────────────────────────────────────────────────────────────────
#  Widgets
# ─────────────────────────────────────────────────────────────────────────────
class DarkButton(tk.Canvas):
    STYLES = {
        "accent":  ("#1a3a4a", "#0d2535", "#4fc3f7", C["accent"],  C["t3"]),
        "danger":  ("#3a1f1f", "#2a1010", "#f48771", "#f48771",    C["t3"]),
        "default": (C["panel2"], C["input"], C["border2"], C["t1"], C["t3"]),
        "ghost":   (C["sidebar"], C["panel"], C["panel"], C["t2"],  C["t3"]),
    }
    def __init__(self, parent, text="", command=None, style="default",
                 width=130, height=32, font=None, anchor="w", padx=10, fg=None, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, **kw)
        self.full_text = text
        self.text_display = text
        self.cmd = command
        self.style = style
        self.font = font or F_UI
        self.anchor = anchor
        self.padx = padx
        self.custom_fg = fg
        self._st = "normal"
        if width == 0:
            self.configure(width=130)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", self._e_enter)
        self.bind("<Leave>", self._e_leave)
        self.bind("<ButtonPress-1>", self._e_press)
        self.bind("<ButtonRelease-1>", self._e_release)
        self.after_idle(self._update_display)

    def _on_resize(self, e):
        self._update_display()

    def _update_display(self):
        self._update_truncated_text()
        self._draw()

    def _update_truncated_text(self):
        w = self.winfo_width()
        if w <= 0:
            return
        available = w - 2 * self.padx - 10
        if available <= 10:
            self.text_display = "…"
            return
        font = _get_font(self.font)
        text_width = font.measure(self.full_text)
        if text_width <= available:
            self.text_display = self.full_text
        else:
            for i in range(len(self.full_text), 0, -1):
                candidate = self.full_text[:i] + "…"
                if font.measure(candidate) <= available:
                    self.text_display = candidate
                    break
            else:
                self.text_display = "…"

    def set_text(self, text):
        self.full_text = text
        self._update_display()

    def _draw(self):
        self.delete("all")
        bg, style_fg = self._cols()
        fg = self.custom_fg if self.custom_fg is not None else style_fg
        r = 7
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 14 or h < 8:
            return
        pts = [r, 1, w-r, 1, w-1, 1, w-1, r, w-1, h-r, w-1, h-1,
               w-r, h-1, r, h-1, 1, h-1, 1, h-r, 1, r, 1, 1]
        self.create_polygon(pts, smooth=True, fill=bg, outline="")
        if self.style == "default":
            border_color = C["accent"] if self._st in ("hover", "pressed") else C["border"]
            self.create_polygon(pts, smooth=True, fill="", outline=border_color, width=1)
        if self.anchor == "w":
            x = self.padx + 5
        elif self.anchor == "e":
            x = w - self.padx - 5
        else:
            x = w // 2
        y = h // 2
        self.create_text(x, y, text=self.text_display, fill=fg, font=self.font, anchor=self.anchor)

    def _cols(self):
        n, h, p, ft, fd = self.STYLES.get(self.style, self.STYLES["default"])
        if self._st == "disabled":
            return C["panel"], fd
        if self._st == "hover":
            return h, ft
        if self._st == "pressed":
            return p, ft
        return n, ft

    def _e_enter(self, e):
        if self._st != "disabled": self._st = "hover"; self._draw(); self.config(cursor="hand2")

    def _e_leave(self, e):
        if self._st != "disabled": self._st = "normal"; self._draw()

    def _e_press(self, e):
        if self._st != "disabled": self._st = "pressed"; self._draw()

    def _e_release(self, e):
        if self._st != "disabled":
            self._st = "hover"; self._draw()
            if self.cmd: self.cmd()

    def set_state(self, st):
        self._st = st; self._draw()
        self.config(cursor="arrow" if st == "disabled" else "hand2")


class PillSelector(tk.Frame):
    def __init__(self, parent, options, variable, command=None, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, **kw)
        self.options = options; self.var = variable; self.cmd = command; self._pills = {}
        self._build()

    def _build(self):
        track = tk.Frame(self, bg=C["input"], padx=3, pady=3); track.pack(fill="x")
        for i, (label, value) in enumerate(self.options):
            track.columnconfigure(i, weight=1)
            c = tk.Canvas(track, height=26, highlightthickness=0, bg=C["input"], cursor="hand2")
            c.grid(row=0, column=i, sticky="ew", padx=2)
            self._pills[value] = c
            c.bind("<Button-1>", lambda e, v=value: self._select(v))
            c.bind("<Enter>",    lambda e, v=value: self._hover(v, True))
            c.bind("<Leave>",    lambda e, v=value: self._hover(v, False))
            c.bind("<Configure>", lambda e, v=value: self._draw_pill(v))

    def _select(self, value):
        self.var.set(value)
        for v in self._pills: self._draw_pill(v)
        if self.cmd: self.cmd()

    def _hover(self, value, on):
        if self.var.get() != value: self._draw_pill(value, hover=on)

    def _draw_pill(self, value, hover=False):
        c = self._pills[value]; c.delete("all")
        w = c.winfo_width() or 120; h = c.winfo_height() or 26
        sel = (self.var.get() == value)
        label = next(l for l, v in self.options if v == value)
        r = 5
        if sel:    bg, fg = C["accent_bg"], C["accent"]
        elif hover: bg, fg = C["panel2"], C["t1"]
        else:      bg, fg = C["input"], C["t2"]
        pts = [r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        c.create_polygon(pts, smooth=True, fill=bg, outline=bg)
        c.create_text(w//2, h//2, text=label, fill=fg,
                      font=(F_BOLD if sel else F_SMALL), anchor="center")


class DarkSlider(tk.Frame):
    def __init__(self, parent, from_, to, resolution, variable,
                 label="", unit="", command=None, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, **kw)
        self.columnconfigure(0, weight=1); self._cmd = command; self._unit = unit
        top = tk.Frame(self, bg=self.cget("bg")); top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        tk.Label(top, text=label, font=F_SMALL, fg=C["t2"],
                 bg=self.cget("bg"), anchor="w").grid(row=0, column=0, sticky="w")
        self._val_lbl = tk.Label(top, text="", font=F_BOLD, fg=C["accent"],
                                 bg=self.cget("bg"), anchor="e")
        self._val_lbl.grid(row=0, column=1, sticky="e")
        self._scale = tk.Scale(self, from_=from_, to=to, resolution=resolution,
                               orient="horizontal", variable=variable,
                               bg=C["bg"], fg=C["t1"], troughcolor=C["input"],
                               activebackground=C["accent"], highlightthickness=0,
                               showvalue=False, sliderrelief="flat", sliderlength=14,
                               command=self._on_change)
        self._scale.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        self._info_lbl = tk.Label(self, text="", font=F_SMALL, fg=C["t3"],
                                  bg=self.cget("bg"), anchor="w")
        self._info_lbl.grid(row=2, column=0, sticky="w")
        self._update_label(variable.get())

    def _on_change(self, val): self._update_label(val); (self._cmd and self._cmd(val))

    def _update_label(self, val):
        try:
            v = float(val)
            if self._unit == "s" and v >= 60: self._val_lbl.config(text=hms(v))
            elif self._unit == "s":           self._val_lbl.config(text=f"{int(v)} s")
            else: self._val_lbl.config(text=f"{int(v)} {self._unit}".strip())
        except Exception: pass

    def set_info(self, text): self._info_lbl.config(text=text)
    def set_state(self, state): self._scale.config(state=state)


class RoundedCombo(tk.Frame):
    def __init__(self, parent, values, variable, width=80, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        super().__init__(parent, **kw)
        self._values = values; self._var = variable; self._width = width; self._open = False
        self._btn = tk.Canvas(self, height=28, width=width, highlightthickness=0,
                              bg=self.cget("bg"), cursor="hand2")
        self._btn.pack()
        self._btn.bind("<Button-1>",  self._toggle)
        self._btn.bind("<Configure>", lambda e: self._draw())
        self._var.trace_add("write",  lambda *a: self._draw())

    def _draw(self):
        c = self._btn; c.delete("all")
        w = c.winfo_width() or self._width; h = c.winfo_height() or 28; r = 7
        pts = [r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        c.create_polygon(pts, smooth=True, fill=C["input"], outline="")
        c.create_text(10, h//2, text=str(self._var.get()), fill=C["t1"], font=F_UI, anchor="w")
        cx = w-14; cy = h//2
        c.create_polygon(cx-4, cy-2, cx+4, cy-2, cx, cy+3, fill=C["t3"], outline="")

    def _toggle(self, event=None):
        if self._open: self._close_menu(); return
        self._open = True
        menu = tk.Menu(self, tearoff=0, bg=C["panel2"], fg=C["t1"],
                       activebackground=C["accent_bg"], activeforeground=C["accent"],
                       relief="flat", bd=0, font=F_UI)
        for v in self._values:
            menu.add_command(label=str(v), command=lambda val=v: self._pick(val))
        menu.tk_popup(self._btn.winfo_rootx(),
                      self._btn.winfo_rooty() + self._btn.winfo_height())
        menu.bind("<Unmap>", lambda e: self._close_menu())

    def _pick(self, val): self._var.set(val); self._open = False; self._draw()
    def _close_menu(self): self._open = False


class DarkEntry(tk.Entry):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", C["input"]); kw.setdefault("fg", C["t1"])
        kw.setdefault("insertbackground", C["t1"]); kw.setdefault("relief", "flat")
        kw.setdefault("font", F_UI); kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", C["border"])
        kw.setdefault("highlightcolor", C["accent"])
        super().__init__(parent, **kw)


class DarkProgress(tk.Canvas):
    def __init__(self, parent, height=4, **kw):
        kw.setdefault("bg", C["bg"])
        super().__init__(parent, height=height, highlightthickness=0, **kw)
        self._v = 0; self.bind("<Configure>", lambda e: self._draw())

    def set(self, v): self._v = max(0, min(100, v)); self._draw()

    def _draw(self):
        self.delete("all"); w = self.winfo_width(); h = self.winfo_height()
        if w < 4: return
        r = h//2; self._rr(0, 0, w, h, r, fill=C["panel2"], outline="")
        if self._v > 0:
            fw = max(r*2, int(w*self._v/100))
            self._rr(0, 0, fw, h, r, fill=C["accent"], outline="")

    def _rr(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
               x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        self.create_polygon(pts, smooth=True, **kw)


class ModernScrollbar(tk.Canvas):
    def __init__(self, parent, command=None, **kw):
        kw.setdefault("bg", C["bg"])
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("width", 8)
        super().__init__(parent, **kw)
        self.command = command
        self.pack_propagate(False)
        self.configure(width=8)
        self._thumb_top = 0.0
        self._thumb_height = 1.0
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_thumb = 0.0
        self._visible = True
        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._hover = False
        self._base_color = C["border"]
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self._hover = True
        self._redraw()

    def _on_leave(self, event):
        self._hover = False
        self._redraw()

    def set(self, first, last):
        first = max(0.0, min(1.0, float(first)))
        last = max(0.0, min(1.0, float(last)))
        if last <= first:
            first, last = 0.0, 1.0
        self._thumb_top = first
        self._thumb_height = last - first
        self._redraw()

    def _redraw(self, event=None):
        self.delete("all")
        if not self._visible:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return
        thumb_h = max(20, self._thumb_height * h)
        thumb_y = self._thumb_top * h
        thumb_y = max(0, min(thumb_y, h - thumb_h))
        r = min(5, w // 2, thumb_h // 2)
        thumb_color = C["accent"] if self._hover else self._base_color
        self._draw_rounded_rect(2, thumb_y, w - 2, thumb_y + thumb_h, r,
                                fill=thumb_color, outline="")

    def _draw_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        points = [x1+r, y1, x2-r, y1,
                  x2, y1, x2, y1+r,
                  x2, y2-r, x2, y2,
                  x2-r, y2, x1+r, y2,
                  x1, y2, x1, y2-r,
                  x1, y1+r, x1, y1]
        self.create_polygon(points, smooth=True, **kw)

    def _on_press(self, event):
        h = self.winfo_height()
        thumb_y = self._thumb_top * h
        thumb_h = max(20, self._thumb_height * h)
        if thumb_y <= event.y <= thumb_y + thumb_h:
            self._dragging = True
            self._drag_start_y = event.y
            self._drag_start_thumb = self._thumb_top
            self.configure(cursor="hand2")
        else:
            if event.y < thumb_y:
                delta = -0.1
            else:
                delta = 0.1
            new_top = max(0.0, min(1.0, self._thumb_top + delta))
            self._move_to(new_top)

    def _on_drag(self, event):
        if not self._dragging:
            return
        h = self.winfo_height()
        if h < 1:
            return
        dy = (event.y - self._drag_start_y) / h
        new_top = max(0.0, min(1.0 - self._thumb_height, self._drag_start_thumb + dy))
        self._move_to(new_top)

    def _on_release(self, event):
        self._dragging = False
        self.configure(cursor="")

    def _move_to(self, top):
        if self.command:
            self.command("moveto", top)


class HSep(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["border"], height=1, **kw)


class SectLabel(tk.Label):
    def __init__(self, parent, text, **kw):
        kw.setdefault("bg", C["bg"]); kw.setdefault("fg", C["t3"])
        kw.setdefault("font", F_SECT); kw.setdefault("anchor", "w")
        super().__init__(parent, text=text.upper(), **kw)


class Tooltip:
    """D5 : tooltip unifié. Paramètres de style pour couvrir les deux anciens systèmes :
    - défaut (jaune) : tooltips d'aide sur les radiobuttons tonemap
    - gris centré   : tooltips de chemin sur les boutons Parcourir"""
    DELAY = 0
    def __init__(self, widget, text_fn, bg="#fffae8", fg="#3a2a00",
                 border="#c8b87a", dx=0, dy=4, padx=10, pady=6, anchor="w"):
        self._w = widget
        self._fn = text_fn
        self._bg = bg
        self._fg = fg
        self._border = border
        self._dx = dx
        self._dy = dy
        self._padx = padx
        self._pady = pady
        self._anchor = anchor
        self._win = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel,   add="+")
        widget.bind("<Button>", self._cancel,  add="+")

    def _schedule(self, e=None):
        self._cancel(); self._job = self._w.after(self.DELAY, self._show)

    def _cancel(self, e=None):
        if self._job: self._w.after_cancel(self._job); self._job = None
        if self._win: self._win.destroy(); self._win = None

    def _show(self):
        text = self._fn()
        if not text: return
        x = self._w.winfo_rootx() + self._dx
        y = self._w.winfo_rooty() + self._w.winfo_height() + self._dy
        self._win = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        lbl = tk.Label(tw, text=text, font=F_SMALL, fg=self._fg, bg=self._bg,
                       justify="left", padx=self._padx, pady=self._pady,
                       relief="flat", bd=0)
        lbl.pack()
        tw.update_idletasks()
        w = tw.winfo_reqwidth()
        h = tw.winfo_reqheight()
        sw = self._w.winfo_screenwidth()
        if x + w > sw - 10: x = sw - w - 10
        tw.geometry(f"+{x}+{y}")
        cv = tk.Canvas(tw, width=w, height=h, bg=self._bg, highlightthickness=0)
        cv.place(x=0, y=0)
        r = 8
        pts = [r,0,w-r,0,w,0,w,r,w,h-r,w,h,w-r,h,r,h,0,h,0,h-r,0,r,0,0]
        if self._border:
            cv.create_polygon(pts, smooth=True, fill=self._bg, outline=self._border, width=1)
        else:
            cv.create_polygon(pts, smooth=True, fill=self._bg, outline="")
        if self._anchor == "center":
            cv.create_text(w//2, h//2, text=text, font=F_SMALL, fill=self._fg, anchor="center")
        else:
            cv.create_text(self._padx, h//2, text=text, font=F_SMALL,
                           fill=self._fg, anchor="w", justify="left")
        lbl.lift()


def setup_style(root):
    s = ttk.Style(root); s.theme_use("clam")
    s.configure("TCombobox", fieldbackground=C["input"], background=C["input"],
                foreground=C["t1"], selectbackground=C["sel_bg"],
                selectforeground=C["t1"], bordercolor=C["border"],
                arrowcolor=C["t2"], font=F_UI, padding=4)
    s.map("TCombobox", fieldbackground=[("readonly", C["input"])],
          bordercolor=[("focus", C["accent"])])