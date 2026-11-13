# css-important-checker-cli

Check CSS files for `!important` declarations, fail CI when any are found.

[![CI](https://github.com/haiderstudio/css-important-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/css-important-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`css_important_checker` reads the CSS files in a project
folder and looks at every declaration for `!important`:

- Every `!important` is a specificity escape hatch: the
  stylesheet stops obeying its own order, and the next
  style change becomes unpredictable — the next developer
  pays for it. This tool reports each use with the file,
  the line of the `!`, and the property name, so it is easy
  to find and remove. It exits 1 when any `!important` is
  found, so it can fail a CI run. A project with none
  exits 0.
- `!important` is matched without case and with any amount
  of space between the `!` and the word — `!IMPORTANT`,
  `! important`, and `!  important` all count — and a
  declaration split across lines is reported on the line
  of the `!`. Custom properties (`--brand`) and vendor
  prefixes (`-webkit-transform`) count too.
- Comments are stripped first, so a `!important` written
  in a comment is never reported. A `!important` inside a
  quoted string (like `content: "!important"`) is not a
  declaration and is never reported, and a `;` or `}` inside
  a quoted value never ends a declaration or a block. A `;`
  inside parentheses (like a `url(data:...)` value) never
  splits a declaration.
- A project folder is given on the command line, and it is
  walked recursively by default (`--no-recursive` stops at
  the top level). A single CSS file can be given instead —
  only that file is checked. `.git`, `__pycache__`, and
  `node_modules` folders are never walked, and directory
  links are never followed, so a link cycle cannot loop the
  check.
- `--exclude PATTERN` skips walked files by glob, for
  example `--exclude 'vendor-*'`. It can be repeated. A
  file passed directly on the command line is always
  checked, even if it matches an exclude pattern.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never edits
  a file, sends nothing anywhere, and needs no API key.
  Python standard library only — plain-text parsing, no
  CSS parser.

## What it does NOT do

- It does not check unused classes. That job is
  css-class-checker-cli (repo #74 in the same series),
  which reports classes nothing references. This tool's
  one job is `!important` use.
- It does not check duplicate properties in one rule.
  That job is css-duplicate-property-checker-cli (repo #78
  in the same series). A rule that repeats a property
  without `!important` passes here.
- It does not delete or fix a `!important`. One is
  reported with its file and line; removing it is your
  job.
- It does not read stylesheets loaded from a URL. Every
  input is a local file or folder.
- It does not understand every corner of CSS: a
  declaration with an empty value (`color:;`) is not
  counted as a declaration, and a declaration split
  across a line inside a string is read as written.
  Plain stylesheets, which is what projects actually
  ship, are all covered.

## Who it is for

Anyone with a stylesheet that has grown `!important`
over time and wants it out: a developer tidying a site
before a redesign, a team adding a CI step that fails
the build when a declaration escapes the cascade, or
anyone who has ever changed one value and watched a
different rule win for no visible reason. Every use is
named with its file, line, and property — the delete is
safe.

## How this differs from similar tools

The exact name `css-important-checker-cli` matches 0
repositories on GitHub (checked Nov 12, 2026), and the
wider field `css important checker` matches only 2
results, both noise — a colour palette picker website
and a vehicle-registration checker. Neither checks CSS
for `!important`. The field is empty for this job.

The closest tools do different jobs on the same files.
css-class-checker-cli (repo #74 in the same series)
checks for UNUSED classes — a class nothing references.
It never looks at declaration values. css-duplicate-
property-checker-cli (repo #78 in the same series)
checks for a property declared twice in one rule — a
rule that repeats a property without `!important`
passes here, and a single `!important` passes there.
colour-contrast-checker-cli (repo #18 in the same
series) checks colour pairs, not declarations. None of
them reports a `!important` with its file and line, or
exits 1 for CI. This tool does that one job: a Python
standard-library-only CLI that finds `!important` in
CSS files — no install beyond Python, no website, no
network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/css-important-checker-cli.git
cd css-important-checker-cli
python3 src/css_important_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 declaration(s), none use !important
OK — 1 CSS file(s) checked, 12 declaration(s), none use !important.
```

## Usage

Check one clean stylesheet:

```
python3 src/css_important_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 declaration(s), none use !important
OK — 1 CSS file(s) checked, 12 declaration(s), none use !important.
```

Check a stylesheet that leans on `!important` — `color`
in `.card`, `margin` in `.btn` (written as `! important`),
`Padding` in `.title` (written as `!IMPORTANT`), `width`
in `.sidebar` inside the media query, `color` and
`background` together in `.alert`, and the custom property
`--brand` in `:root`:

```
python3 src/css_important_checker.py examples/messy.css
```

```
FAIL examples/messy.css:3: property 'color' uses '!important'
FAIL examples/messy.css:8: property 'margin' uses '!important'
FAIL examples/messy.css:13: property 'Padding' uses '!important'
FAIL examples/messy.css:19: property 'width' uses '!important'
FAIL examples/messy.css:24: property 'color' uses '!important'
FAIL examples/messy.css:25: property 'background' uses '!important'
FAIL examples/messy.css:29: property '--brand' uses '!important'
Checked 1 CSS file(s) (10 declaration(s)), 7 problem(s) in 1 file(s).
```

Check a whole folder:

```
python3 src/css_important_checker.py examples
```

```
examples/clean.css: OK — 12 declaration(s), none use !important
FAIL examples/messy.css:3: property 'color' uses '!important'
FAIL examples/messy.css:8: property 'margin' uses '!important'
FAIL examples/messy.css:13: property 'Padding' uses '!important'
FAIL examples/messy.css:19: property 'width' uses '!important'
FAIL examples/messy.css:24: property 'color' uses '!important'
FAIL examples/messy.css:25: property 'background' uses '!important'
FAIL examples/messy.css:29: property '--brand' uses '!important'
Checked 2 CSS file(s) (22 declaration(s)), 7 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/css_important_checker.py --json examples/messy.css
```

```
{
  "files": [
    {
      "file": "examples/messy.css",
      "declarations": 10,
      "problems": [
        {
          "file": "examples/messy.css",
          "line": 3,
          "reason": "property 'color' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 8,
          "reason": "property 'margin' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 13,
          "reason": "property 'Padding' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 19,
          "reason": "property 'width' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 24,
          "reason": "property 'color' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 25,
          "reason": "property 'background' uses '!important'"
        },
        {
          "file": "examples/messy.css",
          "line": 29,
          "reason": "property '--brand' uses '!important'"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "declarations": 10,
    "files_with_problems": 1,
    "problems": 7
  }
}
```

Exit codes: 0 when no declaration uses `!important`, 1
when any is found, 2 for a usage problem (no paths given,
a bad flag, or a missing file or folder).

## Examples

### 1. A clean stylesheet

`examples/clean.css` mentions `!important` in a comment
and inside a `content: "!important"` string — neither is
a declaration using it, so the file passes:

```
python3 src/css_important_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 declaration(s), none use !important
OK — 1 CSS file(s) checked, 12 declaration(s), none use !important.
```

### 2. A stylesheet with seven `!important` uses

`examples/messy.css` has seven uses across six rules,
including two in one rule, one inside a media query, one
written with a space (`! important`), and one written in
full capitals (`!IMPORTANT`):

```
python3 src/css_important_checker.py examples/messy.css
```

```
FAIL examples/messy.css:3: property 'color' uses '!important'
FAIL examples/messy.css:8: property 'margin' uses '!important'
FAIL examples/messy.css:13: property 'Padding' uses '!important'
FAIL examples/messy.css:19: property 'width' uses '!important'
FAIL examples/messy.css:24: property 'color' uses '!important'
FAIL examples/messy.css:25: property 'background' uses '!important'
FAIL examples/messy.css:29: property '--brand' uses '!important'
Checked 1 CSS file(s) (10 declaration(s)), 7 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the whole `examples/` folder (fail, on
purpose — the example stylesheet uses `!important` seven
times). Its full output is in
`examples/sample-output.md`, ending with `Checked 2 CSS
file(s) (22 declaration(s)), 7 problem(s) in 1 file(s).`
The failing run exits 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_css_important_checker.py
```

The tests cover: finding (one use with its exact report
line, several uses in one file, two uses in one rule, a
clean stylesheet, the same property flagged in different
rules, a use in a comment, a use in a multi-line comment,
a comment between declarations, a use in a double-quoted
string, a use in a single-quoted string, a string holding
`;` and `}`, a use in a selector attribute, upper- and
mixed-case `!IMPORTANT`, a space, two spaces, and a tab
between `!` and `important`, no space before the `!`,
`!important` on the next line reporting that line, an
empty file, a whitespace-only file, a comment-only file,
an unclosed block, a last declaration with no semicolon,
a declaration with no colon, an empty value, an extra
closing brace, a filename holding `!important` that is
not a use, `!important` as part of a longer word, a use
in a media-query rule, a use in a nested rule, a use in
a keyframe step, an `@import` line, a `;` inside a
`url(data:...)` value, line numbers across a multi-line
file, problems sorted by line, comment stripping keeping
line numbers, and string blanking keeping length), the
check itself (all clean, one use found with its exact
report line, an unreadable CSS file, several files in
path order), file collection (a folder walk, `.git`,
`__pycache__`, and `node_modules` skipped, `--no-recursive`,
`--exclude`, a direct CSS file checked alone, a direct
non-CSS file ignored, a missing path, an empty folder,
uppercase `.CSS` extensions, duplicate paths
deduplicated), the CLI (exit 0/1/2, `--json` output with
the summary on standard error, `--version`, bad flags,
missing paths, a folder summary count, a run from a
different working directory checked by path suffix, and
the `main` exit codes), the bundled examples (the messy
file's seven uses at their exact lines, the clean file
passing with 12 declarations, sample output compared
byte-for-byte against a fresh run, and the README-quoted
outputs checked against it, including the JSON block),
and hygiene checks (no placeholder text, no absolute
paths, stdlib imports only, `.env` first in `.gitignore`,
CI file checked with substring markers only).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking stylesheets is not new — the similar tools
named above (css-class-checker-cli for unused classes, and
css-duplicate-property-checker-cli for repeated properties)
are listed in "How this differs" — but every line of code
here is original, and the tool builds on nothing but
Python's standard library. The unused-classes job is
deliberately left to css-class-checker-cli, and the
duplicate-properties job to
css-duplicate-property-checker-cli, which own them.
