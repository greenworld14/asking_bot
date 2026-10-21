import re
from dataclasses import dataclass

STARTERS = (
    "what", "why", "how", "when", "where", "who", "which",
    "can you", "could you", "would you", "tell me", "tell us", "describe", "explain",
    "walk me through", "talk about", "give me", "introduce yourself",
    "do you", "have you", "are you", "did you", "please tell", "please explain", "please describe",
)

STARTER_RE = re.compile(r"^(?:" + "|".join(re.escape(s) for s in STARTERS) + r")\b", re.IGNORECASE)
INNER_RE = re.compile(
    r"(?<=[a-z,])\s+(?=(?:" + "|".join(re.escape(s[0].upper() + s[1:]) for s in STARTERS) + r")\b)"
)
SPLIT_RE = re.compile(r"(?<=[.?!])\s+(?=[\"'A-Z0-9])")


@dataclass
class Detection:
    question: str | None
    context: str
    method: str


def split_sentences(text):
    out = []
    for line in text.splitlines():
        out.extend(p.strip() for p in SPLIT_RE.split(line.strip()) if p.strip())
    return out


def is_question(sentence):
    return len(sentence.split()) >= 3 and (sentence.endswith("?") or bool(STARTER_RE.match(sentence)))


def trim_question(sentence):
    if sentence.endswith("?"):
        matches = list(INNER_RE.finditer(sentence))
        if matches:
            cut = sentence[matches[-1].end():]
            if len(cut.split()) >= 3:
                return cut
    return sentence


def detect(text, context_sentences=2, long_after=3):
    sents = split_sentences(text)
    if not sents:
        return Detection(None, "", "none")
    index, method = None, None
    for i, s in enumerate(sents):
        if is_question(s):
            index, method = i, "question"
    if index is None:
        for i in reversed(range(len(sents))):
            if len(sents[i].split()) >= 4 and sents[i][-1] in ".!":
                index, method = i, "last_sentence"
                break
    if index is None:
        lines = [line.strip() for line in text.splitlines() if len(line.split()) >= 3]
        if not lines:
            return Detection(None, "", "none")
        return Detection(lines[-1], "", "last_paragraph")
    question = trim_question(sents[index]) if method == "question" else sents[index]
    context = ""
    if len(sents) > long_after:
        context = " ".join(sents[max(0, index - context_sentences):index])
    return Detection(question, context, method)
