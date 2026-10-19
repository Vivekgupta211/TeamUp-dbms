"""Create a portable source ZIP without local passwords, environments, or caches."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "team-matching-backend.zip"
FOLDERS = ("app", "database", "docs", "scripts", "tests")
FILES = (
    "README.md",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-lock.txt",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "compose.yaml",
    "pyproject.toml",
)


def package():
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if path.is_file():
                archive.write(path, f"team-matching-backend/{name}")
        for folder in FOLDERS:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, f"team-matching-backend/{path.relative_to(ROOT)}")
    print(OUTPUT)


if __name__ == "__main__":
    package()
