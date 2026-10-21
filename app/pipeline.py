from dataclasses import dataclass

from PIL import Image

from .classify import classify, detect_language, detect_role, is_coding_text
from .questions import Detection, detect
from .textclean import clean_text

CODE_TASK_CHARS = 1500
STRONG = ("question", "coding_task")


@dataclass
class Analysis:
    raw: str
    cleaned: str
    detection: Detection
    confidence: float
    variant: str
    image: Image.Image
    processed: Image.Image


def detect_task(cleaned):
    if is_coding_text(cleaned):
        return Detection(cleaned[-CODE_TASK_CHARS:], "", "coding_task")
    return detect(cleaned)


def analyze(images, ocr, max_variants=3):
    results = []
    for img in images:
        r = ocr.best(img, max_variants)
        cleaned = clean_text(r.text)
        results.append(Analysis(r.text, cleaned, detect_task(cleaned), r.confidence, r.variant, img, r.image))
    strong = [a for a in results if a.detection.method in STRONG]
    if strong:
        return strong[-1]
    found = [a for a in results if a.detection.question]
    return max(found or results, key=lambda a: a.confidence)


def format_report(name, a):
    q = a.detection.question or ""
    lines = [
        f"=== {name} ===",
        f"OCR confidence: {a.confidence:.1f}%  (best version: {a.variant})",
        "--- raw OCR text ---",
        a.raw.strip() or "(empty)",
        "--- cleaned text ---",
        a.cleaned or "(empty)",
        f"--- detected question [{a.detection.method}] ---",
        q or "(none)",
        f"--- type: {classify(q)} | language: {detect_language(q) or '-'} | "
        f"interviewer on screen: {detect_role(a.raw) or '-'} ---",
    ]
    if a.detection.context:
        lines += ["--- context ---", a.detection.context]
    return "\n".join(lines)
