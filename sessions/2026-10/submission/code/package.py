"""Build code.zip for submission.

Usage:
    python3 code/package.py

Contents: README.md, requirements.txt, .env.example, code/, and evaluation/.
AGENTS.md 6.8 names evaluation/*.md while the organizers' README names
code/evaluation/*.md, so the reports are kept in code/evaluation/ and copied
to a top-level evaluation/ at packaging time; both paths ship. Excluded:
dataset/, virtual environments, __pycache__, .DS_Store, temporary cache files
and any archive (no nested archives).
"""
import shutil
import sys
import zipfile

from contract import REPO_ROOT

TOP_FILES = ("README.md", "requirements.txt", ".env.example")
REPORTS = ("evaluation_report.md", "usage_report.md")
SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", ".git"}
SKIP_SUFFIXES = (".pyc", ".tmp", ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar")


def copy_reports():
    out = REPO_ROOT / "evaluation"
    out.mkdir(exist_ok=True)
    for name in REPORTS:
        shutil.copyfile(REPO_ROOT / "code" / "evaluation" / name, out / name)


def files_to_ship():
    paths = [REPO_ROOT / name for name in TOP_FILES]
    for folder in ("code", "evaluation"):
        for p in sorted((REPO_ROOT / folder).rglob("*")):
            rel = p.relative_to(REPO_ROOT)
            if p.is_file() and not SKIP_DIRS & set(rel.parts) and p.name != ".DS_Store" \
                    and not p.name.endswith(SKIP_SUFFIXES):
                paths.append(p)
    return paths


def main():
    copy_reports()
    target = REPO_ROOT / "code.zip"
    paths = files_to_ship()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, p.relative_to(REPO_ROOT).as_posix())
    print(f"wrote {target} with {len(paths)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
