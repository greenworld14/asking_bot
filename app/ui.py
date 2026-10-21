import queue
import re
import tkinter as tk
from tkinter import font as tkfont

from .capture import virtual_screen
from .classify import KIND_LABELS, ROLE_LABELS

BG = "#1e1f24"
PANEL = "#2a2c33"
CODE_BG = "#15161a"
FG = "#e6e6e6"
MUTED = "#8b8f9a"
ACCENT = "#4f8cff"
BOLD_RE = re.compile(r"(\*\*.+?\*\*)")
CODE_RE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)


class AnswerWindow:
    def __init__(self, cfg, role="auto", kind="auto"):
        self.jobs = queue.Queue()
        self.on_send = None
        self.code_blocks = []
        self.selected_role = role if role in ROLE_LABELS else "auto"
        self.selected_kind = kind if kind in KIND_LABELS else "auto"
        self.root = tk.Tk()
        self.root.title("Meeting Answers")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", cfg.get("opacity", 0.95))
        width, height = cfg.get("width", 560), cfg.get("height", 700)
        x = max(self.root.winfo_screenwidth() - width - 24, 0)
        y = max(self.root.winfo_screenheight() - height - 72, 0)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(460, 480)

        size = cfg.get("font_size", 11)
        self.body_font = tkfont.Font(family="Segoe UI", size=size)
        self.bold_font = tkfont.Font(family="Segoe UI", size=size, weight="bold")
        self.small_font = tkfont.Font(family="Segoe UI", size=max(size - 2, 8))
        self.code_font = tkfont.Font(family="Consolas", size=max(size - 1, 8))

        self.status = tk.Label(self.root, text="Ready", bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 9))
        self.status.pack(fill="x", padx=10, pady=(8, 4))

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=10, pady=(0, 6))
        self.role_var = self.dropdown(controls, "Interviewer", ROLE_LABELS, self.selected_role, self._sync)
        self.kind_var = self.dropdown(controls, "Type", KIND_LABELS, self.selected_kind, self._sync)

        self.ocr_box = self.labeled_text("Screen text", 4, self.small_font)
        self.q_box = self.labeled_text("Question (edit if needed, Ctrl+Enter sends)", 3, self.body_font)
        self.q_box.bind("<Control-Return>", self._send_shortcut)

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=10, pady=(0, 6))
        self.buttons = {}
        for name in ("Send to AI", "Re-scan", "Use full text", "Region", "Copy", "Copy code"):
            main = name == "Send to AI"
            b = tk.Button(bar, text=name, bg=ACCENT if main else PANEL, fg="white" if main else FG,
                          activebackground=ACCENT, activeforeground="white", relief="flat",
                          padx=8, pady=3, borderwidth=0, font=("Segoe UI", 9))
            b.pack(side="left", padx=(0, 5))
            self.buttons[name] = b
        self.buttons["Copy"].configure(command=self.copy)
        self.buttons["Copy code"].configure(command=self.copy_code)

        tk.Label(self.root, text="Answer", bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 8)).pack(fill="x", padx=10)
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.text = tk.Text(frame, bg=PANEL, fg=FG, font=self.body_font, wrap="word", relief="flat",
                            padx=10, pady=8, borderwidth=0, height=4)
        ys = tk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        xs = tk.Scrollbar(frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.text.tag_configure("bold", font=self.bold_font, foreground="#ffd479")
        self.text.tag_configure("code", font=self.code_font, background=CODE_BG, foreground="#d7e3ff",
                                wrap="none", lmargin1=8, lmargin2=8, spacing1=1, spacing3=1)
        self.text.configure(state="disabled")

        self.root.after(100, self._poll)

    def dropdown(self, parent, title, labels, current, on_change):
        tk.Label(parent, text=title, bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        var = tk.StringVar(value=labels[current])
        menu = tk.OptionMenu(parent, var, *labels.values())
        menu.configure(bg=PANEL, fg=FG, activebackground=ACCENT, activeforeground="white", relief="flat",
                       highlightthickness=0, borderwidth=0, font=("Segoe UI", 9))
        menu["menu"].configure(bg=PANEL, fg=FG, activebackground=ACCENT, activeforeground="white")
        menu.pack(side="left", padx=(0, 12))
        var.trace_add("write", lambda *_: on_change())
        return var

    def _sync(self):
        role_keys = {v: k for k, v in ROLE_LABELS.items()}
        kind_keys = {v: k for k, v in KIND_LABELS.items()}
        self.selected_role = role_keys.get(self.role_var.get(), "auto")
        self.selected_kind = kind_keys.get(self.kind_var.get(), "auto")

    def labeled_text(self, title, height, font):
        tk.Label(self.root, text=title, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 8)).pack(fill="x", padx=10)
        box = tk.Text(self.root, bg=PANEL, fg=FG, font=font, wrap="word", relief="flat", padx=8, pady=6,
                      borderwidth=0, insertbackground=FG, height=height, undo=True)
        box.pack(fill="x", padx=10, pady=(0, 6))
        return box

    def _send_shortcut(self, event):
        if self.on_send:
            self.on_send()
        return "break"

    def post(self, fn, *args):
        self.jobs.put((fn, args))

    def _poll(self):
        try:
            while True:
                fn, args = self.jobs.get_nowait()
                try:
                    fn(*args)
                except Exception as e:
                    self.set_status(f"Error: {e}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def set_status(self, text):
        self.status.configure(text=text)

    def show_error(self, message):
        self.set_status(message)

    @staticmethod
    def _set_box(box, text):
        box.delete("1.0", "end")
        box.insert("1.0", text)

    def set_ocr_text(self, text):
        self._set_box(self.ocr_box, text)

    def get_ocr_text(self):
        return self.ocr_box.get("1.0", "end-1c")

    def set_question(self, text):
        self._set_box(self.q_box, text)

    def get_question(self):
        return self.q_box.get("1.0", "end-1c")

    def _insert_rich(self, text):
        for part in BOLD_RE.split(text):
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                self.text.insert("end", part[2:-2], "bold")
            elif part:
                self.text.insert("end", part)

    def show_answer(self, answer):
        if answer.count("```") % 2:
            answer += "\n```"
        self.code_blocks = []
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        pos = 0
        for m in CODE_RE.finditer(answer):
            self._insert_rich(answer[pos:m.start()])
            code = m.group(1).strip("\n")
            self.code_blocks.append(code)
            self.text.insert("end", code + "\n", "code")
            pos = m.end()
        self._insert_rich(answer[pos:])
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def _to_clipboard(self, content, message):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.set_status(message)

    def copy(self):
        content = self.text.get("1.0", "end").strip()
        if content:
            self._to_clipboard(content, "Answer copied")

    def copy_code(self):
        if not self.code_blocks:
            self.set_status("There is no code in this answer")
            return
        self._to_clipboard("\n\n".join(self.code_blocks), "Code copied")

    def hide(self):
        self.root.withdraw()

    def show(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def pick_region(self, callback):
        vx, vy, vw, vh = virtual_screen()
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.geometry(f"{vw}x{vh}{vx:+d}{vy:+d}")
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.3)
        overlay.configure(bg="black")
        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        state = {"start": None, "rect": None}

        def press(e):
            state["start"] = (e.x_root, e.y_root, e.x, e.y)
            state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=2)

        def drag(e):
            if state["rect"]:
                canvas.coords(state["rect"], state["start"][2], state["start"][3], e.x, e.y)

        def release(e):
            if not state["start"]:
                return
            x1, y1 = state["start"][0], state["start"][1]
            x2, y2 = e.x_root, e.y_root
            overlay.destroy()
            left, top = min(x1, x2), min(y1, y2)
            width, height = abs(x2 - x1), abs(y2 - y1)
            if width > 20 and height > 20:
                callback((left, top, width, height))

        canvas.bind("<ButtonPress-1>", press)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", release)
        overlay.bind("<Escape>", lambda e: overlay.destroy())
        overlay.focus_force()

    def run(self):
        self.root.mainloop()
