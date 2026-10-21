from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "samples"

SAMPLES = {
    "1_normal": {
        "lines": [
            "Sarah Lee  10:32 AM",
            "Thanks for joining today.",
            "Can you tell me about your experience with Python?",
            "",
            "Mute    Stop Video    Share Screen    Chat",
        ],
        "size": 22, "bg": (255, 255, 255), "fg": (25, 25, 25),
        "question": "Can you tell me about your experience with Python?", "method": "question",
    },
    "2_dark_mode": {
        "lines": ["Recruiter", "Why do you want to work at our company?", "", "Unmute   Chat   Leave"],
        "size": 22, "bg": (32, 33, 36), "fg": (232, 234, 237),
        "question": "Why do you want to work at our company?", "method": "question",
    },
    "3_small_font": {
        "lines": ["How would you design a REST API for a library", "system with users, books and loans?"],
        "size": 12, "bg": (250, 250, 250), "fg": (40, 40, 40),
        "question": "How would you design a REST API for a library system with users, books and loans?",
        "method": "question",
    },
    "4_two_questions": {
        "lines": [
            "Mike Chen  10:40 AM",
            "What is your current role?",
            "Mike Chen  10:41 AM",
            "Okay great. How do you handle tight deadlines?",
        ],
        "size": 20, "bg": (255, 255, 255), "fg": (30, 30, 30),
        "question": "How do you handle tight deadlines?", "method": "question",
    },
    "5_no_question_mark": {
        "lines": [
            "Interviewer",
            "Thanks for sharing that.",
            "I would like to hear about the biggest challenge in your last job.",
        ],
        "size": 20, "bg": (255, 255, 255), "fg": (30, 30, 30),
        "question": "I would like to hear about the biggest challenge in your last job.", "method": "last_sentence",
    },
    "6_coding_task": {
        "lines": [
            "Live coding task",
            "Given an array of integers nums and an integer target,",
            "return the indices of the two numbers that add up to target.",
            "Write a function in Python.",
        ],
        "size": 20, "bg": (30, 30, 30), "fg": (220, 220, 220),
        "question": "Live coding task Given an array of integers nums and an integer target, return the indices "
                    "of the two numbers that add up to target. Write a function in Python.",
        "method": "coding_task",
    },
}


def load_font(size):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(sample):
    font = load_font(sample["size"])
    line_height = int(sample["size"] * 1.6)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    width = int(max(probe.textlength(line, font=font) for line in sample["lines"])) + 40
    height = line_height * len(sample["lines"]) + 40
    img = Image.new("RGB", (width, height), sample["bg"])
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(sample["lines"]):
        draw.text((20, 20 + i * line_height), line, font=font, fill=sample["fg"])
    return img


def make_all():
    OUT.mkdir(exist_ok=True)
    paths = []
    for name, sample in SAMPLES.items():
        path = OUT / f"{name}.png"
        render(sample).save(path)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in make_all():
        print(p)
