from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else BASE_DIR / p


def load_config(name="config.yaml"):
    path = resolve(name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {path}")
    except yaml.YAMLError as e:
        raise SystemExit(f"Config file is not valid YAML: {e}")


def load_profile(cfg):
    path = resolve(cfg["profile_file"])
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"Profile file not found: {path}")
    if not text:
        raise SystemExit(f"Profile file is empty: {path}")
    return text
