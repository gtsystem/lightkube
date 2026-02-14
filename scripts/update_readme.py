#!/usr/bin/env python3
"""Convert pymdownx.tabbed markdown to plain markdown keeping only first tab's content.

Default: read `docs/index.md` and write `README.md` in repo root.

The script removes tab markers like:

=== "Tab title"
    indented content...

and keeps only the content of the first tab for each tab group, unindenting it.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional


MARKER_RE = re.compile(r'^[ \t]*===[ \t]*["\'].*?["\'][ \t]*$')


def find_next_marker(lines: List[str], start: int) -> Optional[int]:
    n = len(lines)
    for idx in range(start + 1, n):
        if MARKER_RE.match(lines[idx]):
            return idx
    return None


def all_indented_or_blank(lines: List[str], a: int, b: int) -> bool:
    # check lines[a:b] (exclusive of b) are blank or start with space/tab
    for L in lines[a:b]:
        if L.strip() == '':
            continue
        if L.startswith(' ') or L.startswith('\t'):
            continue
        return False
    return True


def unindent_block(block: List[str]) -> List[str]:
    # remove common leading indentation (spaces or tabs) from non-blank lines
    indents = []
    for L in block:
        if L.strip() == '':
            continue
        m = re.match(r'^[ \t]*', L)
        indents.append(len(m.group(0)))
    if not indents:
        return block
    strip = min(indents)
    if strip == 0:
        return block
    out = []
    for L in block:
        if L.startswith(' ' * strip) or L.startswith('\t' * strip):
            out.append(L[strip:])
        else:
            # if line is shorter than strip or different indentation, lstrip just up to strip spaces
            out.append(L.lstrip(' \t'))
    return out


def transform(lines: List[str]) -> List[str]:
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if MARKER_RE.match(line):
            # Found a tab marker. Collect the immediately following indented
            # block (the first tab content) and append its unindented form.
            start = i + 1
            end = start
            while end < n and (lines[end].strip() == '' or lines[end].startswith(' ') or lines[end].startswith('\t')):
                end += 1
            block = lines[start:end]
            out.extend(unindent_block(block))

            # Advance to the next non-indented line after the first tab block.
            i = end

            # Now skip any immediately consecutive tab markers with only indented
            # content between them (they belong to the same tab group). Stop when
            # a non-indented line or EOF is encountered.
            while i < n and MARKER_RE.match(lines[i]):
                # determine the block after this marker
                s = i + 1
                e = s
                while e < n and (lines[e].strip() == '' or lines[e].startswith(' ') or lines[e].startswith('\t')):
                    e += 1
                # skip this marker+block by advancing i to e
                i = e

            continue

        # not a marker, copy line as-is
        out.append(line)
        i += 1

    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Keep only first tab content from pymdownx.tabbed markdown')
    p.add_argument('--source', '-s', default='docs/index.md', help='Source markdown file')
    p.add_argument('--dest', '-d', default='README.md', help='Destination markdown file')
    args = p.parse_args(argv)

    src = Path(args.source)
    dst = Path(args.dest)

    if not src.exists():
        print(f'Error: source {src} not found')
        return 2

    text = src.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    out_lines = transform(lines)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(''.join(out_lines), encoding='utf-8')
    print(f'Wrote {dst}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
