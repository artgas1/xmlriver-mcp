#!/usr/bin/env python3
"""Insert an MCP entry into awesome-mcp-servers README alphabetically.

Used by fan-out CI workflow to open a PR adding our MCP to the
🔎 Search & Data Extraction section of punkpeye/awesome-mcp-servers.

Usage:
    python3 scripts/insert_awesome_mcp_entry.py \\
        --readme /tmp/awesome-mcp-servers/README.md \\
        --entry "- [user/repo](https://github.com/user/repo) 🐍 ☁️ - Description."

Logic:
1. Find the Search & Data Extraction section heading (tries several variants).
2. Find the bullet list inside the section.
3. Insert the entry alphabetically by GitHub repo name.
4. Write back. Exit 0 on success, 1 on failure.
"""

import argparse
import re
import sys
from pathlib import Path

SECTION_HEADING_PATTERNS = [
    r"### 🔎 <a name=\"search\"></a>Search & Data Extraction",
    r"### 🔎 Search & Data Extraction",
    r"### 🔍 Search & Data Extraction",
    r"### 🔎 Search",
    r"### Search & Data Extraction",
    r"### 🌐 Search",
]


def find_section(content: str) -> tuple[int, int] | None:
    """Return (start_of_bullets, end_of_section) byte offsets in content.

    Searches in order of preference. Returns None if no section found.
    """
    for pat in SECTION_HEADING_PATTERNS:
        m = re.search(pat, content)
        if not m:
            continue
        section_start = m.end()
        # End of section = next "##" or "### " heading
        next_heading = re.search(r"\n##+ ", content[section_start:])
        section_end = section_start + (
            next_heading.start() if next_heading else len(content) - section_start
        )
        return section_start, section_end
    return None


def extract_repo_key(bullet_line: str) -> str:
    """Get the alphabetical key for sorting — first [owner/repo] in bullet."""
    m = re.match(r"-\s*\[([^\]]+)\]", bullet_line)
    return m.group(1).lower() if m else "zzz"


def insert_alphabetically(
    section_content: str, new_entry: str, repo_key: str
) -> str:
    """Insert new_entry into section_content at correct alphabetical position."""
    lines = section_content.split("\n")
    bullet_pat = re.compile(r"^-\s*\[")

    last_bullet_idx = -1
    for i, line in enumerate(lines):
        if not bullet_pat.match(line):
            continue
        last_bullet_idx = i
        existing_key = extract_repo_key(line)
        if existing_key > repo_key:
            lines.insert(i, new_entry)
            return "\n".join(lines)

    # Не нашли — append после последнего bullet, или в самом конце если нет ни одного
    if last_bullet_idx >= 0:
        lines.insert(last_bullet_idx + 1, new_entry)
    else:
        lines.append(new_entry)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", required=True, type=Path, help="Path to README.md")
    parser.add_argument(
        "--entry",
        required=True,
        help="Full bullet line, including leading '-' and trailing description",
    )
    args = parser.parse_args()

    content = args.readme.read_text(encoding="utf-8")

    # Check whether the entry already exists (idempotent re-run)
    repo_match = re.match(r"-\s*\[([^\]]+)\]", args.entry)
    if not repo_match:
        print(
            "ERROR: --entry must start with '- [owner/repo](...) ...'",
            file=sys.stderr,
        )
        return 1

    repo_path = repo_match.group(1)
    if f"[{repo_path}]" in content:
        print(f"Entry [{repo_path}] already in README — skipping", file=sys.stderr)
        return 0

    section = find_section(content)
    if section is None:
        print(
            "ERROR: 'Search & Data Extraction' section not found",
            file=sys.stderr,
        )
        return 1
    section_start, section_end = section

    new_section = insert_alphabetically(
        content[section_start:section_end],
        args.entry,
        repo_path.lower(),
    )
    new_content = content[:section_start] + new_section + content[section_end:]
    args.readme.write_text(new_content, encoding="utf-8")
    print(f"Inserted [{repo_path}] into Search & Data Extraction section")
    return 0


if __name__ == "__main__":
    sys.exit(main())
