"""css-important-checker-cli: check CSS files for !important declarations, fail CI when any are found.

Reads the CSS files in a project folder and looks at every
declaration for `!important` — for example `color: red
!important;`. Every `!important` is a specificity escape hatch:
the stylesheet stops obeying its own order, and the next style
change becomes unpredictable. Each one is reported with the
file, the line of the `!`, and the property name, so it is easy
to find and remove. Report-only: it never rewrites a file.
Exit 0 when no declaration uses `!important`, 1 when any is
found, 2 for a usage error.

This is a different job from repo #74 (css-class-checker-cli),
which checks for UNUSED classes, and from repo #78
(css-duplicate-property-checker-cli), which checks for a
property declared twice in one rule. Neither of them looks for
`!important`. The field is empty for this job: the exact name
`css-important-checker-cli` matches 0 repositories on GitHub,
and `css important checker` matches only noise (checked
Nov 12, 2026).

`!important` is matched without case and with any amount of
space between the `!` and the word — `!IMPORTANT`,
`! important`, and `!  important` all count. A `!important`
inside a comment or inside a quoted string (like
`content: "!important"`) is not a declaration and is never
reported. A declaration split across lines is reported on the
line of the `!`.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSS_SUFFIX = ".css"
SKIPPED_DIRS = (".git", "__pycache__", "node_modules")

PROPERTY_RE = re.compile(r"^-{0,2}[A-Za-z][A-Za-z0-9-]*$")
IMPORTANT_RE = re.compile(r"!\s*important(?![A-Za-z0-9_.-])",
                           re.IGNORECASE)


class Problem:
    """One !important use: path, line number, plain reason."""

    def __init__(self, path, line, reason):
        self.path = path
        self.line = line
        self.reason = reason

    def text(self):
        return f"{self.path}:{self.line}: {self.reason}"

    def as_dict(self):
        return {"file": self.path, "line": self.line, "reason": self.reason}


def blank_out(match):
    """Replace a comment with spaces, keeping its newlines."""
    return "".join("\n" if char == "\n" else " "
                   for char in match.group(0))


def strip_comments(text):
    """Remove /* ... */ comments without moving later line numbers."""
    return re.sub(r"/\*.*?\*/", blank_out, text, flags=re.DOTALL)


def blank_strings(text):
    """Blank the contents of quoted strings, keeping their length.

    A string like `content: "!important"` must never be read as
    a declaration using `!important`, and a `;` or `}` inside a
    string must never end a declaration or a block. Replacing
    every string character (except the quotes themselves) with a
    space keeps every line number and every offset exactly where
    it was, so the rest of the scan works on plain text. An
    escaped quote inside a string does not end it.
    """
    chars = list(text)
    index = 0
    while index < len(text):
        char = text[index]
        if char in ("'", '"'):
            quote = char
            index += 1
            while index < len(text):
                inner = text[index]
                if inner == "\\" and index + 1 < len(text):
                    chars[index] = " "
                    chars[index + 1] = " "
                    index += 2
                    continue
                if inner == quote:
                    break
                if inner != "\n":
                    chars[index] = " "
                index += 1
        index += 1
    return "".join(chars)


def line_of(text, offset):
    """Line number (1-based) of a character offset in text."""
    return text.count("\n", 0, offset) + 1


class _Frame:
    """One open rule block: its pending declaration segment.

    A frame holds the text of the declaration currently being
    read, and the offset where it starts. A nested block (a rule
    inside a media query, or a nested rule) gets its own frame,
    so a declaration in the inner block is read on its own.
    """

    def __init__(self):
        self.segment = ""
        self.segment_start = 0


def _finish_segment(text, frame, path, problems):
    """Turn the frame's pending segment into a declaration, if it is one.

    A segment is a declaration when it holds `name: value` with
    a real property name and a non-empty value. Selector text
    (which has no colon, or a colon followed by selector text)
    never qualifies: a property name has no spaces and starts
    with a letter or a dash. When the value holds `!important`,
    a problem is recorded on the line of the `!`. Returns 1 when
    the segment was a declaration, else 0.
    """
    segment = frame.segment
    frame.segment = ""
    stripped = segment.strip()
    if not stripped or ":" not in stripped:
        return 0
    name, _, value = stripped.partition(":")
    name = name.strip()
    if not PROPERTY_RE.match(name):
        return 0
    if not value.strip():
        return 0
    match = IMPORTANT_RE.search(value)
    if match is None:
        return 1
    colon_at = segment.index(":")
    important_at = frame.segment_start + colon_at + 1 + match.start()
    line = line_of(text, important_at)
    problems.append(Problem(
        path, line,
        f"property '{name}' uses '!important'",
    ))
    return 1


def find_important(text, path):
    """Find !important uses in one CSS document.

    Returns (problems, declaration_count). Comments are blanked
    first and string contents are blanked next, so a
    `!important` in a comment or in a quoted value is never
    read as a declaration, and a `;` or `}` inside a string
    never ends a declaration or a block. A `;` inside
    parentheses (like a `url(data:...)` value) never splits a
    declaration either.
    """
    text = blank_strings(strip_comments(text))
    root = _Frame()
    stack = [root]
    problems = []
    total = 0
    paren_depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        frame = stack[-1]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        if char == "{":
            frame.segment = ""
            stack.append(_Frame())
            index += 1
            continue
        if char == "}":
            if len(stack) > 1:
                total += _finish_segment(text, frame, path, problems)
                stack.pop()
                stack[-1].segment = ""
            else:
                frame.segment = ""
            index += 1
            continue
        if char == ";" and paren_depth == 0 and len(stack) > 1:
            total += _finish_segment(text, frame, path, problems)
            index += 1
            continue
        if not frame.segment:
            frame.segment_start = index
        frame.segment += char
        index += 1
    while len(stack) > 1:
        frame = stack.pop()
        total += _finish_segment(text, frame, path, problems)
    problems.sort(key=lambda problem: problem.line)
    return problems, total


def check_files(css_files):
    """Check CSS files for !important uses.

    Returns (results, total_declarations) where results is a list
    of (path, declaration_count, [Problem]) per CSS file, in path
    order.
    """
    results = []
    total_declarations = 0
    for css_path in css_files:
        try:
            text = Path(css_path).read_text(encoding="utf-8",
                                            errors="replace")
        except OSError as exc:
            results.append((css_path, 0, [Problem(
                css_path, 0,
                f"cannot read file: {exc.strerror or exc}",
            )]))
            continue
        problems, count = find_important(text, css_path)
        total_declarations += count
        results.append((css_path, count, problems))
    return results, total_declarations


def is_excluded(name, patterns):
    """True when a file name matches any --exclude glob pattern."""
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in patterns)


def collect(paths, recursive=True, exclude=()):
    """Gather CSS files from the given paths.

    A folder contributes its .css files (recursively unless
    --no-recursive). A CSS file passed directly is always
    checked. .git, __pycache__, and node_modules folders are
    never walked, and directory links are never followed.
    Returns (css_files, missing) with files sorted and
    deduplicated.
    """
    css_files = []
    missing = []

    def walk(folder):
        for root, dirs, names in os.walk(folder):
            dirs[:] = sorted(
                name for name in dirs
                if name not in SKIPPED_DIRS
                and not os.path.islink(os.path.join(root, name))
            )
            if not recursive:
                dirs[:] = []
            for name in sorted(names):
                if is_excluded(name, exclude):
                    continue
                if name.lower().endswith(CSS_SUFFIX):
                    css_files.append(str(Path(root) / name))

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            missing.append(raw)
            continue
        if path.is_file():
            if path.name.lower().endswith(CSS_SUFFIX):
                css_files.append(str(path))
            continue
        walk(str(path))
    return sorted(set(css_files)), missing


def build_parser():
    parser = argparse.ArgumentParser(
        prog="css_important_checker",
        description="Check CSS files for !important declarations.",
    )
    parser.add_argument(
        "paths", nargs="*", metavar="PATH",
        help="CSS file(s) or folder(s) to check",
    )
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="PATTERN",
        help="skip walked files whose name matches this glob "
             "(repeatable; direct files are always checked)",
    )
    parser.add_argument(
        "--no-recursive", action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the result as machine-readable JSON "
             "(the summary goes to standard error)",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
    )
    return parser


def report_text(results, checked, total_declarations, total):
    """Print the plain-text report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    for path, count, problems in results:
        if problems:
            for problem in problems:
                print(f"FAIL {problem.text()}")
        elif count == 0:
            print(f"{path}: OK — no declarations found")
        else:
            print(f"{path}: OK — {count} declaration(s), "
                  "none use !important")
    if total == 0:
        print(f"OK — {checked} CSS file(s) checked, "
              f"{total_declarations} declaration(s), "
              "none use !important.")
        return 0
    print(f"Checked {checked} CSS file(s) "
          f"({total_declarations} declaration(s)), "
          f"{total} problem(s) in {files_with_problems} file(s).")
    return 1


def report_json(results, checked, total_declarations, total):
    """Print the JSON report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    payload = {
        "files": [
            {
                "file": path,
                "declarations": count,
                "problems": [problem.as_dict() for problem in problems],
            }
            for path, count, problems in results
        ],
        "summary": {
            "checked": checked,
            "declarations": total_declarations,
            "files_with_problems": files_with_problems,
            "problems": total,
        },
    }
    print(json.dumps(payload, indent=2))
    print(f"Checked {checked} CSS file(s) "
          f"({total_declarations} declaration(s)), "
          f"{total} problem(s) in {files_with_problems} file(s).",
          file=sys.stderr)
    return 1 if total else 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.paths:
        parser.error("give at least one PATH")
    css_files, missing = collect(
        args.paths,
        recursive=not args.no_recursive,
        exclude=args.exclude,
    )
    if missing:
        for raw in missing:
            print(f"error: no such file or folder: {raw}",
                  file=sys.stderr)
        return 2
    if not css_files:
        print("error: no CSS files found", file=sys.stderr)
        return 2
    results, total_declarations = check_files(css_files)
    total = sum(len(problems) for _, _, problems in results)
    if args.json:
        return report_json(results, len(css_files),
                           total_declarations, total)
    return report_text(results, len(css_files),
                       total_declarations, total)


if __name__ == "__main__":
    sys.exit(main())
