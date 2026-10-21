from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps


class OCRError(Exception):
    pass


@dataclass
class OcrResult:
    text: str
    confidence: float
    variant: str
    image: Image.Image


def upscale(img):
    factor = 3 if img.width < 800 else 2
    factor = min(factor, 5000 / max(img.width, img.height))
    if factor <= 1:
        return img
    return img.resize((int(img.width * factor), int(img.height * factor)), Image.LANCZOS)


def is_dark(gray):
    small = gray.resize((64, 64))
    pixels = list(small.getdata())
    return sum(pixels) / len(pixels) < 110


def otsu_threshold(gray):
    hist = gray.histogram()
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_back = weight_back = 0
    best, threshold = 0.0, 127
    for i, h in enumerate(hist):
        weight_back += h
        if weight_back == 0:
            continue
        weight_fore = total - weight_back
        if weight_fore == 0:
            break
        sum_back += i * h
        mean_back = sum_back / weight_back
        mean_fore = (sum_all - sum_back) / weight_fore
        between = weight_back * weight_fore * (mean_back - mean_fore) ** 2
        if between > best:
            best, threshold = between, i
    return threshold


def variants(img):
    gray = upscale(ImageOps.grayscale(img))
    base = ImageOps.invert(gray) if is_dark(gray) else gray
    base = ImageOps.autocontrast(base.filter(ImageFilter.MedianFilter(3)), cutoff=1)
    threshold = otsu_threshold(base)
    binary = base.filter(ImageFilter.SHARPEN).point(lambda p: 255 if p > threshold else 0)
    bright = gray.filter(ImageFilter.MedianFilter(3)).point(lambda p: 0 if p > 200 else 255)
    return [("contrast", base), ("binary", binary), ("bright-text", bright)]


class OCR:
    def __init__(self, cfg):
        self.engine = cfg["engine"].lower()
        self.lang = cfg.get("lang", "eng")
        self.config = f"--oem {cfg.get('oem', 3)} --psm {cfg.get('psm', 6)}"
        self.reader = None
        if self.engine == "tesseract":
            try:
                import pytesseract
            except ImportError:
                raise OCRError("pytesseract is not installed")
            cmd = cfg.get("tesseract_cmd")
            if cmd:
                pytesseract.pytesseract.tesseract_cmd = cmd
            self.pytesseract = pytesseract
        elif self.engine == "easyocr":
            try:
                import easyocr
            except ImportError:
                raise OCRError("easyocr is not installed (pip install -r requirements-optional.txt)")
            self.easyocr = easyocr
        else:
            raise OCRError(f"Unknown OCR engine: {self.engine}")

    def read_tesseract(self, img):
        data = self.pytesseract.image_to_data(
            img, lang=self.lang, config=self.config, output_type=self.pytesseract.Output.DICT
        )
        lines, order, confs = {}, [], []
        for i, word in enumerate(data["text"]):
            word = word.strip()
            conf = float(data["conf"][i])
            if not word or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if key not in lines:
                lines[key] = []
                order.append(key)
            lines[key].append(word)
            confs.append(conf)
        out, last_par = [], None
        for key in order:
            if last_par is not None and key[:2] != last_par:
                out.append("")
            out.append(" ".join(lines[key]))
            last_par = key[:2]
        return "\n".join(out), (sum(confs) / len(confs) if confs else 0.0)

    def read_easyocr(self, img):
        import numpy as np
        if self.reader is None:
            code = {"eng": "en"}.get(self.lang, self.lang)
            self.reader = self.easyocr.Reader([code], gpu=False)
        results = self.reader.readtext(np.array(img), detail=1, paragraph=False)
        if not results:
            return "", 0.0
        text = "\n".join(r[1] for r in results)
        return text, 100 * sum(r[2] for r in results) / len(results)

    def read_raw(self, img):
        if self.engine == "tesseract":
            return self.read_tesseract(img)
        return self.read_easyocr(img)

    def best(self, img, max_variants=3):
        try:
            candidates = []
            for name, version in variants(img)[:max(max_variants, 1)]:
                text, conf = self.read_raw(version)
                candidates.append(OcrResult(text, conf, name, version))
        except Exception as e:
            raise OCRError(f"OCR failed: {e}")
        longest = max(len(c.text.strip()) for c in candidates) or 1

        def score(c):
            return c.confidence * min(1.0, len(c.text.strip()) / (0.6 * longest))

        return max(candidates, key=score)
