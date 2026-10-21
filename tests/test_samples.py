import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from PIL import Image

from app.config import load_config
from app.ocr import OCR
from app.pipeline import analyze, format_report
from make_samples import OUT, SAMPLES, make_all


def norm(text):
    return " ".join((text or "").lower().split())


def run(verbose=True):
    make_all()
    cfg = load_config()
    ocr = OCR(cfg["ocr"])
    failures = []
    for name, sample in SAMPLES.items():
        img = Image.open(OUT / f"{name}.png").convert("RGB")
        a = analyze([img], ocr, cfg["ocr"].get("max_variants", 3))
        ok = norm(a.detection.question) == norm(sample["question"]) and a.detection.method == sample["method"]
        if verbose:
            print(format_report(name, a))
            print(f"--- expected [{sample['method']}] ---")
            print(sample["question"])
            print("PASS" if ok else "FAIL")
            print()
        if not ok:
            failures.append(name)
    return failures


def test_samples():
    assert run(verbose=False) == []


if __name__ == "__main__":
    failed = run()
    print(f"{len(SAMPLES) - len(failed)}/{len(SAMPLES)} passed")
    sys.exit(1 if failed else 0)
