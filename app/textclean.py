import re

from .questions import STARTER_RE

BUTTON_WORDS = {
    "mute", "unmute", "start", "stop", "video", "share", "screen", "chat", "participants", "people",
    "leave", "end", "meeting", "record", "recording", "reactions", "react", "raise", "lower", "hand",
    "more", "apps", "security", "captions", "cc", "present", "now", "view", "gallery", "speaker",
    "everyone", "to", "send", "camera", "mic", "microphone", "join", "invite", "details", "rooms",
    "breakout", "notes", "whiteboard", "activities", "host", "tools", "copy", "link", "settings",
    "search", "close", "minimize", "maximize", "turn", "on", "off", "type", "message", "here", "a",
    "summary", "companion", "ai", "anydesk", "rustdesk", "zoom", "teams", "meet", "options", "audio",
    "full", "exit", "pin", "spotlight", "rename", "hide", "show", "waiting", "room", "admit",
}

QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?(?=\W|$)")
TAG_RE = re.compile(r"\((?:host|co-host|me|you|guest|edited|external)\)", re.IGNORECASE)
FROM_RE = re.compile(r"^from\s+.{1,40}?\s+to\s+(?:.{1,30}?:|everyone\b|me\b)\s*", re.IGNORECASE)
NAME_PREFIX_RE = re.compile(r"^(?!(?:Input|Output|Example|Explanation|Constraints|Note|Task)\b)(?:[A-Z][\w'.-]*\s+){0,2}[A-Z][\w'.-]*\s*:\s+")
NAME_RE = re.compile(r"^[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,2}:?$")
PIPE_I_RE = re.compile(r"(?:^|(?<=\s))[|!](?=\s+[a-z]|'[a-z])")
JUNK_RE = re.compile(r"[^A-Za-z0-9\s.,?!'\":;()\[\]{}<>=*&%$@#+/\-]")
SECTION_RE = re.compile(r"^(?:input|output|example|explanation|constraints|note)\b", re.IGNORECASE)
CODE_LINE_RE =re.compile(r"^(?:input|output|example|explanation|constraints|note)\b|\w\s*=\s*\S|\[.*\]", re.IGNORECASE)


def normalize(line):
    for a, b in QUOTES.items():
        line = line.replace(a, b)
    line = FROM_RE.sub("", line.strip())
    line = PIPE_I_RE.sub("I", line)
    line = TIME_RE.sub(" ", line)
    line = TAG_RE.sub(" ", line)
    line = JUNK_RE.sub(" ", line)
    line = re.sub(r"\s+", " ", line).strip()
    line = NAME_PREFIX_RE.sub("", line)
    line = line.lstrip(" -.,:;'\"").rstrip(" -;")
    line = re.sub(r"\s+([?.!,;:])", r"\1", line)
    line = re.sub(r"([?!.])\1+", r"\1", line)
    line = re.sub(r"([?!])(?=[A-Za-z])", r"\1 ", line)
    line = re.sub(r"(?<=[a-z])\.(?=[A-Z][a-z])", ". ", line)
    line = re.sub(r",(?=[A-Za-z])", ", ", line)
    line = re.sub(r"\s+'(s|t|re|ve|ll|d|m)\b", r"'\1", line)
    line = re.sub(r"\b(\w+) n't\b", r"\1n't", line)
    if STARTER_RE.match(line):
        line = re.sub(r"(?<=[a-z])[72]$", "?", line)
    return line.strip()


def is_junk(line):
    letters = sum(c.isalpha() for c in line)
    if len(line) < 3 or letters == 0:
        return True
    return letters < len(line) * 0.5 and not CODE_LINE_RE.search(line)


def is_buttons(line):
    words = re.findall(r"[a-z]+", line.lower())
    return bool(words) and all(w in BUTTON_WORDS for w in words)


def is_name(line):
    return bool(NAME_RE.match(line)) and not STARTER_RE.match(line) and line[-1] not in ".?!"


def neighbour(items, index, step):
    i = index + step
    while 0 <= i < len(items):
        if items[i]:
            return items[i]
        i += step
    return None


def should_join(prev, cur, longest):
    if prev[-1] in ".?!:" or SECTION_RE.match(cur):
        return False
    if cur[0].islower():
        return True
    return longest >= 30 and len(prev) >= 0.7 * longest


def join(prev, cur):
    if prev.endswith("-") and cur[0].islower():
        return prev[:-1] + cur
    return prev + " " + cur


def clean_text(raw):
    items = []
    for line in raw.splitlines():
        if not line.strip():
            items.append("")
            continue
        line = normalize(line)
        if line and not is_junk(line) and not is_buttons(line):
            items.append(line)

    kept = []
    for i, line in enumerate(items):
        if line and is_name(line):
            prev, nxt = neighbour(items, i, -1), neighbour(items, i, 1)
            if prev is None or prev[-1] in ".?!:" or nxt is None or nxt[0].isupper():
                continue
        kept.append(line)

    paragraphs, current = [], []
    for line in kept:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)

    out = []
    for para in paragraphs:
        longest = max(len(line) for line in para)
        merged = []
        for line in para:
            if merged and should_join(merged[-1], line, longest):
                merged[-1] = join(merged[-1], line)
            else:
                merged.append(line)
        out.extend(merged)
    return "\n".join(out)
