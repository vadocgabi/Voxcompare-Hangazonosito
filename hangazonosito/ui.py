"""Main window."""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Optional

from . import audio
from .audio import AudioError
from .engine import (THRESHOLD, UNCERTAIN_RANGE, Result, SpeakerVerifier, confidence)
from .i18n import LANGS, credit_text, load_language, save_language, tr
from .theme import (Gauge, Theme, button, card, current_theme, entry, font, label, style_window)

AUDIO_PATTERNS = "*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.wma *.opus"
MIN_WIDTH = 720


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / name


class Busy(tk.Canvas):
    """Small indeterminate progress indicator."""

    def __init__(self, parent: tk.Misc, theme: Theme):
        super().__init__(parent, height=4, bg=theme.bg, highlightthickness=0, bd=0)
        self.theme, self._job, self._x = theme, None, 0.0

    def start(self) -> None:
        if self._job is None:
            self._tick()

    def stop(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self.delete("all")

    def _tick(self) -> None:
        width = max(self.winfo_width(), 1)
        self.delete("all")
        self.create_rectangle(0, 0, width, 4, fill=self.theme.track, width=0)
        length = width * 0.25
        left = self._x - length
        self.create_rectangle(max(left, 0), 0, min(self._x, width), 4, fill=self.theme.accent, width=0)
        self._x = (self._x + width * 0.03) % (width + length)
        self._job = self.after(16, self._tick)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = current_theme()
        self.lang = load_language()
        self.verifier = SpeakerVerifier()
        self.file_vars = [tk.StringVar(), tk.StringVar()]
        self.file_infos = ["", ""]
        self.result: Optional[Result] = None
        self.error: Optional[str] = None
        self.status_key = "ready"
        self.running = False

        root.configure(bg=self.theme.bg)
        root.minsize(MIN_WIDTH, 420)
        try:
            root.iconbitmap(str(resource_path("app.ico")))
        except tk.TclError:
            pass
        root.bind("<Return>", lambda event: self.identify())
        self.build()
        style_window(root, self.theme)
        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
        y = max(20, (root.winfo_screenheight() - root.winfo_reqheight()) // 3)
        root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------ layout
    def T(self, key: str, **kwargs) -> str:
        return tr(self.lang, key, **kwargs)

    def build(self) -> None:
        theme, root = self.theme, self.root
        for child in root.winfo_children():
            child.destroy()
        root.title(self.T("title"))
        body = tk.Frame(root, bg=theme.bg, padx=24, pady=20)
        body.pack(fill="both", expand=True)

        # header: title + language switch
        header = tk.Frame(body, bg=theme.bg)
        header.pack(fill="x")
        titles = tk.Frame(header, bg=theme.bg)
        titles.pack(side="left")
        label(titles, theme, self.T("title"), 20, True, bg=theme.bg).pack(anchor="w")
        label(titles, theme, self.T("subtitle"), 10, muted=True, bg=theme.bg).pack(anchor="w")
        switch = tk.Frame(header, bg=theme.bg)
        switch.pack(side="right", anchor="n")
        for code in LANGS:
            chosen = code == self.lang
            tab = label(switch, theme, code.upper(), 9, chosen, muted=not chosen, bg=theme.card if chosen
                        else theme.bg, padx=10, pady=3, cursor="hand2")
            tab.pack(side="left", padx=1)
            tab.bind("<Button-1>", lambda event, c=code: self.set_language(c))

        # files
        files = card(body, theme, pady=(16, 10))
        for index, key in enumerate(("file1", "file2")):
            label(files, theme, self.T(key), 9, True).pack(anchor="w", pady=(0 if index == 0 else 10, 3))
            row = tk.Frame(files, bg=theme.card)
            row.pack(fill="x")
            field = entry(row, theme, self.file_vars[index])
            field.pack(side="left", fill="x", expand=True, ipady=6)
            button(row, theme, self.T("browse"), lambda i=index: self.browse(i)).pack(side="left", padx=(8, 0))
            info = label(files, theme, self.file_infos[index], 9, muted=True)
            info.pack(anchor="w", pady=(3, 0))
            setattr(self, f"info_label_{index}", info)

        # actions
        actions = tk.Frame(body, bg=theme.bg)
        actions.pack(fill="x", pady=(0, 6))
        self.identify_button = button(actions, theme, self.T("identify"), self.identify, primary=True)
        self.identify_button.pack(side="left")
        button(actions, theme, self.T("clear"), self.clear, bg=theme.bg).pack(side="left", padx=8)
        self.device_label = label(actions, theme, self.device_text(), 9, muted=True, bg=theme.bg)
        self.device_label.pack(side="right")
        self.busy = Busy(body, theme)
        self.busy.pack(fill="x", pady=(0, 8))

        # result area is filled by render_result()
        self.result_host = tk.Frame(body, bg=theme.bg)
        self.result_host.pack(fill="x")

        # notice: this is not an official / expert tool
        notice = label(body, theme, "ⓘ  " + self.T("disclaimer"), 9, muted=True, bg=theme.bg,
                       wraplength=MIN_WIDTH - 60, justify="left")
        notice.pack(fill="x", side="bottom", pady=(12, 0), anchor="w")

        # footer
        footer = tk.Frame(body, bg=theme.bg)
        footer.pack(fill="x", side="bottom", pady=(14, 0))
        self.status_label = label(footer, theme, "", 9, muted=True, bg=theme.bg)
        self.status_label.pack(side="left")
        label(footer, theme, credit_text(self.lang), 8, muted=True, bg=theme.bg).pack(side="right")
        self.set_status(self.status_key)
        self.render_result()
        self.identify_button.set_enabled(not self.running)

    def device_text(self) -> str:
        if self.verifier.cuda:
            return self.T("device_gpu", n=self.verifier.device_name)
        return self.T("device_cpu")

    # ------------------------------------------------------------ result card
    def render_result(self) -> None:
        theme = self.theme
        for child in self.result_host.winfo_children():
            child.destroy()
        if self.error:
            box = card(self.result_host, theme)
            box.configure(highlightbackground=theme.bad)
            label(box, theme, self.error, 10, wraplength=MIN_WIDTH - 90, justify="left").pack(anchor="w")
            return
        if self.result is None:
            return
        result = self.result
        colour = {"same": theme.good, "different": theme.bad, "uncertain": theme.warn}[result.verdict]
        box = card(self.result_host, theme)

        top = tk.Frame(box, bg=theme.card)
        top.pack(fill="x")
        tk.Label(top, text=f"{result.confidence:.1f}%", font=font(top, 34, True), bg=theme.card,
                 fg=colour).pack(side="left")
        side = tk.Frame(top, bg=theme.card)
        side.pack(side="left", padx=18)
        tk.Label(side, text=self.T(f"verdict_{result.verdict}"), font=font(side, 14, True), bg=theme.card,
                 fg=colour).pack(anchor="w")
        label(side, theme, self.T("confidence_hint"), 9, muted=True).pack(anchor="w")

        low, high = confidence(THRESHOLD - UNCERTAIN_RANGE), confidence(THRESHOLD + UNCERTAIN_RANGE)
        gauge = Gauge(box, theme, confidence(THRESHOLD), (low, high))
        gauge.pack(fill="x", pady=(12, 2))
        gauge.set(result.confidence, colour)
        scale = tk.Frame(box, bg=theme.card)
        scale.pack(fill="x")
        label(scale, theme, self.T("gauge_different"), 8, muted=True).pack(side="left")
        label(scale, theme, self.T("gauge_same"), 8, muted=True).pack(side="right")

        grid = tk.Frame(box, bg=theme.card)
        grid.pack(fill="x", pady=(14, 0))
        for column in (1, 3):
            grid.columnconfigure(column, weight=1)
        for position, (key, value) in enumerate(self.metrics(result)):
            row, column = divmod(position, 2)
            label(grid, theme, self.T(key), 9, muted=True).grid(row=row, column=column * 2, sticky="w",
                                                                pady=2, padx=(0, 10))
            label(grid, theme, value, 9, True).grid(row=row, column=column * 2 + 1, sticky="w", pady=2,
                                                    padx=(0, 20))

        for key, argument in result.warnings:
            parts = argument.split("|")
            text = self.T(key, n=parts[0], s=parts[1] if len(parts) > 1 else "")
            warning = label(box, theme, "⚠  " + text, 9, wraplength=MIN_WIDTH - 90, justify="left")
            warning.configure(fg=theme.warn)
            warning.pack(anchor="w", pady=(8, 0))

        button(box, theme, self.T("copy"), self.copy_result).pack(anchor="e", pady=(12, 0))

    def metrics(self, result: Result) -> list:
        first, second = result.files
        speech = f"{first.speech_seconds:.1f} s  /  {second.speech_seconds:.1f} s"

        def percent(info) -> str:
            return "–" if info.consistency is None else f"{info.consistency * 100:.0f}%"

        model = self.T("m_model_same" if result.prediction else "m_model_different")
        return [("m_score", f"{result.score:.4f}"),
                ("m_threshold", f"{THRESHOLD:.2f}  (±{UNCERTAIN_RANGE:.2f})"),
                ("m_model", model),
                ("m_speech", speech),
                ("m_consistency", f"{percent(first)}  /  {percent(second)}"),
                ("m_time", f"{result.seconds:.1f} s"),
                ("m_device", self.device_text())]

    # ------------------------------------------------------------ actions
    def set_language(self, code: str) -> None:
        if code == self.lang:
            return
        self.lang = code
        save_language(code)
        self.build()

    def set_status(self, key: str, **kwargs) -> None:
        self.status_key = key
        self.status_label.configure(text=self.T(key, **kwargs))

    def browse(self, index: int) -> None:
        path = filedialog.askopenfilename(
            title=self.T("browse_title"),
            filetypes=[(self.T("filter_audio"), AUDIO_PATTERNS), (self.T("filter_all"), "*.*")])
        if path:
            self.file_vars[index].set(os.path.normpath(path))
            self.probe(index, path)

    def probe(self, index: int, path: str) -> None:
        """Shows duration and net speech of a chosen file (computed in the background)."""
        self.file_infos[index] = self.T("reading")
        getattr(self, f"info_label_{index}").configure(text=self.file_infos[index])

        def work() -> None:
            try:
                samples = audio.load_audio(path)
                total = len(samples) / audio.SAMPLE_RATE
                speech = len(audio.trim_silence(samples)) / audio.SAMPLE_RATE
                text = self.T("file_info", d=f"{total:.1f} s", s=f"{speech:.1f} s")
            except AudioError as e:
                text = self.T(e.key, a=e.arg)
            except Exception:
                text = ""
            self.root.after(0, lambda: self.set_file_info(index, path, text))

        threading.Thread(target=work, daemon=True).start()

    def set_file_info(self, index: int, path: str, text: str) -> None:
        if self.file_vars[index].get().strip() and os.path.normpath(path) == \
                os.path.normpath(self.file_vars[index].get().strip()):
            self.file_infos[index] = text
            try:
                getattr(self, f"info_label_{index}").configure(text=text)
            except tk.TclError:
                pass

    def clear(self) -> None:
        if self.running:
            return
        for index in (0, 1):
            self.file_vars[index].set("")
            self.file_infos[index] = ""
            getattr(self, f"info_label_{index}").configure(text="")
        self.result, self.error = None, None
        self.render_result()
        self.set_status("ready")

    def identify(self) -> None:
        if self.running:
            return
        paths = [var.get().strip().strip('"') for var in self.file_vars]
        if not all(paths):
            self.show_error(self.T("need_files"))
            return
        self.running, self.result, self.error = True, None, None
        self.identify_button.set_enabled(False)
        self.render_result()
        self.busy.start()
        self.set_status("loading_model")

        def progress(key: str) -> None:
            self.root.after(0, lambda: self.set_status(key))

        def work() -> None:
            try:
                result = self.verifier.verify(paths[0], paths[1], progress)
                self.root.after(0, lambda: self.finish(result, None))
            except AudioError as e:
                self.root.after(0, lambda: self.finish(None, self.T(e.key, a=e.arg)))
            except Exception as e:
                self.root.after(0, lambda: self.finish(None, self.T("err_generic", a=str(e)[:300])))

        threading.Thread(target=work, daemon=True).start()

    def finish(self, result: Optional[Result], error: Optional[str]) -> None:
        self.running = False
        self.busy.stop()
        self.identify_button.set_enabled(True)
        self.result, self.error = result, error
        self.render_result()
        self.set_status("done" if result else "failed")

    def show_error(self, text: str) -> None:
        self.result, self.error = None, text
        self.render_result()
        self.set_status("failed")

    def copy_result(self) -> None:
        if self.result is None:
            return
        result = self.result
        lines = [f"{self.T('title')} {datetime.now():%Y-%m-%d %H:%M}",
                 f"1: {os.path.basename(result.files[0].path)}", f"2: {os.path.basename(result.files[1].path)}",
                 f"{self.T('verdict_' + result.verdict)}: {result.confidence:.1f}%"]
        lines += [f"{self.T(key)}: {value}" for key, value in self.metrics(result)]
        lines += ["", self.T("disclaimer")]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.set_status("copied")


def run() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
