"""Build the one-file review pack for the reviewer (a second Claude session, or Gemini).

    py -3 tools\\make_review_pack.py          (Windows)
    python3 tools/make_review_pack.py        (Mac / Linux)

It writes ../for_gemini/Luminaz_review_pack_<date>.txt containing, in order:
the instructions for the reviewer, AGENTS.md, HANDOFF.md, and every source file.
Diane attaches that one file to a fresh Claude (or Gemini) chat and sends the single line printed at the end.

Never included: instance/ (real data), backups, caches, and the third-party qrcode.min.js.
Standard library only.
"""
import datetime
import os
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(APP), "for_gemini")

TEXT_EXT = {".py", ".html", ".md", ".txt", ".css", ".js", ".bat", ".webmanifest"}
BARE_NAMES = {"Dockerfile", "Procfile"}
SKIP_DIRS = {"instance", "__pycache__", ".git", "backups", "for_gemini", ".venv", "venv", "node_modules"}
SKIP_FILES = {"qrcode.min.js", "AGENTS.md", "HANDOFF.md"}      # the last two are printed first, as parts 1 and 2

INSTRUCTIONS = """INSTRUCTIONS FOR THE REVIEWER

You are the second pair of eyes on the code for Luminaz, a small web app. Another AI (Claude)
writes the code. You review it. You do not rewrite it.

The person reading your answer is Diane, the founder. She is not a programmer. She will paste your
answer back to the builder, who will fix whatever holds up.

What is in this file, in order:
  PART 1  The rulebook (AGENTS.md). Sections 4 and 5 are the lines the code must never cross.
  PART 2  The handoff log (HANDOFF.md). Its top entry describes the latest change and lists the
          problems already known.
  PART 3  Every source file, each under a line that starts with ===== FILE:

Your job:
  1. Check the latest change described at the top of the handoff log. Is it correct? Could it
     break anything?
  2. Read the rest of the code and look for, in this order:
     a. anything that crosses a line in section 4 or 5 of the rulebook, or lets a user cross it;
     b. security problems: who can see or change what, sign-in, uploads, redirects, anything a
        stranger could abuse;
     c. places where a page promises something the code does not actually do;
     d. bugs that would stop a real investor or fund manager from finishing a task.
  3. Do not repeat a problem already listed in the handoff log unless you disagree with it or have
     something to add.

How to answer:
  - First line, for Diane, in plain words: is the latest change OK? Yes or no, and why in one
    sentence.
  - Then a numbered list, most serious first, at most 15 items. For each item give:
        Severity: High, Medium or Low
        Where: the file, and the function or line
        What happens: one or two plain sentences
        Why it matters: one sentence
        Suggested fix: one or two sentences. Do not paste rewritten files.
        Confidence: Sure, Fairly sure, or Not sure
  - If you find nothing in a category, say so in one line. Do not pad the list.
  - No praise, no summary of what the app does, no advice to change the technology.
  - If something is a product or legal decision rather than a bug, label it "Decision for Diane"
    or "Question for the attorney" and leave it there.
"""

ONE_LINE = "Follow the instructions at the top of the attached file."


def source_files():
    found = []
    for folder, dirs, files in os.walk(APP):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name in SKIP_FILES:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in TEXT_EXT or name in BARE_NAMES:
                found.append(os.path.join(folder, name))
    return found


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().replace("\r\n", "\n")


def main():
    today = datetime.date.today().isoformat()
    parts = [INSTRUCTIONS.rstrip() + "\n"]
    for title, name in (("PART 1: THE RULEBOOK (AGENTS.md)", "AGENTS.md"), ("PART 2: THE HANDOFF LOG (HANDOFF.md)", "HANDOFF.md")):
        path = os.path.join(APP, name)
        if not os.path.exists(path):
            sys.exit("Missing %s - the pack needs it." % name)
        parts.append("\n" + "#" * 100 + "\n" + title + "\n" + "#" * 100 + "\n\n" + read(path).rstrip() + "\n")
    files = source_files()
    parts.append("\n" + "#" * 100 + "\nPART 3: SOURCE FILES (%d files, built %s)\n" % (len(files), today) + "#" * 100 + "\n")
    lines = 0
    for path in files:
        rel = os.path.relpath(path, APP).replace(os.sep, "/")
        text = read(path)
        lines += text.count("\n") + 1
        parts.append("\n===== FILE: app/%s =====\n%s\n" % (rel, text.rstrip()))
    parts.append("\n===== END OF PACK =====\n")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "Luminaz_review_pack_%s.txt" % today)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(parts))
    size_kb = os.path.getsize(out) / 1024.0
    print("Review pack written: %s" % out)
    print("%d source files, about %d lines, %.0f KB" % (len(files), lines, size_kb))
    print("In a fresh Claude chat (or Gemini): attach that file and send this one line:")
    print("    " + ONE_LINE)


if __name__ == "__main__":
    main()
