#!/usr/bin/env python3
"""Replace static HTML style attributes with page-local generated classes."""

from hashlib import sha1
from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent
STYLE_ATTR = re.compile(r'\sstyle="([^"]+)"', re.IGNORECASE)
TAG_WITH_STYLE = re.compile(r'<([A-Za-z][^<>]*?)\sstyle="([^"]+)"([^<>]*?)>', re.IGNORECASE)
GENERATED = re.compile(
    r'\n?<style id="generated-inline-styles">.*?</style>',
    re.IGNORECASE | re.DOTALL,
)


def class_name(style):
    return "u-" + sha1(style.strip().encode("utf-8")).hexdigest()[:10]


def replace_tag(match):
    before, style, after = match.groups()
    generated = class_name(style)
    class_match = re.search(r'\bclass="([^"]*)"', before, re.IGNORECASE)
    if class_match:
        classes = class_match.group(1).split()
        if generated not in classes:
            classes.append(generated)
        before = before[:class_match.start(1)] + " ".join(classes) + before[class_match.end(1):]
    else:
        before += f' class="{generated}"'
    return f"<{before}{after}>"


def process(path):
    original = path.read_text(encoding="utf-8")
    base = GENERATED.sub("", original)
    styles = sorted(set(STYLE_ATTR.findall(base)))
    if not styles:
        return False
    updated = TAG_WITH_STYLE.sub(replace_tag, base)
    rules = [f".{class_name(style)} {{ {style.strip()} }}" for style in styles]
    block = '\n<style id="generated-inline-styles">\n' + "\n".join(rules) + "\n</style>"
    updated = updated.replace("</head>", block + "\n</head>", 1)
    path.write_text(updated, encoding="utf-8")
    print(f"Extracted {len(styles)} styles from {path.relative_to(REPO)}")
    return True


def main():
    count = 0
    for path in sorted(REPO.rglob("*.html")):
        if any(part in {".git", ".venv"} for part in path.parts):
            continue
        count += process(path)
    print(f"Updated {count} HTML files")


if __name__ == "__main__":
    main()