"""Linter for architectural markdown specifications."""
import os
import sys

def lint_markdown_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    has_title = content.startswith("# ")
    has_sections = "## " in content
    return has_title and has_sections

if __name__ == "__main__":
    print("Linting spec files...")
