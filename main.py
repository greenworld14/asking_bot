import ctypes
import io
import sys
import threading
import time

from PIL import Image

from app.audio import AudioListener, list_devices
from app.capture import clear_saved_region, grab_all, load_region, monitors, save_region
from app.classify import KIND_LABELS, ROLE_LABELS, classify, detect_language, detect_role, resolve_role
from app.config import load_config, load_profile, resolve
from app.history import History
from app.llm import LLMError, create_client, split_vision
from app.ocr import OCR, OCRError
from app.pipeline import CODE_TASK_CHARS, analyze, format_report
from app.questions import Detection, detect
from app.ui import AnswerWindow

METHOD_LABELS = {
    "coding_task": "coding task found",
    "question": "question found",
    "last_sentence": "no question mark, using last sentence",
    "last_paragraph": "no sentence, using last line",
    "none": "no text found",
}


def set_dpi_awareness():
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def save_debug(cfg, image, processed=None):
    if not cfg.get("debug", {}).get("save_images", True):
        return
    try:
        image.save(resolve("debug_capture.png"))
        if processed is not None:
            processed.save(resolve("debug_ocr.png"))
    except OSError:
        pass


class Controller:
    def __init__(self):
        self.cfg = load_config()
        self.profile = load_profile(self.cfg)
        self.mode = str(self.cfg.get("mode", "ocr")).lower()
        try:
            self.client = create_client(self.cfg, self.profile)
        except LLMError as e:
            raise SystemExit(str(e))
        try:
            self.ocr = OCR(self.cfg["ocr"])
        except OCRError as e:
            if self.mode != "vision":
                raise SystemExit(str(e))
            self.ocr = None
        self.history = History(self.cfg["history"])
        self.ui = AnswerWindow(
            self.cfg["ui"],
            role=str(self.cfg.get("interviewer", "auto")).lower(),
            kind=str(self.cfg.get("answer_type", "auto")).lower(),
        )
        self.language = self.cfg.get("coding", {}).get("language", "Python")
        self.region = load_region() or self.cfg["capture"].get("region")
        self.context = ""
        self.screen_role = None
        self.busy = threading.Lock()
        self.last_spoken = None
        self.audio = AudioListener(
            self.cfg["audio"],
            on_text=self.on_spoken,
            on_status=lambda t: self.ui.post(self.ui.set_status, t),
        )
        self.ui.on_send = self.send
        b = self.ui.buttons
        b["Send to AI"].configure(command=self.send)
        b["Re-scan"].configure(command=self.start_capture)
        b["Use full text"].configure(command=self.use_full_text)
        b["Region"].configure(command=self.choose_region)

    def bind_hotkeys(self):
        try:
            import keyboard
            keys = self.cfg["hotkeys"]
            keyboard.add_hotkey(keys["capture"], lambda: self.ui.post(self.start_capture))
            keyboard.add_hotkey(keys["region"], lambda: self.ui.post(self.choose_region))
            keyboard.add_hotkey(keys["toggle_audio"], lambda: self.ui.post(self.toggle_audio))
            if keys.get("clear_region"):
                keyboard.add_hotkey(keys["clear_region"], lambda: self.ui.post(self.clear_region))
        except Exception as e:
            self.ui.set_status(f"Hotkeys failed: {e}. Try running as administrator.")

    def choose_region(self):
        self.ui.pick_region(self.set_region)

    def set_region(self, region):
        self.region = region
        save_region(region)
        self.ui.set_status(f"Region saved: {region[2]}x{region[3]} at ({region[0]}, {region[1]})")
        self.ui.root.after(300, self.start_capture)

    def clear_region(self):
        self.region = None
        clear_saved_region()
        self.ui.set_status("Region cleared. Capturing full screen.")

    def toggle_audio(self):
        if self.audio.running:
            self.audio.stop()
            self.ui.set_status("Stopping audio...")
        else:
            self.audio.start()

    def capture_images(self):
        cap = self.cfg["capture"]
        return grab_all(
            self.region,
            cap.get("monitor", "all"),
            [k.lower() for k in cap.get("window_keywords", [])],
            cap.get("frames", 3),
            cap.get("frame_interval", 0.4),
        )

    def start_capture(self):
        if not self.busy.acquire(blocking=False):
            self.ui.set_status("Still working...")
            return
        hide = self.cfg["capture"].get("hide_window_during_capture", True)
        if hide:
            self.ui.hide()
        threading.Thread(target=self.run_screen, args=(hide,), daemon=True).start()

    def run_screen(self, hidden):
        try:
            if hidden:
                time.sleep(0.25)
            try:
                images = self.capture_images()
            finally:
                if hidden:
                    self.ui.post(self.ui.show)
            if not images:
                self.ui.post(self.ui.set_status, "Nothing captured")
                return
            if self.mode == "vision":
                self.run_vision(images[0])
                return
            self.ui.post(self.ui.set_status, "Reading text...")
            ocr_cfg = self.cfg["ocr"]
            variants = ocr_cfg.get("max_variants", 3) if self.region else ocr_cfg.get("full_screen_variants", 1)
            analysis = analyze(images, self.ocr, variants)
            save_debug(self.cfg, analysis.image, analysis.processed)
            self.screen_role = detect_role(analysis.raw)
            d = self.adjust_detection(analysis)
            self.context = d.context
            self.ui.post(self.show_analysis, analysis, d)
            if self.cfg.get("auto_send", True):
                if d.question:
                    self.answer(d.question, d.context, "screen")
                else:
                    self.ui.post(self.ui.set_status, "No text found in the region. Press F9 to select again.")
        except OCRError as e:
            self.ui.post(self.ui.show_error, str(e))
        except Exception as e:
            self.ui.post(self.ui.show_error, f"Error: {e}")
        finally:
            self.busy.release()

    def adjust_detection(self, analysis):
        d = analysis.detection
        kind = self.ui.selected_kind
        if kind == "coding" and d.method != "coding_task" and analysis.cleaned:
            return Detection(analysis.cleaned[-CODE_TASK_CHARS:], "", "coding_task")
        if kind not in ("auto", "coding") and d.method == "coding_task":
            return detect(analysis.cleaned)
        return d

    def show_analysis(self, analysis, d):
        self.ui.set_ocr_text(analysis.cleaned)
        self.ui.set_question(d.question or "")
        hint = "" if self.cfg.get("auto_send", True) else " | check and press Send to AI"
        self.ui.set_status(f"OCR {analysis.confidence:.0f}% | {METHOD_LABELS[d.method]}{hint}")

    def run_vision(self, image):
        save_debug(self.cfg, image)
        self.ui.post(self.ui.set_status, "AI is reading the screenshot...")
        img = image.copy()
        img.thumbnail((1568, 1568))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        try:
            text = self.client.ask_image(buf.getvalue(), self.language)
        except LLMError as e:
            self.ui.post(self.ui.show_error, str(e))
            return
        question, answer = split_vision(text)
        self.ui.post(self.ui.set_question, question or "")
        self.ui.post(self.ui.show_answer, answer)
        self.ui.post(self.ui.set_status, "Done (vision)")
        self.history.add(question or "", answer, "vision")

    def send(self):
        question = self.ui.get_question().strip()
        if not question:
            self.ui.set_status("The question box is empty")
            return
        if not self.busy.acquire(blocking=False):
            self.ui.set_status("Still working...")
            return
        threading.Thread(target=self.run_answer, args=(question, self.context, "screen"), daemon=True).start()

    def use_full_text(self):
        text = self.ui.get_ocr_text().strip()
        if not text:
            self.ui.set_status("No screen text yet")
            return
        self.context = ""
        self.ui.set_question(text[-CODE_TASK_CHARS:])
        self.ui.set_status("Full text is in the question box. Press Send to AI.")

    def on_spoken(self, text):
        d = detect(text)
        if d.method != "question" or d.question == self.last_spoken:
            return
        if not self.busy.acquire(blocking=False):
            return
        self.last_spoken = d.question
        self.ui.post(self.ui.set_ocr_text, text)
        self.ui.post(self.ui.set_question, d.question)
        threading.Thread(target=self.run_answer, args=(d.question, d.context, "audio"), daemon=True).start()

    def run_answer(self, question, context, source):
        try:
            self.answer(question, context, source)
        except Exception as e:
            self.ui.post(self.ui.show_error, f"Error: {e}")
        finally:
            self.busy.release()

    def answer(self, question, context, source):
        selected = self.ui.selected_kind
        kind = selected if selected != "auto" else classify(question)
        role = resolve_role(self.ui.selected_role, kind, self.screen_role if source == "screen" else None)
        language = detect_language(question) or self.language
        label = f"{KIND_LABELS[kind]} for {ROLE_LABELS[role]}"
        if kind == "coding":
            label += f" in {language}"
        self.ui.post(self.ui.set_status, f"Thinking... ({label})")
        try:
            answer = self.client.ask(question, context, kind, role, language)
        except LLMError as e:
            self.ui.post(self.ui.show_error, str(e))
            return
        if not answer:
            self.ui.post(self.ui.show_error, "The model returned an empty answer")
            return
        self.ui.post(self.ui.show_answer, answer)
        self.ui.post(self.ui.set_status, f"Done | {label}")
        self.history.add(question, answer, source, kind, role)

    def run(self):
        self.bind_hotkeys()
        keys = self.cfg["hotkeys"]
        where = "saved region" if self.region else "full screen"
        self.ui.set_status(
            f"{keys['capture'].upper()} capture ({where}) | {keys['region'].upper()} region | "
            f"{keys['toggle_audio'].upper()} audio | mode: {self.mode}"
        )
        if self.cfg["audio"].get("enabled"):
            self.audio.start()
        self.ui.run()


def run_test(paths):
    cfg = load_config()
    try:
        ocr = OCR(cfg["ocr"])
    except OCRError as e:
        raise SystemExit(str(e))
    variants = cfg["ocr"].get("max_variants", 3)
    if paths:
        for path in paths:
            try:
                img = Image.open(path).convert("RGB")
            except OSError as e:
                print(f"Cannot open {path}: {e}")
                continue
            print(format_report(path, analyze([img], ocr, variants)))
            print()
        return
    region = load_region() or cfg["capture"].get("region")
    for i, m in enumerate(monitors()):
        label = "all monitors" if i == 0 else f"monitor {i}"
        print(f"{label}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})")
    print(f"region: {region or 'none (full screen)'}")
    images = grab_all(region, cfg["capture"].get("monitor", "all"), [], 1, 0)
    if not images:
        raise SystemExit("Nothing captured. Is the region inside the screen?")
    analysis = analyze(images, ocr, variants if region else cfg["ocr"].get("full_screen_variants", 1))
    save_debug(cfg, analysis.image, analysis.processed)
    print(f"captured image: {analysis.image.width}x{analysis.image.height} (saved to debug_capture.png)")
    print(format_report("screen region" if region else "full screen", analysis))


def main():
    set_dpi_awareness()
    if "--devices" in sys.argv:
        print(list_devices())
        return
    if "--test" in sys.argv:
        run_test(sys.argv[sys.argv.index("--test") + 1:])
        return
    Controller().run()


if __name__ == "__main__":
    main()
