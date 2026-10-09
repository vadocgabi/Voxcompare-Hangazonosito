"""Design tokens, Windows light/dark detection and flat tkinter widgets."""
from __future__ import annotations

import ctypes
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    card: str
    border: str
    text: str
    muted: str
    track: str
    accent: str
    accent_text: str
    good: str
    warn: str
    bad: str
    hover: str


DARK = Theme("dark", bg="#1b1b1f", card="#25252b", border="#33333b", text="#f3f3f6", muted="#9b9ba6",
             track="#34343d", accent="#4f8cff", accent_text="#ffffff", good="#43b581", warn="#f5a623",
             bad="#ef5350", hover="#2f2f37")
LIGHT = Theme("light", bg="#f4f4f7", card="#ffffff", border="#e2e2e9", text="#16161b", muted="#6a6a77",
              track="#e7e7ee", accent="#2563eb", accent_text="#ffffff", good="#1f8f55", warn="#e08600",
              bad="#d93636", hover="#ececf2")


def current_theme() -> Theme:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return LIGHT if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else DARK
    except OSError:
        return LIGHT


def font(root: tk.Misc, size: int = 10, bold: bool = False) -> tuple:
    families = set(root.tk.call("font", "families"))
    family = "Segoe UI Variable Text" if "Segoe UI Variable Text" in families else "Segoe UI"
    return (family, size, "bold" if bold else "normal")


def style_window(window: tk.Misc, theme: Theme) -> None:
    """Dark title bar and rounded corners on Windows 10/11; ignored elsewhere."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        for attribute, value in ((20, int(theme.name == "dark")), (33, 2)):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(ctypes.c_int(value)), 4)
    except (OSError, AttributeError):
        pass


def label(parent: tk.Misc, theme: Theme, text: str = "", size: int = 10, bold: bool = False,
          muted: bool = False, bg: Optional[str] = None, **options) -> tk.Label:
    return tk.Label(parent, text=text, font=font(parent, size, bold), bg=bg or theme.card,
                    fg=theme.muted if muted else theme.text, **options)


def button(parent: tk.Misc, theme: Theme, text: str, command: Callable, primary: bool = False,
           bg: Optional[str] = None) -> tk.Label:
    """Flat button built from a Label so every colour is themeable."""
    normal = theme.accent if primary else (bg or theme.card)
    hover = theme.accent if primary else theme.hover
    widget = tk.Label(parent, text=text, font=font(parent, 10, primary), bg=normal,
                      fg=theme.accent_text if primary else theme.text, padx=18, pady=7, cursor="hand2",
                      highlightthickness=0 if primary else 1, highlightbackground=theme.border)
    state = {"enabled": True}
    widget.bind("<Button-1>", lambda event: command() if state["enabled"] else None)
    widget.bind("<Enter>", lambda event: state["enabled"] and widget.configure(bg=hover))
    widget.bind("<Leave>", lambda event: widget.configure(bg=normal if state["enabled"] else theme.track))

    def set_enabled(enabled: bool) -> None:
        state["enabled"] = enabled
        widget.configure(bg=normal if enabled else theme.track, cursor="hand2" if enabled else "arrow",
                         fg=(theme.accent_text if primary else theme.text) if enabled else theme.muted)

    widget.set_enabled = set_enabled
    return widget


def entry(parent: tk.Misc, theme: Theme, variable: tk.StringVar) -> tk.Entry:
    return tk.Entry(parent, textvariable=variable, font=font(parent, 10), bg=theme.bg, fg=theme.text,
                    insertbackground=theme.text, relief="flat", highlightthickness=1,
                    highlightbackground=theme.border, highlightcolor=theme.accent)


def card(parent: tk.Misc, theme: Theme, **pack) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.card, highlightthickness=1, highlightbackground=theme.border,
                     padx=16, pady=14)
    frame.pack(fill="x", **pack)
    return frame


class Gauge(tk.Canvas):
    """0-100 bar with the uncertain zone shaded and a marker at the decision threshold."""

    def __init__(self, parent: tk.Misc, theme: Theme, threshold_pct: float, band: tuple, height: int = 12):
        super().__init__(parent, height=height, bg=theme.card, highlightthickness=0, bd=0)
        self.theme, self.h = theme, height
        self.threshold_pct, self.band = threshold_pct, band
        self.pct: Optional[float] = None
        self.color = theme.accent
        self.bind("<Configure>", lambda event: self._draw())

    def set(self, pct: Optional[float], color: str) -> None:
        self.pct, self.color = pct, color
        self._draw()

    def _line(self, x0: float, x1: float, color: str) -> None:
        r = self.h / 2
        self.create_line(x0 + r, r, max(x0 + r, x1 - r), r, width=self.h, capstyle="round", fill=color)

    def _draw(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            return
        self._line(0, w, self.theme.track)
        lo, hi = (w * self.band[0] / 100, w * self.band[1] / 100)
        self.create_rectangle(lo, 0, hi, self.h, fill=self.theme.border, width=0)
        if self.pct is not None:
            self._line(0, max(w * self.pct / 100, self.h), self.color)
        x = w * self.threshold_pct / 100
        self.create_line(x, -1, x, self.h + 1, fill=self.theme.text, width=2)
