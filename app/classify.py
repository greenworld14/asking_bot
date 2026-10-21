import re

KIND_LABELS = {
    "auto": "Auto",
    "coding": "Coding",
    "technical": "Technical",
    "system_design": "System design",
    "behavioral": "Behavioral",
    "general": "General",
}

ROLE_LABELS = {
    "auto": "Auto",
    "recruiter": "Recruiter",
    "tech_lead": "Tech Lead",
    "cto": "CTO",
}

CODING_RE = re.compile(
    r"\bwrite (?:a |an |the |some )?(?:sql |python |java |javascript )?"
    r"(?:function|program|method|class|query|script|code|solution|algorithm)\b"
    r"|\bimplement (?:a|an|the)\b"
    r"|\bgiven (?:an?|the|two) (?:\w+ )?(?:array|list|string|number|integer|tree|matrix|linked list|graph|table|sequence)"
    r"|\b(?:input|output|constraints|example \d*)\s*:"
    r"|\b(?:live )?coding (?:task|challenge|problem|question|exercise|test|assessment)\b|\blive coding\b"
    r"|\bsolve (?:this|the following|the) (?:problem|task|challenge)\b"
    r"|\bleetcode\b|\bfizz ?buzz\b|\bpalindrome\b|\banagram\b|\bfibonacci\b|\btwo sum\b"
    r"|\breverse (?:a|the) (?:string|list|array|linked list|number|words)\b"
    r"|\bselect\b.+\bfrom\b.+\bwhere\b",
    re.IGNORECASE,
)

PERSONAL_RE = re.compile(
    r"\btell me about yourself\b|\bintroduce yourself\b|\bwhy do you want\b|\bwhy should we\b"
    r"|\bwhere do you see yourself\b|\bsalary\b|\bnotice period\b|\bwhen can you start\b"
    r"|\bwhy are you leaving\b|\bwhat do you know about (?:us|our company)\b",
    re.IGNORECASE,
)

BEHAVIORAL_RE = re.compile(
    r"\btell me about a time\b|\bdescribe a (?:time|situation)\b|\bgive (?:me )?an example of\b"
    r"|\bconflict\b|\bdisagree|\bmistake\b|\bfail(?:ure|ed)\b|\bweakness|\bstrength|\bproud\b"
    r"|\bchalleng|\bdeadline|\bpressure\b|\bdifficult (?:person|colleague|situation|stakeholder)"
    r"|\bhow do you (?:handle|deal|manage|prioriti[sz]e)\b|\bteam ?work\b|\bleadership\b",
    re.IGNORECASE,
)

DESIGN_RE = re.compile(
    r"\bdesign (?:a|an|the)\b(?! pattern)|\bsystem design\b|\barchitect|\bscal(?:e|ing|able|ability)\b"
    r"|\bhigh availability\b|\bload balanc|\bmicroservice|\bdistributed\b|\bmillions of\b"
    r"|\bthroughput\b|\bfault toleran|\bdisaster recovery\b",
    re.IGNORECASE,
)

TECH_RE = re.compile(
    r"\b(?:python|java|javascript|typescript|c\+\+|c#|golang|rust|kotlin|swift|php|ruby|sql|nosql"
    r"|database|index(?:es|ing)?|docker|kubernetes|aws|azure|gcp|cloud|api|rest|graphql|http|https|tcp"
    r"|git|ci/?cd|linux|react|angular|vue|node|django|flask|fastapi|spring|cache|caching|redis|kafka"
    r"|thread|async|concurren\w*|memory|oop|inheritance|polymorphism|encapsulation|interface|framework"
    r"|testing|unit test|security|authentication|oauth|jwt|complexity|big[- ]o|algorithm|data structure)\b"
    r"|\bdifference between\b|\bwhat is (?:a |an |the )?\w+",
    re.IGNORECASE,
)

ROLE_PATTERNS = [
    ("cto", re.compile(r"\bcto\b|chief technology|vp of engineering|head of engineering|co-?founder", re.I)),
    ("tech_lead", re.compile(
        r"tech(?:nical)? lead|team lead|engineering manager|lead (?:engineer|developer)"
        r"|staff engineer|principal engineer|senior engineer|architect", re.I)),
    ("recruiter", re.compile(r"recruit|talent|\bhr\b|human resources|people partner|hiring manager", re.I)),
]

LANGUAGES = [
    ("C++", "cpp", re.compile(r"c\+\+|\bcpp\b", re.I)),
    ("C#", "csharp", re.compile(r"c#|\.net\b|\bcsharp\b", re.I)),
    ("TypeScript", "typescript", re.compile(r"\btypescript\b", re.I)),
    ("JavaScript", "javascript", re.compile(r"\bjavascript\b|\bnode\.?js\b|\bjs\b", re.I)),
    ("Java", "java", re.compile(r"\bjava\b", re.I)),
    ("Go", "go", re.compile(r"\bgolang\b|\bin go\b", re.I)),
    ("Rust", "rust", re.compile(r"\brust\b", re.I)),
    ("Kotlin", "kotlin", re.compile(r"\bkotlin\b", re.I)),
    ("Swift", "swift", re.compile(r"\bswift\b", re.I)),
    ("PHP", "php", re.compile(r"\bphp\b", re.I)),
    ("Ruby", "ruby", re.compile(r"\bruby\b", re.I)),
    ("SQL", "sql", re.compile(r"\bsql\b|\bwrite (?:a |an )?query\b|\bselect\b.+\bfrom\b", re.I)),
    ("Python", "python", re.compile(r"\bpython\b", re.I)),
]


def classify(text):
    if not text:
        return "general"
    if CODING_RE.search(text):
        return "coding"
    if PERSONAL_RE.search(text):
        return "general"
    if BEHAVIORAL_RE.search(text):
        return "behavioral"
    if DESIGN_RE.search(text):
        return "system_design"
    if TECH_RE.search(text):
        return "technical"
    return "general"


def is_coding_text(text):
    return bool(text and CODING_RE.search(text))


def detect_role(text):
    for role, pattern in ROLE_PATTERNS:
        if text and pattern.search(text):
            return role
    return None


def resolve_role(selected, kind, screen_role=None):
    if selected and selected != "auto":
        return selected
    if screen_role:
        return screen_role
    return {"coding": "tech_lead", "technical": "tech_lead", "system_design": "cto"}.get(kind, "recruiter")


def detect_language(text):
    for name, _, pattern in LANGUAGES:
        if text and pattern.search(text):
            return name
    return None


def language_tag(name):
    for lang, tag, _ in LANGUAGES:
        if lang.lower() == (name or "").lower():
            return tag
    return (name or "text").lower()
