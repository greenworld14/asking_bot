# Meeting Answers

Press a hotkey, read the question on your screen with OCR, and get a short answer from your profile in a small always-on-top window.

## Folder structure

```
meeting_answers/
  main.py
  config.yaml
  profile.txt
  requirements.txt
  requirements-optional.txt
  history.jsonl          (created automatically)
  app/
    config.py
    capture.py
    ocr.py
    questions.py
    llm.py
    history.py
    audio.py
    ui.py
```

## Setup (Windows, Python 3.11+)

1. Create a virtual environment and install packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
   Then check `ocr.tesseract_cmd` in config.yaml. (Or set `ocr.engine: easyocr` and install `requirements-optional.txt`.)
3. Edit `profile.txt` with your real resume, skills, and results.
4. Pick the AI model in `config.yaml` with `provider`:
   - `ollama`: install Ollama, then run `ollama pull qwen3:8b`.
   - `claude`: set your key with `setx ANTHROPIC_API_KEY "your-key"` and open a new terminal.
5. Run: `python main.py`

## Use

| Key | Action |
| --- | --- |
| F8 | Capture screen (or the chosen region), find the last question, show the answer |
| F9 | Drag a box to choose a capture region (Esc cancels) |
| Shift+F9 | Forget the saved region and capture the full screen again |
| F10 | Turn live audio listening on or off |

The region you choose is saved in `region.json` and reused next time.
F9: drag a box and the program reads the question and answers it right away. F8: read the same region again and answer.
No buttons are needed, but they help when OCR makes a mistake:

| Button | What it does |
| --- | --- |
| Send to AI | Sends the text in the Question box (after you edit it). Ctrl+Enter does the same. |
| Re-scan | Reads the saved region again and answers (same as F8). |
| Use full text | Puts all the screen text in the Question box. Then press Send to AI. |
| Region | Select a new region (same as F9). |
| Copy | Copies the whole answer. |
| Copy code | Copies only the code from the answer. |

## Interviewer and question type

The program finds the question type by itself and answers in the right style:

| Type | Answer |
| --- | --- |
| Coding | Full solution in a code block, then Approach and Complexity |
| Technical | Direct answer, one short example (small code snippet if useful) |
| System design | 4 to 6 short bullet points |
| Behavioral | STAR (Situation, Task, Action, Result) |
| General | 2 to 4 short sentences from your profile |

The tone changes with the interviewer: **Recruiter** (plain words), **Tech Lead** (technical detail), **CTO**
(architecture, cost and business impact). With **Auto**, it uses a role seen on screen (for example "Anna (CTO)"),
otherwise Tech Lead for coding and technical questions, CTO for system design, and Recruiter for the rest.
Use the **Interviewer** and **Type** menus at the top of the window to choose them yourself.

For a coding task the whole problem text from the region is sent, including Input, Output and Example lines.
The default language is `coding.language` in config.yaml; a language named in the task (Java, SQL, C++...) wins.
Local models are slower for code: a coding answer from `qwen3:8b` can take 20 to 60 seconds. Set `mode: vision` to send the screenshot itself to the AI
(Claude, or an Ollama vision model such as `qwen2.5vl:7b`).

`debug_capture.png` is exactly what was captured. `debug_ocr.png` is the cleaned-up image the OCR read.

## Testing

```
python main.py --test                 read the saved region (or full screen) and print the OCR report
python main.py --test some_image.png  run the same report on an image file
python tests/test_samples.py          run the 6 built-in sample images
python tests/test_classify.py         check question type, interviewer and language detection
```

The `keyboard` library may need an administrator terminal on some systems.
Choosing a small region around the meeting chat or captions makes OCR faster and more accurate.

## Live audio (optional)

```
pip install -r requirements-optional.txt
python main.py --devices
```

Set `audio.device` in config.yaml to the device number or name. To hear the other person, use a loopback input such as "Stereo Mix" (enable it in Windows Sound settings) or a virtual cable. Set `audio.enabled: true` to start listening on launch. Whisper runs on CPU with the `base.en` model; use `tiny.en` if CPU use is too high.

## History

Every question and answer is appended to `history.jsonl` (one JSON object per line). Turn it off with `history.enabled: false`.
