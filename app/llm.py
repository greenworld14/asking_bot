import base64
import os
import re

import requests

from .classify import language_tag
from .config import resolve

SYSTEM_TEMPLATE = """You help a job candidate answer questions during a live video interview.
The interviewer may be a recruiter, a technical lead, or a CTO.

Use ONLY the facts in the PROFILE below when you talk about the candidate's experience.
Never invent employers, projects, numbers, tools, or skills. If the profile does not cover it, say so honestly in a short way.
Coding and technical knowledge answers do not need to come from the profile, but never claim work experience that is not in it.
The question comes from OCR or speech, so it may have small typos. If the message has several sentences, answer the last question or task.
Follow the rules given with each question exactly. No preamble.

PROFILE:
{profile}
"""

ROLES = {
    "recruiter": "The interviewer is a recruiter (not technical). Use plain words, avoid jargon, focus on results, teamwork and motivation.",
    "tech_lead": "The interviewer is a technical lead. Be precise and technical. Mention tools, best practices and trade-offs.",
    "cto": "The interviewer is a CTO. Connect the answer to architecture, scalability, reliability, cost and business impact.",
}

KEY_WORDS = "- Last line: Key words: **word1**, **word2**, **word3** (exactly 3 short key words in bold)."

STYLES = {
    "coding": """- This is a live coding task. Solve it in {language} unless the task names another language.
- Reply in this order:
  1. The full solution in ONE fenced code block that starts with ```{tag}. Correct, clean, runnable code with clear names, edge cases handled, and very few comments. Add a tiny usage example at the end of the code if it helps.
  2. Approach: one or two short sentences in simple English that the candidate can say out loud.
  3. Complexity: time and space in Big-O.
""" + KEY_WORDS,
    "system_design": """- This is a system design question.
- Give 4 to 6 short bullet points: main components, data flow, storage, scaling, and one trade-off.
- Simple English, one line per bullet.
""" + KEY_WORDS,
    "technical": """- This is a technical question.
- Give the direct answer first, then one short example. 2 to 4 short sentences in simple English.
- If a tiny code snippet makes it clearer, add it in a fenced code block (max 8 lines).
""" + KEY_WORDS,
    "behavioral": """- This is a behavior question. Use STAR with one short sentence each, starting with the labels Situation:, Task:, Action:, Result:.
- Speak in first person as the candidate, using only facts from the profile.
""" + KEY_WORDS,
    "general": """- Simple English, 2 to 4 short sentences, first person as the candidate, using only facts from the profile.
""" + KEY_WORDS,
}

VISION_PROMPT = """This is a screenshot from a video interview.
Find the LAST question or task in it. Ignore names, timestamps, and buttons like Mute, Share, Chat.
If there is no clear question, use the last full sentence.
If it is a coding task, solve it in {language}: give the full solution in one fenced code block, then "Approach:" (1-2 sentences) and "Complexity:".
Otherwise answer in simple English, 2 to 4 short sentences, using only facts from the profile for experience.
End with: Key words: **word1**, **word2**, **word3**
Reply in exactly this form:
Q: <the question or a one-line summary of the task>

<the answer>"""

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
LONG_KINDS = ("coding", "system_design")


class LLMError(Exception):
    pass


def clean(text):
    return THINK_RE.sub("", text).strip()


def user_message(question, context="", kind="general", role="recruiter", language="Python"):
    style = STYLES.get(kind, STYLES["general"]).format(language=language, tag=language_tag(language))
    parts = [ROLES.get(role, ROLES["recruiter"]), "Rules:\n" + style]
    if context:
        parts.append(f"Earlier text on screen (only for context):\n{context}")
    label = "Task" if kind == "coding" else "Question"
    parts.append(f"{label}:\n{question}")
    return "\n\n".join(parts)


def split_vision(text):
    lines = text.strip().splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip().lower().startswith("q:"):
            return line.strip()[2:].strip(), "\n".join(lines[i + 1:]).strip()
        break
    return None, text.strip()


class OllamaClient:
    def __init__(self, cfg, system, long_tokens):
        self.url = cfg["host"].rstrip("/") + "/api/chat"
        self.model = cfg["model"]
        self.vision_model = cfg.get("vision_model") or self.model
        self.timeout = cfg.get("timeout", 300)
        self.system = system
        self.long_tokens = long_tokens

    def chat(self, model, message, tokens):
        payload = {
            "model": model,
            "stream": False,
            "think": False,
            "messages": [{"role": "system", "content": self.system}, message],
            "options": {"temperature": 0.2, "num_predict": tokens},
        }
        try:
            r = requests.post(self.url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return clean(r.json()["message"]["content"])
        except requests.ConnectionError:
            raise LLMError("Cannot reach Ollama. Is it running? (ollama serve)")
        except requests.Timeout:
            raise LLMError("Ollama took too long to answer. Raise ollama.timeout in config.yaml")
        except requests.HTTPError as e:
            raise LLMError(f"Ollama error: {e.response.text[:200]}")
        except (KeyError, ValueError) as e:
            raise LLMError(f"Bad reply from Ollama: {e}")

    def ask(self, question, context="", kind="general", role="recruiter", language="Python"):
        tokens = self.long_tokens if kind in LONG_KINDS else 400
        content = user_message(question, context, kind, role, language)
        return self.chat(self.model, {"role": "user", "content": content}, tokens)

    def ask_image(self, png_bytes, language="Python"):
        image = base64.b64encode(png_bytes).decode("ascii")
        message = {"role": "user", "content": VISION_PROMPT.format(language=language), "images": [image]}
        return self.chat(self.vision_model, message, self.long_tokens)


class ClaudeClient:
    def __init__(self, cfg, system, long_tokens):
        try:
            import anthropic
        except ImportError:
            raise LLMError("anthropic package is not installed")
        key_env = cfg.get("api_key_env", "ANTHROPIC_API_KEY")
        key_file = resolve(cfg.get("api_key_file", "anthropic_key.txt"))
        key = os.environ.get(key_env, "").strip()
        if not key and key_file.is_file():
            key = key_file.read_text(encoding="utf-8").strip()
        if not key:
            raise LLMError(
                f"No Claude API key. Paste it into {key_file.name} next to main.py, "
                f"or run: setx {key_env} \"your-key\" and restart VS Code"
            )
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=key)
        self.model = cfg["model"]
        self.max_tokens = cfg.get("max_tokens", 400)
        self.long_tokens = long_tokens
        self.system = system

    def chat(self, content, tokens):
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=tokens,
                system=self.system,
                messages=[{"role": "user", "content": content}],
            )
            return "".join(b.text for b in msg.content if b.type == "text").strip()
        except self.anthropic.AuthenticationError:
            raise LLMError("Claude API key was rejected")
        except self.anthropic.RateLimitError:
            raise LLMError("Claude API rate limit reached")
        except self.anthropic.APIConnectionError:
            raise LLMError("Cannot reach the Claude API")
        except self.anthropic.APIError as e:
            raise LLMError(f"Claude API error: {e}")

    def ask(self, question, context="", kind="general", role="recruiter", language="Python"):
        tokens = self.long_tokens if kind in LONG_KINDS else self.max_tokens
        return self.chat(user_message(question, context, kind, role, language), tokens)

    def ask_image(self, png_bytes, language="Python"):
        image = base64.b64encode(png_bytes).decode("ascii")
        return self.chat([
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image}},
            {"type": "text", "text": VISION_PROMPT.format(language=language)},
        ], self.long_tokens)


def create_client(cfg, profile):
    system = SYSTEM_TEMPLATE.format(profile=profile)
    long_tokens = cfg.get("coding", {}).get("max_tokens", 1500)
    provider = cfg["provider"].lower()
    if provider == "ollama":
        return OllamaClient(cfg["ollama"], system, long_tokens)
    if provider == "claude":
        return ClaudeClient(cfg["claude"], system, long_tokens)
    raise LLMError(f"Unknown provider: {provider}")
