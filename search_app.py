# -*- coding: utf-8 -*-
"""ForSearch — busca em .txt, .jsonl, .csv, .sql e dumps URL/user/pass."""

import os
import re
import sys
import math
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from shutil import which

# .txt primeiro (dumps de URL/user/pass)
DEFAULT_EXTS = [
    ".txt", ".jsonl", ".json", ".csv", ".sql", ".log", ".tsv", ".dat",
    ".md", ".xml", ".html", ".htm", ".env", ".ini", ".cfg",
    ".conf", ".yaml", ".yml", ".js", ".ts", ".py",
]

# Tema: preto + roxo
C = {
    "bg": "#0a0a0f",
    "surface": "#12121a",
    "surface2": "#181822",
    "elevated": "#22222e",
    "border": "#2a2a3a",
    "border_focus": "#a855f7",
    "accent": "#8b5cf6",
    "accent_hover": "#a78bfa",
    "accent_deep": "#6d28d9",
    "accent_soft": "#1e1433",
    "shimmer": ["#4c1d95", "#7c3aed", "#c084fc", "#e9d5ff", "#a78bfa", "#7c3aed", "#4c1d95"],
    "text": "#f3f0ff",
    "text_dim": "#a5a0b8",
    "text_faint": "#6b6680",
    "input": "#0e0e14",
    "success": "#34d399",
    "row": "#12121a",
    "row_alt": "#16161f",
    "white": "#ffffff",
}


class ShimmerBorder(tk.Frame):
    """Card com borda shimmer animada (roxo)."""

    def __init__(self, master, pad=2, **kwargs):
        super().__init__(master, bg=C["bg"], **kwargs)
        self._phase = 0.0
        self._pad = pad
        self._running = True

        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=C["surface"])
        self._win = self.canvas.create_window(pad, pad, anchor="nw", window=self.inner)

        self.inner.bind("<Configure>", lambda e: self._draw_border())
        self.canvas.bind("<Configure>", self._on_canvas)
        self._animate()

    def _on_canvas(self, e):
        w = max(e.width - self._pad * 2, 1)
        h = max(e.height - self._pad * 2, 1)
        self.canvas.coords(self._win, self._pad, self._pad)
        self.canvas.itemconfigure(self._win, width=w, height=h)
        self._draw_border()

    def _lerp_color(self, c1, c2, t):
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

        a, b = hex_to_rgb(c1), hex_to_rgb(c2)
        r = int(a[0] + (b[0] - a[0]) * t)
        g = int(a[1] + (b[1] - a[1]) * t)
        bl = int(a[2] + (b[2] - a[2]) * t)
        return f"#{r:02x}{g:02x}{bl:02x}"

    def _color_at(self, t):
        colors = C["shimmer"]
        n = len(colors)
        t = t % 1.0
        idx = t * (n - 1)
        i = int(idx)
        frac = idx - i
        return self._lerp_color(colors[i], colors[min(i + 1, n - 1)], frac)

    def _draw_border(self):
        self.canvas.delete("shine")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 8 or h < 8:
            return
        pad = self._pad
        segs = []
        steps = 36
        for i in range(steps):
            segs.append((pad + (w - pad * 2) * i / steps, pad / 2))
        for i in range(steps):
            segs.append((w - pad / 2, pad + (h - pad * 2) * i / steps))
        for i in range(steps):
            segs.append((w - pad - (w - pad * 2) * i / steps, h - pad / 2))
        for i in range(steps):
            segs.append((pad / 2, h - pad - (h - pad * 2) * i / steps))

        total = len(segs)
        for i, (x, y) in enumerate(segs):
            t = (i / total + self._phase) % 1.0
            color = self._color_at(t)
            glow = abs(math.sin((t * 4 + self._phase * 6) * math.pi))
            r = 1.5 + glow * 1.8
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color, outline="", tags="shine",
            )

    def _animate(self):
        if not self._running:
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self._phase = (self._phase + 0.014) % 1.0
        self._draw_border()
        self.after(33, self._animate)

    def stop(self):
        self._running = False


class FuzzyMatch:
    @staticmethod
    def score(query: str, text: str) -> float:
        q = query.lower().strip()
        t = text.lower()
        if not q:
            return 1.0
        if q in t:
            name = Path(t).name
            if q in name:
                return 100.0 - name.find(q) * 0.1 + (10 if name.startswith(q) else 0)
            return 50.0 - t.find(q) * 0.01
        qi, score, last = 0, 0.0, -2
        for i, ch in enumerate(t):
            if qi < len(q) and ch == q[qi]:
                score += 2 if i == last + 1 else 1
                last = i
                qi += 1
        return 0.0 if qi < len(q) else score / max(len(t), 1)


class SearchEngine:
    """Busca linha a linha — padrão = contém (ideal para URL / user / pass)."""

    def __init__(
        self,
        root_dir,
        query,
        extensions,
        case_sensitive=False,
        whole_word=False,
        regex_mode=False,
        max_results=10000,
        on_progress=None,
        on_hit=None,
        should_stop=None,
    ):
        self.root_dir = Path(root_dir)
        self.query = query
        self.extensions = {
            (e if e.startswith(".") else f".{e}").lower() for e in extensions
        }
        self.case_sensitive = case_sensitive
        self.whole_word = whole_word
        self.regex_mode = regex_mode
        self.max_results = max_results
        self.on_progress = on_progress or (lambda *a: None)
        self.on_hit = on_hit or (lambda *a: None)
        self.should_stop = should_stop or (lambda: False)
        self.hits = []
        self.files_scanned = 0
        self.files_total = 0
        self.errors = 0
        self.skipped_binary = 0

    def _compile_pattern(self):
        flags = 0 if self.case_sensitive else re.IGNORECASE
        if self.regex_mode:
            return re.compile(self.query, flags)
        escaped = re.escape(self.query)
        if self.whole_word:
            # \b falha em vários dumps; usa limites mais tolerantes
            escaped = rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
        return re.compile(escaped, flags)

    def _iter_files(self):
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".idea", ".vs", "dist", "build",
        }
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
            for name in filenames:
                if self.should_stop():
                    return
                path = Path(dirpath) / name
                ext = path.suffix.lower()
                # aceita .txt / .TXT e arquivos sem extensão se .* estiver na lista
                if ext in self.extensions or (ext == "" and ".*" in self.extensions):
                    yield path
                elif not self.extensions:
                    yield path

    def run(self):
        try:
            pattern = self._compile_pattern()
        except re.error as e:
            raise ValueError(f"Regex inválido: {e}") from e

        files = list(self._iter_files())
        self.files_total = len(files)
        total = len(files) or 1

        for i, path in enumerate(files):
            if self.should_stop() or len(self.hits) >= self.max_results:
                break
            self.files_scanned += 1
            self.on_progress(i + 1, total, str(path))
            try:
                self._scan_file(path, pattern)
            except (OSError, PermissionError):
                self.errors += 1
        return self.hits

    def _decode_bytes(self, raw: bytes) -> str:
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _scan_file(self, path: Path, pattern):
        try:
            with open(path, "rb") as f:
                sample = f.read(4096)
                if sample.count(b"\x00") > 8:
                    self.skipped_binary += 1
                    return
                f.seek(0)
                raw = f.read()
            if b"\x00" in raw[:8192] and raw.count(b"\x00") > 20:
                self.skipped_binary += 1
                return

            text = self._decode_bytes(raw)
            lines = text.splitlines()
            try:
                rel = str(path.relative_to(self.root_dir))
            except ValueError:
                rel = str(path)
            full_path = str(path.resolve())

            # dump estilo REDLINE: URL / Username / Password
            if self._looks_like_cred_dump(lines):
                for block in self._iter_cred_blocks(lines):
                    if self.should_stop() or len(self.hits) >= self.max_results:
                        return
                    if pattern.search(block["text"]):
                        hit = {
                            "path": full_path,
                            "line": block["start"],
                            "text": block["text"],
                            "rel": rel,
                            "url": block.get("url", ""),
                            "username": block.get("username", ""),
                            "password": block.get("password", ""),
                            "summary": block.get("summary", block["text"].splitlines()[0]),
                        }
                        self.hits.append(hit)
                        self.on_hit(hit)
                return

            # arquivo comum: linha inteira que contém o termo
            for lineno, line in enumerate(lines, 1):
                if self.should_stop() or len(self.hits) >= self.max_results:
                    return
                if pattern.search(line):
                    parsed = self._parse_inline_cred(line)
                    hit = {
                        "path": full_path,
                        "line": lineno,
                        "text": line,
                        "rel": rel,
                        "url": parsed.get("url", ""),
                        "username": parsed.get("username", ""),
                        "password": parsed.get("password", ""),
                        "summary": line[:200],
                    }
                    self.hits.append(hit)
                    self.on_hit(hit)
        except Exception:
            self.errors += 1

    @staticmethod
    def _looks_like_cred_dump(lines) -> bool:
        """Detecta dump com campos URL: / Username: / Password:."""
        flags = {"url": 0, "user": 0, "pass": 0}
        for line in lines[:400]:
            s = line.strip().lower()
            if s.startswith("url:"):
                flags["url"] += 1
            elif s.startswith("username:") or s.startswith("user:"):
                flags["user"] += 1
            elif s.startswith("password:") or s.startswith("pass:"):
                flags["pass"] += 1
        return flags["url"] >= 1 and flags["user"] >= 1 and flags["pass"] >= 1

    @staticmethod
    def _is_block_separator(line: str) -> bool:
        s = line.strip()
        if not s:
            return True
        if set(s) <= {"=", "-", "*", "_", "#"} and len(s) >= 3:
            return True
        if s.startswith("****") or s.startswith("===="):
            return True
        return False

    @staticmethod
    def _is_block_start(line: str) -> bool:
        s = line.strip().lower()
        return s.startswith("url:")

    def _iter_cred_blocks(self, lines):
        """Agrupa linhas em blocos URL / Username / Password / Application."""
        n = len(lines)
        i = 0
        while i < n:
            if self.should_stop():
                return
            line = lines[i]
            if not self._is_block_start(line):
                i += 1
                continue

            start = i + 1  # 1-based
            chunk = [line.rstrip("\r\n")]
            i += 1
            while i < n:
                nxt = lines[i]
                if self._is_block_start(nxt):
                    break
                if self._is_block_separator(nxt) and chunk:
                    # separador fecha o bloco (não inclui a linha ===)
                    break
                chunk.append(nxt.rstrip("\r\n"))
                i += 1
                # limita tamanho de bloco estranho
                if len(chunk) > 30:
                    break

            # consome separadores seguintes
            while i < n and self._is_block_separator(lines[i]) and not self._is_block_start(lines[i]):
                i += 1

            fields = self._extract_cred_fields(chunk)
            text = "\n".join(chunk).strip()
            if not text:
                continue
            summary = self._format_cred_summary(fields, text)
            yield {
                "start": start,
                "text": text,
                "url": fields.get("url", ""),
                "username": fields.get("username", ""),
                "password": fields.get("password", ""),
                "summary": summary,
            }

    @staticmethod
    def _extract_cred_fields(chunk_lines):
        fields = {"url": "", "username": "", "password": "", "application": ""}
        for line in chunk_lines:
            raw = line.strip()
            low = raw.lower()
            if low.startswith("url:"):
                fields["url"] = raw.split(":", 1)[1].strip()
            elif low.startswith("username:") or low.startswith("user:"):
                fields["username"] = raw.split(":", 1)[1].strip()
            elif low.startswith("password:") or low.startswith("pass:"):
                fields["password"] = raw.split(":", 1)[1].strip()
            elif low.startswith("application:") or low.startswith("app:"):
                fields["application"] = raw.split(":", 1)[1].strip()
        return fields

    @staticmethod
    def _format_cred_summary(fields, fallback=""):
        url = fields.get("url") or ""
        user = fields.get("username") or ""
        pwd = fields.get("password") or ""
        if url or user or pwd:
            return f"{url}  |  {user}  |  {pwd}"
        return (fallback.splitlines()[0] if fallback else "")[:200]

    @staticmethod
    def _parse_inline_cred(line: str):
        """Tenta url:user:pass ou url | user | pass em uma linha."""
        fields = {"url": "", "username": "", "password": ""}
        s = line.strip()
        # url:user:pass (comum em dumps)
        if "://" in s and s.count(":") >= 2:
            # http(s)://host/...:user:pass
            m = re.match(
                r"^(https?://[^\s:]+(?::\d+)?(?:/[^\s:]*)?):([^:\s]+):(.+)$",
                s,
            )
            if m:
                fields["url"], fields["username"], fields["password"] = m.groups()
                return fields
        if "|" in s:
            parts = [p.strip() for p in s.split("|")]
            if len(parts) >= 3 and "://" in parts[0]:
                fields["url"], fields["username"], fields["password"] = parts[0], parts[1], parts[2]
        return fields


class QuickOpen(tk.Toplevel):
    """Paleta rápida estilo Cursor (Ctrl+P)."""

    def __init__(self, master, file_list, on_open):
        super().__init__(master)
        self.on_open = on_open
        self.all_files = file_list
        self.filtered = list(file_list)

        self.title("Quick Open")
        self.configure(bg=C["bg"])
        self.geometry("620x400")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - 620) // 2
        y = master.winfo_rooty() + 80
        self.geometry(f"+{max(x, 40)}+{max(y, 40)}")

        tk.Frame(self, bg=C["accent"], height=2).pack(fill="x")

        tk.Label(
            self, text="Abrir arquivo  ·  digite para filtrar",
            bg=C["bg"], fg=C["text_dim"], font=("Segoe UI", 9),
            anchor="w", padx=16, pady=(12, 6),
        ).pack(fill="x")

        self.query = tk.StringVar()
        entry = tk.Entry(
            self, textvariable=self.query,
            bg=C["input"], fg=C["text"], insertbackground=C["accent"],
            relief="flat", font=("Cascadia Mono", 12),
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"],
        )
        entry.pack(fill="x", padx=16, pady=(0, 10), ipady=9)
        entry.focus_set()
        entry.bind("<KeyRelease>", self._filter)
        entry.bind("<Down>", lambda e: self._move(1))
        entry.bind("<Up>", lambda e: self._move(-1))
        entry.bind("<Return>", lambda e: self._confirm())
        entry.bind("<Escape>", lambda e: self.destroy())

        frame = tk.Frame(self, bg=C["surface"])
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.listbox = tk.Listbox(
            frame, bg=C["surface"], fg=C["text"],
            selectbackground=C["accent"], selectforeground=C["white"],
            activestyle="none", relief="flat", font=("Cascadia Mono", 10),
            highlightthickness=0, borderwidth=0,
        )
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.listbox.bind("<Double-Button-1>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())
        self._populate(self.filtered[:250])

    def _filter(self, _=None):
        q = self.query.get().strip()
        if not q:
            self.filtered = list(self.all_files)
        else:
            scored = [(FuzzyMatch.score(q, f), f) for f in self.all_files]
            scored = [(s, f) for s, f in scored if s > 0]
            scored.sort(key=lambda x: -x[0])
            self.filtered = [f for _, f in scored]
        self._populate(self.filtered[:250])

    def _populate(self, items):
        self.listbox.delete(0, "end")
        for f in items:
            self.listbox.insert("end", f)
        if items:
            self.listbox.selection_set(0)
            self.listbox.activate(0)

    def _move(self, delta):
        if not self.listbox.size():
            return "break"
        cur = self.listbox.curselection()
        idx = cur[0] if cur else 0
        idx = max(0, min(self.listbox.size() - 1, idx + delta))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self.listbox.see(idx)
        return "break"

    def _confirm(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        path = self.listbox.get(sel[0])
        self.destroy()
        self.on_open(path)


class ForSearchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ForSearch")
        self.configure(bg=C["bg"])
        self.geometry("1060x740")
        self.minsize(880, 600)

        # pasta db ao lado do app, se existir
        default_dir = Path(__file__).resolve().parent / "db"
        if not default_dir.is_dir():
            default_dir = Path(__file__).resolve().parent

        self.directory = tk.StringVar(value=str(default_dir))
        self.query = tk.StringVar()
        self.exts_var = tk.StringVar(value=", ".join(DEFAULT_EXTS))
        # padrões seguros: contém (não case / não palavra / não regex)
        self.case_sensitive = tk.BooleanVar(value=False)
        self.whole_word = tk.BooleanVar(value=False)
        self.regex_mode = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Pronto  ·  Enter busca  ·  Ctrl+P abre arquivo")
        self.progress_val = tk.DoubleVar(value=0)
        self.files_ready = tk.StringVar(value="")

        self._stop_flag = False
        self._searching = False
        self._hits = []
        self._file_index = []
        self._result_map = {}
        self._shimmers = []

        self._setup_fonts()
        self._setup_style()
        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._refresh_index)

    def _on_close(self):
        for s in self._shimmers:
            try:
                s.stop()
            except Exception:
                pass
        self.destroy()

    def _setup_fonts(self):
        from tkinter import font as tkfont
        avail = {f.lower(): f for f in tkfont.families()}

        def pick(*names, size=10, weight=""):
            for n in names:
                key = n.lower()
                if key in avail:
                    fam = avail[key]
                    return (fam, size, weight) if weight else (fam, size)
            return ("Segoe UI", size, weight) if weight else ("Segoe UI", size)

        self.font_ui = pick("Segoe UI Variable", "Segoe UI", size=10)
        self.font_ui_sm = pick("Segoe UI Variable", "Segoe UI", size=9)
        self.font_label = pick("Segoe UI Variable", "Segoe UI", size=8, weight="bold")
        self.font_title = pick(
            "Bahnschrift", "Segoe UI Semibold", "Segoe UI Variable Display",
            "Montserrat", "Segoe UI", size=26, weight="bold",
        )
        self.font_brand = pick(
            "Bahnschrift Light", "Bahnschrift", "Segoe UI Light",
            "Segoe UI", size=26,
        )
        self.font_mono = pick("Cascadia Mono", "Consolas", "Courier New", size=11)
        self.font_mono_sm = pick("Cascadia Mono", "Consolas", "Courier New", size=9)

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=C["surface2"],
            background=C["accent"],
            bordercolor=C["border"],
            lightcolor=C["accent"],
            darkcolor=C["accent"],
            thickness=4,
        )
        style.configure(
            "Results.Treeview",
            background=C["surface"],
            foreground=C["text"],
            fieldbackground=C["surface"],
            borderwidth=0,
            rowheight=28,
            font=self.font_mono_sm,
        )
        style.configure(
            "Results.Treeview.Heading",
            background=C["surface2"],
            foreground=C["text_dim"],
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Results.Treeview",
            background=[("selected", C["accent"])],
            foreground=[("selected", C["white"])],
        )
        style.map(
            "Results.Treeview.Heading",
            background=[("active", C["elevated"])],
        )

    def _entry(self, parent, var, mono=True, **kw):
        return tk.Entry(
            parent,
            textvariable=var,
            bg=C["input"],
            fg=C["text"],
            insertbackground=C["accent"],
            relief="flat",
            font=self.font_mono if mono else self.font_ui,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"],
            **kw,
        )

    def _btn(self, parent, text, cmd, primary=False, **kw):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=C["accent"] if primary else C["elevated"],
            fg=C["white"] if primary else C["text"],
            activebackground=C["accent_hover"] if primary else C["border"],
            activeforeground=C["white"],
            relief="flat",
            font=("Segoe UI Semibold", 10) if primary else self.font_ui_sm,
            cursor="hand2",
            padx=14,
            pady=8,
            bd=0,
            **kw,
        )

    def _label(self, parent, text):
        return tk.Label(
            parent, text=text.upper(),
            bg=parent.cget("bg"), fg=C["text_faint"],
            font=self.font_label, anchor="w",
        )

    def _build_ui(self):
        # topo shimmer fino
        top_shine = tk.Canvas(self, height=3, bg=C["bg"], highlightthickness=0, bd=0)
        top_shine.pack(fill="x")
        self._top_shine = top_shine
        self._top_phase = 0.0
        self._animate_top_bar()

        # header
        header = tk.Frame(self, bg=C["bg"])
        header.pack(fill="x", padx=28, pady=(18, 6))

        brand = tk.Frame(header, bg=C["bg"])
        brand.pack(side="left")
        tk.Label(
            brand, text="For", bg=C["bg"], fg=C["accent_hover"],
            font=self.font_title,
        ).pack(side="left")
        tk.Label(
            brand, text="Search", bg=C["bg"], fg=C["text"],
            font=self.font_brand,
        ).pack(side="left")
        tk.Label(
            header,
            text="string · url · user · pass · jsonl",
            bg=C["bg"], fg=C["text_faint"], font=self.font_ui_sm,
        ).pack(side="left", padx=(14, 0), pady=(10, 0))

        self.files_badge = tk.Label(
            header, textvariable=self.files_ready,
            bg=C["accent_soft"], fg=C["accent_hover"],
            font=("Segoe UI", 8, "bold"), padx=12, pady=5,
        )
        self.files_badge.pack(side="right")

        # search card com shimmer
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.pack(fill="x", padx=28, pady=(10, 6))

        card = ShimmerBorder(wrap, pad=2)
        self._shimmers.append(card)
        card.pack(fill="x")
        inner = tk.Frame(card.inner, bg=C["surface"])
        inner.pack(fill="x", padx=18, pady=16)

        # query
        self._label(inner, "Buscar").pack(anchor="w")
        q_row = tk.Frame(inner, bg=C["surface"])
        q_row.pack(fill="x", pady=(4, 14))

        self.query_entry = self._entry(q_row, self.query)
        self.query_entry.pack(side="left", fill="x", expand=True, ipady=10)
        self.query_entry.focus_set()

        self.search_btn = self._btn(q_row, "Buscar", self.start_search, primary=True)
        self.search_btn.pack(side="left", padx=(10, 0))

        self.stop_btn = self._btn(q_row, "Parar", self.stop_search)
        self.stop_btn.configure(state="disabled", fg=C["text_faint"])
        self.stop_btn.pack(side="left", padx=(6, 0))

        # directory
        self._label(inner, "Diretório").pack(anchor="w")
        d_row = tk.Frame(inner, bg=C["surface"])
        d_row.pack(fill="x", pady=(4, 12))

        self.dir_entry = self._entry(d_row, self.directory)
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.dir_entry.bind("<FocusOut>", lambda e: self._refresh_index())

        self._btn(d_row, "Pasta…", self.pick_directory).pack(side="left", padx=(8, 0))
        self._btn(d_row, "Ctrl+P", self.open_quick_open).pack(side="left", padx=(6, 0))

        # options row
        opt = tk.Frame(inner, bg=C["surface"])
        opt.pack(fill="x")

        for text, var in [
            ("Maiúsculas", self.case_sensitive),
            ("Palavra inteira", self.whole_word),
            ("Regex", self.regex_mode),
        ]:
            tk.Checkbutton(
                opt, text=text, variable=var,
                bg=C["surface"], fg=C["text_dim"],
                selectcolor=C["input"],
                activebackground=C["surface"],
                activeforeground=C["text"],
                font=self.font_ui_sm,
                highlightthickness=0,
                bd=0,
            ).pack(side="left", padx=(0, 16))

        # presets de extensão
        presets = tk.Frame(inner, bg=C["surface"])
        presets.pack(fill="x", pady=(12, 0))
        self._label(presets, "Tipo de arquivo").pack(anchor="w")

        chips = tk.Frame(presets, bg=C["surface"])
        chips.pack(fill="x", pady=(6, 6))

        for label, value in [
            ("TXT (dumps)", ".txt"),
            ("JSONL", ".jsonl"),
            ("JSON", ".json,.jsonl"),
            ("CSV", ".csv"),
            ("SQL", ".sql"),
            ("Logs", ".log,.txt"),
            ("Tudo", ",".join(DEFAULT_EXTS)),
        ]:
            self._chip(chips, label, value)

        ext_row = tk.Frame(presets, bg=C["surface"])
        ext_row.pack(fill="x")
        tk.Label(
            ext_row, text="Extensões",
            bg=C["surface"], fg=C["text_faint"], font=self.font_ui_sm,
        ).pack(side="left", padx=(0, 8))
        self.ext_entry = self._entry(ext_row, self.exts_var, mono=True)
        self.ext_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.ext_entry.bind("<FocusOut>", lambda e: self._refresh_index())

        # progress
        prog = tk.Frame(self, bg=C["bg"])
        prog.pack(fill="x", padx=28, pady=(6, 0))
        self.progress = ttk.Progressbar(
            prog, variable=self.progress_val, maximum=100,
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x")

        # results header
        res_head = tk.Frame(self, bg=C["bg"])
        res_head.pack(fill="x", padx=28, pady=(14, 6))
        tk.Label(
            res_head, text="RESULTADOS",
            bg=C["bg"], fg=C["text_faint"], font=self.font_label,
        ).pack(side="left")
        self.count_label = tk.Label(
            res_head, text="0",
            bg=C["bg"], fg=C["text_dim"], font=self.font_ui_sm,
        )
        self.count_label.pack(side="left", padx=10)

        self._btn(res_head, "Exportar", self.export_results).pack(side="right")
        self._btn(res_head, "Abrir arquivo", self.open_selected, primary=True).pack(
            side="right", padx=6
        )
        self._btn(res_head, "No Explorer", self.reveal_selected).pack(side="right")

        # results shimmer
        res_wrap = tk.Frame(self, bg=C["bg"])
        res_wrap.pack(fill="both", expand=True, padx=28, pady=(0, 8))
        res_card = ShimmerBorder(res_wrap, pad=2)
        self._shimmers.append(res_card)
        res_card.pack(fill="both", expand=True)
        list_wrap = res_card.inner

        cols = ("file", "line", "content")
        self.tree = ttk.Treeview(
            list_wrap, columns=cols, show="headings",
            style="Results.Treeview", selectmode="browse",
        )
        self.tree.heading("file", text="ARQUIVO", anchor="w")
        self.tree.heading("line", text="LINHA", anchor="center")
        self.tree.heading("content", text="CONTEÚDO", anchor="w")
        self.tree.column("file", width=220, minwidth=120, stretch=False)
        self.tree.column("line", width=70, minwidth=50, stretch=False, anchor="center")
        self.tree.column("content", width=600, minwidth=200, stretch=True)

        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree.tag_configure("odd", background=C["row"])
        self.tree.tag_configure("even", background=C["row_alt"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_selected())
        self.tree.bind("<Return>", lambda e: self.open_selected())

        # preview
        prev = tk.Frame(
            self, bg=C["surface2"],
            highlightbackground=C["accent_deep"], highlightthickness=1,
        )
        prev.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(
            prev, text="PREVIEW",
            bg=C["surface2"], fg=C["accent_hover"], font=self.font_label,
        ).pack(anchor="w", padx=12, pady=(8, 0))
        self.preview = tk.Text(
            prev, height=6, bg=C["surface2"], fg=C["text"],
            relief="flat", font=self.font_mono_sm, wrap="word",
            insertbackground=C["accent"], highlightthickness=0,
            state="disabled", padx=4, pady=4,
        )
        self.preview.pack(fill="x", padx=8, pady=(2, 10))

        # status
        status = tk.Frame(self, bg=C["surface2"])
        status.pack(fill="x", side="bottom")
        tk.Frame(status, bg=C["accent"], width=3).pack(side="left", fill="y")
        tk.Label(
            status, textvariable=self.status,
            bg=C["surface2"], fg=C["text_dim"], font=self.font_ui_sm,
            anchor="w", padx=14, pady=8,
        ).pack(fill="x")

    def _animate_top_bar(self):
        if not self.winfo_exists():
            return
        c = self._top_shine
        c.delete("all")
        w = max(c.winfo_width(), 200)
        colors = C["shimmer"]
        segs = 40
        for i in range(segs):
            t = (i / segs + self._top_phase) % 1.0
            idx = t * (len(colors) - 1)
            a = int(idx)
            frac = idx - a
            # lerp simples via ShimmerBorder helper
            col = colors[a]
            if a + 1 < len(colors):
                # reuse lerp from first shimmer if available
                if self._shimmers:
                    col = self._shimmers[0]._lerp_color(colors[a], colors[a + 1], frac)
            x0 = w * i / segs
            x1 = w * (i + 1) / segs + 1
            c.create_rectangle(x0, 0, x1, 3, fill=col, outline="")
        self._top_phase = (self._top_phase + 0.018) % 1.0
        self.after(36, self._animate_top_bar)

    def _chip(self, parent, label, value):
        def apply():
            self.exts_var.set(value)
            self._refresh_index()

        btn = tk.Button(
            parent, text=label, command=apply,
            bg=C["elevated"], fg=C["text_dim"],
            activebackground=C["accent_soft"],
            activeforeground=C["accent"],
            relief="flat", font=("Segoe UI", 8),
            cursor="hand2", padx=10, pady=4, bd=0,
        )
        btn.pack(side="left", padx=(0, 6))

    def _bind_keys(self):
        self.bind("<Control-p>", lambda e: self.open_quick_open())
        self.bind("<Control-P>", lambda e: self.open_quick_open())
        self.bind("<Control-f>", lambda e: self.query_entry.focus_set())
        self.bind("<Control-o>", lambda e: self.pick_directory())
        self.bind("<Escape>", lambda e: self.stop_search())
        self.query_entry.bind("<Return>", lambda e: self.start_search())
        self.dir_entry.bind("<Return>", lambda e: self.start_search())

    def _parse_exts(self):
        raw = self.exts_var.get().replace(";", ",")
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        out = []
        for p in parts:
            out.append(p if p.startswith(".") else f".{p}")
        return out or list(DEFAULT_EXTS)

    def pick_directory(self):
        path = filedialog.askdirectory(
            title="Escolher pasta para pesquisar",
            initialdir=self.directory.get() or str(Path.cwd()),
        )
        if path:
            self.directory.set(path)
            self._refresh_index()

    def _refresh_index(self):
        threading.Thread(target=self._index_files, daemon=True).start()

    def _index_files(self):
        root = Path(self.directory.get())
        if not root.is_dir():
            self.after(0, lambda: self.files_ready.set("Pasta inválida"))
            return
        exts = set(self._parse_exts())
        files = []
        txt_count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}
            ]
            for name in filenames:
                ext = Path(name).suffix.lower()
                if ext in exts:
                    try:
                        rel = str(Path(dirpath, name).relative_to(root))
                    except ValueError:
                        rel = str(Path(dirpath, name))
                    files.append(rel)
                    if ext == ".txt":
                        txt_count += 1
        self._file_index = files
        n = len(files)

        def ui():
            self.files_ready.set(f"{n} arquivos  ·  {txt_count} .txt")
            self.status.set(
                f"Indexado: {n} arquivos em {root}  ·  Ctrl+P para abrir"
            )

        self.after(0, ui)

    def open_quick_open(self):
        if not self._file_index:
            root = Path(self.directory.get())
            if root.is_dir():
                self.status.set("Indexando…")
                self.update_idletasks()
                self._index_files()
        if not self._file_index:
            messagebox.showinfo(
                "Quick Open",
                "Nenhum arquivo nas extensões atuais.\n"
                "Clique em TXT (dumps) ou escolha a pasta certa.",
            )
            return

        def on_open(rel):
            full = Path(self.directory.get()) / rel
            self.open_file(str(full))

        QuickOpen(self, self._file_index, on_open)

    def start_search(self):
        if self._searching:
            return
        q = self.query.get().strip()
        if not q:
            messagebox.showwarning("Busca", "Digite uma palavra, URL ou string.")
            return
        root = Path(self.directory.get())
        if not root.is_dir():
            messagebox.showerror("Diretório", "Pasta inválida.")
            return

        # avisos úteis
        if self.regex_mode.get():
            try:
                re.compile(q)
            except re.error as e:
                messagebox.showerror("Regex", f"Padrão inválido:\n{e}")
                return

        self._stop_flag = False
        self._searching = True
        self._hits = []
        self._result_map = {}
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.progress_val.set(0)
        self.count_label.config(text="0")
        self.search_btn.config(state="disabled")
        self.stop_btn.config(state="normal", fg=C["text"])
        self.status.set(f"Buscando “{q}”…")
        self._set_preview("")

        threading.Thread(target=self._run_search, args=(q, str(root)), daemon=True).start()

    def stop_search(self):
        if self._searching:
            self._stop_flag = True
            self.status.set("Parando…")

    def _run_search(self, query, root):
        def on_progress(cur, total, path):
            pct = (cur / max(total, 1)) * 100
            name = Path(path).name
            self.after(0, lambda: (
                self.progress_val.set(pct),
                self.status.set(f"[{cur}/{total}]  {name}"),
            ))

        def on_hit(hit):
            self.after(0, lambda h=hit: self._append_hit(h))

        engine = SearchEngine(
            root_dir=root,
            query=query,
            extensions=self._parse_exts(),
            case_sensitive=self.case_sensitive.get(),
            whole_word=self.whole_word.get(),
            regex_mode=self.regex_mode.get(),
            on_progress=on_progress,
            on_hit=on_hit,
            should_stop=lambda: self._stop_flag,
        )
        try:
            engine.run()
        except ValueError as e:
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))

        def finish():
            self._searching = False
            self.search_btn.config(state="normal")
            self.stop_btn.config(state="disabled", fg=C["text_faint"])
            self.progress_val.set(100 if engine.files_total else 0)
            n = len(self._hits)
            self.count_label.config(text=str(n))
            stopped = " (parado)" if self._stop_flag else ""

            if engine.files_total == 0:
                self.status.set(
                    "Nenhum arquivo nas extensões selecionadas. "
                    "Clique em TXT (dumps) e tente de novo."
                )
                messagebox.showinfo(
                    "Sem arquivos",
                    "A pasta não tem arquivos com as extensões atuais.\n\n"
                    f"Pasta: {root}\n"
                    f"Extensões: {', '.join(self._parse_exts()[:8])}…\n\n"
                    "Use o botão TXT (dumps) e confira se a pasta está certa.",
                )
            elif n == 0:
                self.status.set(
                    f"Concluído{stopped}  ·  0 resultados em "
                    f"{engine.files_scanned} arquivo(s)  ·  "
                    f"a string “{query}” não aparece nos arquivos"
                )
            else:
                self.status.set(
                    f"Concluído{stopped}  ·  {n} resultado(s)  ·  "
                    f"{engine.files_scanned} arquivo(s)  ·  "
                    f"{engine.errors} erro(s)"
                )
            if not self._file_index:
                self._refresh_index()

        self.after(0, finish)

    def _append_hit(self, hit):
        self._hits.append(hit)
        idx = len(self._hits) - 1
        tag = "even" if idx % 2 else "odd"
        # lista: resumo compacto; preview: bloco inteiro URL/User/Pass
        summary = hit.get("summary") or hit["text"].replace("\n", "  ·  ")[:200]
        iid = self.tree.insert(
            "", "end",
            values=(hit["rel"], hit["line"], summary),
            tags=(tag,),
        )
        self._result_map[iid] = hit
        self.count_label.config(text=str(len(self._hits)))

    def _on_select(self, _=None):
        hit = self._current_hit()
        if hit:
            block = hit.get("text") or ""
            header = f"{hit['path']}:{hit['line']}\n" + ("─" * 48) + "\n"
            self._set_preview(header + block)

    def _set_preview(self, text):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")

    def _current_hit(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._result_map.get(sel[0])

    def open_selected(self):
        hit = self._current_hit()
        if not hit:
            messagebox.showinfo("Abrir", "Selecione um resultado na lista.")
            return
        self.open_file(hit["path"], hit["line"])

    def reveal_selected(self):
        hit = self._current_hit()
        if not hit:
            messagebox.showinfo("Explorer", "Selecione um resultado.")
            return
        path = Path(hit["path"])
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])

    def open_file(self, path, line=None):
        path = str(Path(path).resolve())
        if not os.path.isfile(path):
            messagebox.showerror("Arquivo", f"Não encontrado:\n{path}")
            return
        for cmd in (
            self._cursor_cmd(path, line),
            self._code_cmd(path, line),
            self._npp_cmd(path, line),
        ):
            if cmd and self._try_spawn(cmd):
                self.status.set(f"Aberto: {Path(path).name}" + (f":{line}" if line else ""))
                return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            self.status.set(f"Aberto: {path}")
        except OSError as e:
            messagebox.showerror("Abrir", str(e))

    def _cursor_cmd(self, path, line):
        exe = which("cursor") or self._find_win([
            r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe",
            r"%LOCALAPPDATA%\Programs\Cursor\Cursor.exe",
        ])
        if not exe:
            return None
        return [exe, "-g", f"{path}:{line}"] if line else [exe, path]

    def _code_cmd(self, path, line):
        exe = which("code")
        if not exe:
            return None
        return [exe, "-g", f"{path}:{line}"] if line else [exe, path]

    def _npp_cmd(self, path, line):
        exe = self._find_win([
            r"%ProgramFiles%\Notepad++\notepad++.exe",
            r"%ProgramFiles(x86)%\Notepad++\notepad++.exe",
        ])
        if not exe:
            return None
        return [exe, f"-n{line}", path] if line else [exe, path]

    def _find_win(self, patterns):
        for p in patterns:
            expanded = os.path.expandvars(p)
            if os.path.isfile(expanded):
                return expanded
        return None

    def _try_spawn(self, cmd):
        try:
            subprocess.Popen(cmd, shell=False)
            return True
        except OSError:
            return False

    def export_results(self):
        if not self._hits:
            messagebox.showinfo("Exportar", "Nenhum resultado.")
            return
        q = re.sub(r'[<>:"/\\|?*]', "_", self.query.get().strip())[:50] or "resultado"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            title="Exportar resultados",
            defaultextension=".txt",
            initialfile=f"forsearch_{q}_{stamp}.txt",
            filetypes=[("Texto", "*.txt"), ("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# query: {self.query.get()}\n")
                f.write(f"# dir: {self.directory.get()}\n")
                f.write(f"# hits: {len(self._hits)}\n\n")
                if path.lower().endswith(".csv"):
                    f.write("file,line,url,username,password,block\n")
                    for h in self._hits:
                        block = h["text"].replace('"', '""').replace("\n", " | ")
                        f.write(
                            f'"{h["path"]}",{h["line"]},'
                            f'"{h.get("url", "")}","{h.get("username", "")}",'
                            f'"{h.get("password", "")}","{block}"\n'
                        )
                else:
                    for h in self._hits:
                        f.write(f"{'=' * 48}\n")
                        f.write(f"# {h['path']}:{h['line']}\n")
                        f.write(h["text"].rstrip() + "\n\n")
            self.status.set(f"Exportado: {path}")
            messagebox.showinfo("Exportar", f"Salvo em:\n{path}")
        except OSError as e:
            messagebox.showerror("Exportar", str(e))


def main():
    app = ForSearchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
