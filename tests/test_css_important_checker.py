"""Tests for css-important-checker-cli.

Standard library unittest only. The tests run from any working
directory: the repo root is found from this file's own location,
never from the current directory, and every assertion on a path
uses a suffix or a relative path, never an absolute one.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from css_important_checker import (  # noqa: E402
    blank_strings,
    check_files,
    collect,
    find_important,
    main,
    strip_comments,
)

SCRIPT = REPO_ROOT / "src" / "css_important_checker.py"
EXAMPLES = REPO_ROOT / "examples"


def problems_for(text, name="test.css"):
    """(problems, declaration_count) for one CSS document."""
    return find_important(text, name)


def reasons(text, name="test.css"):
    """Plain reason strings for one CSS document."""
    problems, _ = problems_for(text, name)
    return [problem.text() for problem in problems]


class TestFindImportant(unittest.TestCase):
    def test_single_important_found(self):
        problems, count = problems_for(
            ".card {\n  color: red !important;\n}\n")
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)
        self.assertEqual(
            problems[0].text(),
            "test.css:2: property 'color' uses '!important'")

    def test_multiple_important_in_one_file(self):
        text = (".a { color: red !important; }\n"
                ".b { margin: 0 !important; }\n"
                ".c { padding: 2px !important; }\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 3)
        self.assertEqual([p.line for p in problems], [1, 2, 3])
        self.assertEqual(
            [p.reason for p in problems],
            ["property 'color' uses '!important'",
             "property 'margin' uses '!important'",
             "property 'padding' uses '!important'"])

    def test_two_important_in_one_rule(self):
        text = (".alert {\n"
                "  color: red !important;\n"
                "  background: yellow !important;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 2)
        self.assertEqual([p.line for p in problems], [2, 3])

    def test_clean_css_passes(self):
        text = (".card {\n"
                "  color: red;\n"
                "  background: blue;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)

    def test_same_property_in_different_rules_both_flagged(self):
        text = (".a { color: red !important; }\n"
                ".b { color: blue !important; }\n")
        problems, _ = problems_for(text)
        self.assertEqual(len(problems), 2)

    def test_important_in_comment_ignored(self):
        text = ("/* color: red !important; */\n"
                ".a { color: red; }\n")
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 1)

    def test_important_in_multiline_comment_ignored(self):
        text = ("/*\n"
                "  color: red !important;\n"
                "  margin: 0 !important;\n"
                "*/\n"
                ".a { color: red; }\n")
        problems, _ = problems_for(text)
        self.assertEqual(problems, [])

    def test_comment_between_declarations_ignored(self):
        text = (".a {\n"
                "  color: red;\n"
                "  /* margin: 0 !important; */\n"
                "  padding: 2px;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)

    def test_important_in_double_quoted_string_ignored(self):
        text = ('.a {\n'
                '  content: "!important";\n'
                '  color: red;\n'
                '}\n')
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)

    def test_important_in_single_quoted_string_ignored(self):
        text = (".a {\n"
                "  content: '!important';\n"
                "  color: red;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 2)

    def test_string_holding_semicolon_and_brace(self):
        text = ('.a {\n'
                '  content: "; }";\n'
                '  color: red !important;\n'
                '}\n')
        problems, count = problems_for(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 3)

    def test_string_in_selector_attribute_ignored(self):
        text = ('a[href="!important"] {\n'
                '  color: red;\n'
                '}\n')
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 1)

    def test_uppercase_important(self):
        problems, _ = problems_for(".a { color: red !IMPORTANT; }\n")
        self.assertEqual(len(problems), 1)

    def test_mixed_case_important(self):
        problems, _ = problems_for(".a { color: red !Important; }\n")
        self.assertEqual(len(problems), 1)

    def test_space_between_bang_and_important(self):
        problems, _ = problems_for(".a { color: red ! important; }\n")
        self.assertEqual(len(problems), 1)

    def test_two_spaces_between_bang_and_important(self):
        problems, _ = problems_for(
            ".a { color: red !  important; }\n")
        self.assertEqual(len(problems), 1)

    def test_tab_between_bang_and_important(self):
        problems, _ = problems_for(
            ".a { color: red !\timportant; }\n")
        self.assertEqual(len(problems), 1)

    def test_no_space_before_bang(self):
        problems, _ = problems_for(".a { color: red!important; }\n")
        self.assertEqual(len(problems), 1)

    def test_important_on_next_line_reports_that_line(self):
        text = (".a {\n"
                "  color: red\n"
                "    !important;\n"
                "}\n")
        problems, _ = problems_for(text)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 3)

    def test_empty_file(self):
        problems, count = problems_for("")
        self.assertEqual(problems, [])
        self.assertEqual(count, 0)

    def test_whitespace_only_file(self):
        problems, count = problems_for("  \n\n  \n")
        self.assertEqual(problems, [])
        self.assertEqual(count, 0)

    def test_comment_only_file(self):
        problems, count = problems_for("/* nothing here */\n")
        self.assertEqual(problems, [])
        self.assertEqual(count, 0)

    def test_unclosed_block_still_reported(self):
        text = ".a { color: red !important;\n"
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)

    def test_last_declaration_without_semicolon(self):
        text = ".a {\n  color: red !important\n}\n"
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)

    def test_declaration_without_colon_ignored(self):
        text = ".a {\n  color red !important;\n  margin: 0;\n}\n"
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 1)

    def test_empty_value_ignored(self):
        text = ".a {\n  color:;\n  margin: 0 !important;\n}\n"
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)

    def test_extra_closing_brace_tolerated(self):
        text = ".a { color: red !important; }}\n"
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)

    def test_filename_holding_important_not_reported(self):
        text = ".a { background: url(x!important.png); }\n"
        problems, count = problems_for(text)
        self.assertEqual(problems, [])
        self.assertEqual(count, 1)

    def test_important_as_part_of_longer_word_not_reported(self):
        problems, _ = problems_for(
            ".a { content: important; color: red; }\n")
        self.assertEqual(problems, [])

    def test_important_followed_by_digit_not_reported(self):
        text = ".a { background: url(x!important2.png); }\n"
        problems, _ = problems_for(text)
        self.assertEqual(problems, [])

    def test_custom_property_flagged(self):
        text = ":root {\n  --brand: #06c !important;\n}\n"
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)
        self.assertIn("--brand", problems[0].reason)

    def test_vendor_prefixed_property_flagged(self):
        text = ".a { -webkit-transform: none !important; }\n"
        problems, _ = problems_for(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("-webkit-transform", problems[0].reason)

    def test_property_name_kept_as_written(self):
        text = ".a { Padding: 10px !IMPORTANT; }\n"
        problems, _ = problems_for(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("'Padding'", problems[0].reason)

    def test_important_in_media_query_rule(self):
        text = ("@media (min-width: 600px) {\n"
                "  .sidebar {\n"
                "    width: 200px !important;\n"
                "  }\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 3)

    def test_important_in_nested_rule(self):
        text = (".outer {\n"
                "  color: red;\n"
                "  .inner {\n"
                "    margin: 0 !important;\n"
                "  }\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 4)

    def test_important_in_keyframe_step(self):
        text = ("@keyframes fade {\n"
                "  from { opacity: 0; }\n"
                "  to { opacity: 1 !important; }\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 3)

    def test_import_line_not_a_declaration(self):
        problems, count = problems_for(
            '@import url("theme.css");\n.a { color: red; }\n')
        self.assertEqual(problems, [])
        self.assertEqual(count, 1)

    def test_semicolon_inside_url_value(self):
        text = (".a {\n"
                "  background: url(data:image/png;base64,AAA) "
                "!important;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 1)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 2)

    def test_line_numbers_across_multiline_file(self):
        text = (".a {\n"
                "  color: red;\n"
                "  margin: 0;\n"
                "}\n"
                "\n"
                ".b {\n"
                "  padding: 2px !important;\n"
                "}\n")
        problems, count = problems_for(text)
        self.assertEqual(count, 3)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].line, 7)

    def test_problems_sorted_by_line(self):
        text = (".b { padding: 2px !important; }\n"
                ".a { color: red !important; }\n")
        problems, _ = problems_for(text)
        self.assertEqual([p.line for p in problems], [1, 2])

    def test_strip_comments_keeps_line_numbers(self):
        text = "/* one\ntwo */\n.a { color: red; }\n"
        cleaned = strip_comments(text)
        self.assertEqual(cleaned.count("\n"), text.count("\n"))
        self.assertNotIn("one", cleaned)

    def test_blank_strings_keeps_length(self):
        text = '.a { content: "!important"; }\n'
        blanked = blank_strings(text)
        self.assertEqual(len(blanked), len(text))
        self.assertNotIn("!important", blanked)
        self.assertIn('"', blanked)


class TestCheckFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_all_clean(self):
        clean = self.write("clean.css", ".a { color: red; }\n")
        results, total = check_files([clean])
        self.assertEqual(total, 1)
        self.assertEqual(results[0][2], [])

    def test_problem_found_with_exact_report_line(self):
        messy = self.write(
            "messy.css", ".a { color: red !important; }\n")
        results, total = check_files([messy])
        self.assertEqual(total, 1)
        self.assertEqual(len(results[0][2]), 1)
        self.assertTrue(
            results[0][2][0].text().endswith(
                "messy.css:1: property 'color' uses '!important'"))

    def test_several_files_in_path_order(self):
        first = self.write("a.css", ".a { color: red; }\n")
        second = self.write("b.css", ".b { color: red !important; }\n")
        results, total = check_files([second, first])
        self.assertEqual(total, 2)
        self.assertEqual(results[0][0], second)
        self.assertEqual(results[1][0], first)

    def test_unreadable_css_file_reported(self):
        folder = self.dir / "broken.css"
        folder.mkdir()
        results, _ = check_files([str(folder)])
        self.assertEqual(len(results[0][2]), 1)
        self.assertIn("cannot read file", results[0][2][0].reason)


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text=".a { color: red; }\n"):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_folder_walk(self):
        self.write("a.css")
        self.write("sub/b.css")
        self.write("sub/c.txt")
        files, missing = collect([str(self.dir)])
        self.assertEqual(missing, [])
        self.assertEqual(
            [Path(f).name for f in files], ["a.css", "b.css"])

    def test_git_and_pycache_and_node_modules_skipped(self):
        self.write(".git/hooks/x.css")
        self.write("__pycache__/y.css")
        self.write("node_modules/z.css")
        self.write("keep.css")
        files, _ = collect([str(self.dir)])
        self.assertEqual([Path(f).name for f in files], ["keep.css"])

    def test_no_recursive(self):
        self.write("a.css")
        self.write("sub/b.css")
        files, _ = collect([str(self.dir)], recursive=False)
        self.assertEqual([Path(f).name for f in files], ["a.css"])

    def test_exclude_pattern(self):
        self.write("vendor.css")
        self.write("main.css")
        files, _ = collect([str(self.dir)], exclude=["vendor*"])
        self.assertEqual([Path(f).name for f in files], ["main.css"])

    def test_direct_file_always_checked(self):
        vendor = self.write("vendor.css")
        files, _ = collect([str(vendor)], exclude=["vendor*"])
        self.assertEqual(files, [str(vendor)])

    def test_direct_non_css_file_ignored(self):
        note = self.write("notes.txt")
        files, _ = collect([str(note)])
        self.assertEqual(files, [])

    def test_missing_path_reported(self):
        files, missing = collect([str(self.dir / "nope.css")])
        self.assertEqual(files, [])
        self.assertEqual(len(missing), 1)

    def test_empty_folder(self):
        files, missing = collect([str(self.dir)])
        self.assertEqual(files, [])
        self.assertEqual(missing, [])

    def test_uppercase_css_extension(self):
        upper = self.write("STYLE.CSS")
        files, _ = collect([str(self.dir)])
        self.assertEqual(files, [str(upper)])

    def test_duplicate_paths_deduplicated(self):
        path = self.write("a.css")
        files, _ = collect([str(path), str(path)])
        self.assertEqual(files, [str(path)])


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.clean = self.dir / "clean.css"
        self.clean.write_text(".a { color: red; }\n", encoding="utf-8")
        self.messy = self.dir / "messy.css"
        self.messy.write_text(
            ".a { color: red !important; }\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT)] + args,
            capture_output=True, text=True,
            cwd=cwd or str(self.dir))

    def test_exit_zero_clean(self):
        result = self.run_cli([str(self.clean)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("none use !important", result.stdout)

    def test_exit_one_important_found(self):
        result = self.run_cli([str(self.messy)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("uses '!important'", result.stdout)

    def test_exit_two_no_paths(self):
        result = self.run_cli([])
        self.assertEqual(result.returncode, 2)

    def test_exit_two_missing_path(self):
        result = self.run_cli([str(self.dir / "nope.css")])
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file or folder", result.stderr)

    def test_exit_two_no_css_files(self):
        result = self.run_cli([str(self.dir / "empty")])
        self.assertEqual(result.returncode, 2)

    def test_exit_two_bad_flag(self):
        result = self.run_cli(["--nope", str(self.clean)])
        self.assertEqual(result.returncode, 2)

    def test_version_flag(self):
        result = self.run_cli(["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)

    def test_json_output(self):
        result = self.run_cli(["--json", str(self.messy)])
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 1)
        self.assertEqual(payload["summary"]["checked"], 1)
        self.assertEqual(
            payload["files"][0]["problems"][0]["line"], 1)
        self.assertIn("Checked 1 CSS file(s)", result.stderr)
        self.assertNotIn("Checked", result.stdout)

    def test_json_clean_exit_zero(self):
        result = self.run_cli(["--json", str(self.clean)])
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_folder_summary_count(self):
        result = self.run_cli([str(self.dir)])
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Checked 2 CSS file(s) (2 declaration(s)), "
            "1 problem(s) in 1 file(s).", result.stdout)

    def test_run_from_other_directory_by_path_suffix(self):
        result = self.run_cli(
            [str(EXAMPLES / "messy.css")], cwd="/tmp")
        self.assertEqual(result.returncode, 1)
        self.assertIn("examples/messy.css:3:", result.stdout)

    def test_main_function_exit_codes(self):
        self.assertEqual(main([str(self.clean)]), 0)
        self.assertEqual(main([str(self.messy)]), 1)
        self.assertEqual(main([str(self.dir / "nope.css")]), 2)


class TestExamples(unittest.TestCase):
    def test_bundled_messy_has_seven_problems(self):
        problems, count = find_important(
            (EXAMPLES / "messy.css").read_text(encoding="utf-8"),
            "messy.css")
        self.assertEqual(count, 10)
        self.assertEqual(
            [p.line for p in problems], [3, 8, 13, 19, 24, 25, 29])

    def test_bundled_clean_passes(self):
        problems, count = find_important(
            (EXAMPLES / "clean.css").read_text(encoding="utf-8"),
            "clean.css")
        self.assertEqual(problems, [])
        self.assertEqual(count, 12)

    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(result.returncode, 0)
        sample = (EXAMPLES / "sample-output.md").read_text(
            encoding="utf-8")
        block = sample.split("```\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(block.strip(), result.stdout.strip())

    def test_readme_quoted_outputs_match_real_runs(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        clean = subprocess.run(
            [sys.executable, str(SCRIPT), "examples/clean.css"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertIn(clean.stdout.strip(), readme)
        messy = subprocess.run(
            [sys.executable, str(SCRIPT), "examples/messy.css"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertIn(messy.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, str(SCRIPT), "examples"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertIn(folder.stdout.strip(), readme)
        as_json = subprocess.run(
            [sys.executable, str(SCRIPT), "--json",
             "examples/messy.css"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertIn(as_json.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def repo_files(self):
        for root, dirs, names in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for name in names:
                path = Path(root) / name
                if "tests" in path.parts:
                    continue
                yield path

    def test_no_placeholder_text(self):
        banned = ("todo", "coming soon", "lorem")
        for path in self.repo_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for word in banned:
                self.assertNotIn(
                    word, text.lower(),
                    f"{path.name} contains placeholder text {word!r}")

    def test_no_absolute_local_paths(self):
        for path in self.repo_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in ("/home/", "/Users/", "C:\\"):
                self.assertNotIn(
                    marker, text,
                    f"{path.name} contains an absolute path {marker!r}")

    def test_stdlib_imports_only(self):
        tree = ast.parse(
            (REPO_ROOT / "src" / "css_important_checker.py")
            .read_text(encoding="utf-8"))
        stdlib = sys.stdlib_module_names
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], stdlib)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split(".")[0], stdlib)

    def test_env_first_line_of_gitignore(self):
        lines = (REPO_ROOT / ".gitignore").read_text(
            encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_file_markers(self):
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8")
        for marker in ("actions/checkout@v4",
                       "actions/setup-python@v5",
                       "3.12",
                       "tests/test_css_important_checker.py",
                       "push", "pull_request"):
            self.assertIn(marker, text)

    def test_licence_present(self):
        text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)


if __name__ == "__main__":
    unittest.main()
