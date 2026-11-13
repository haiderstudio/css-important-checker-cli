#!/bin/sh
# Run the checker on the bundled examples and show the report.
# The checker exits 1 because the example stylesheet uses
# !important seven times; that is the point of the examples,
# so this script exits 0.
cd "$(dirname "$0")/.." || exit 2
python3 src/css_important_checker.py examples || true
