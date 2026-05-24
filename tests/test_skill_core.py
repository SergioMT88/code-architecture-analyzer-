import json
import tempfile
import textwrap
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from code_analyzer.analyzer import run_analysis, prune_criteria  # noqa: E402
from code_analyzer.artifact_manager import ArtifactRegistry  # noqa: E402
from code_analyzer.refactorer import RefactoringOrchestrator, refactor_file  # noqa: E402
from code_analyzer.report_generator import ReportGenerator  # noqa: E402


class SkillCoreTests(unittest.TestCase):
    def test_artifact_registry_builds_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("print('hi')\n", encoding="utf-8")

            registry = ArtifactRegistry(source, output_dir=tmp, structured_outputs=True)
            self.assertTrue(registry.run_root.exists())
            self.assertTrue(registry.analysis_dir.exists())
            self.assertTrue(registry.reports_dir.exists())
            self.assertTrue(registry.backups_dir.exists())

            manifest_path = registry.save_manifest({"ok": True})
            self.assertTrue(manifest_path.exists())

    def test_useless_fstring_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text('print("hi")\n', encoding="utf-8")
            orchestrator = RefactoringOrchestrator(str(source), dry_run=True, output_dir=tmp)

            fixed = orchestrator._fix_useless_fstrings('msg = f"hello"\n', [])
            self.assertIn("hello", fixed)
            self.assertNotIn('f"hello"', fixed)

    def test_partial_import_cleanup_keeps_alias_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("print('hi')\n", encoding="utf-8")
            orchestrator = RefactoringOrchestrator(str(source), dry_run=True, output_dir=tmp)

            code = "from m import a, b\nprint(a)\n"
            cleaned = orchestrator._remove_unused_imports(code, [])
            self.assertIn("from m import a, b", cleaned)
            self.assertIn("print(a)", cleaned)

    def test_ignore_criteria_skips_srp(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Demo:\n"
                "    def a(self):\n"
                "        return 1\n"
                "    def b(self):\n"
                "        return 2\n"
                "    def c(self):\n"
                "        return 3\n"
                "    def d(self):\n"
                "        return 4\n"
                "    def e(self):\n"
                "        return 5\n"
                "    def f(self):\n"
                "        return 6\n"
                "    def g(self):\n"
                "        return 7\n"
                "    def h(self):\n"
                "        return 8\n"
                "    def i(self):\n"
                "        return 9\n"
                "    def j(self):\n"
                "        return 10\n"
                "    def k(self):\n"
                "        return 11\n",
                encoding="utf-8",
            )

            result = run_analysis(str(source), {"ignore_criteria": ["SRP"]})
            self.assertTrue(result["success"])
            self.assertNotIn("SRP", result["criteria"])

    def test_circular_dependency_detection_reports_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a_file = root / "a.py"
            b_file = root / "b.py"

            a_file.write_text(
                "from b import helper\n\n"
                "def entry():\n"
                "    return helper()\n",
                encoding="utf-8",
            )
            b_file.write_text(
                "from a import entry\n\n"
                "def helper():\n"
                "    return entry()\n",
                encoding="utf-8",
            )

            result = run_analysis(str(a_file), {})
            self.assertTrue(result["success"])
            circular = result["criteria"]["CircularDeps"]["findings"]
            self.assertTrue(circular)
            self.assertIn("a -> b -> a", circular[0]["issue"])

    def test_design_patterns_detection_reports_explicit_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class User:\n"
                "    pass\n\n"
                "class UserFactory:\n"
                "    def create(self):\n"
                "        return User()\n",
                encoding="utf-8",
            )

            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DesignPatterns"]["findings"]
            self.assertTrue(findings)
            self.assertIn("Factory", findings[0]["issue"])

    def test_comment_ratio_target_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def foo():\n"
                "    return 1\n",
                encoding="utf-8",
            )

            result = run_analysis(str(source), {"min_comment_ratio": 50})
            self.assertTrue(result["success"])
            metrics = result["metrics"]
            self.assertEqual(metrics["comment_ratio_target"], 50)
            self.assertFalse(metrics["comment_ratio_ok"])

    def test_report_generator_exposes_action_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Demo:\n"
                "    def run(self):\n"
                "        return 1\n",
                encoding="utf-8",
            )

            analysis = {
                "metrics": {
                    "lines_of_code": 10,
                    "code_lines": 8,
                    "comment_lines": 0,
                    "blank_lines": 2,
                    "num_classes": 1,
                    "num_functions": 1,
                    "num_imports": 0,
                    "avg_cyclomatic_complexity": 1.0,
                    "max_cyclomatic_complexity": 1,
                    "maintainability_index": 90.0,
                    "maintainability_grade": "A",
                    "comment_ratio": 0,
                },
                "criteria": {
                    "SRP": {
                        "score": 4,
                        "status": "FAIL",
                        "description": "Class concentra responsabilidades demais.",
                        "severity": "ALTA",
                        "findings": [
                            {
                                "location": "sample.py:1",
                                "issue": "Classe muito ampla",
                                "suggestion": "Separar responsabilidades em classes menores.",
                                "severity": "ALTA",
                            }
                        ],
                    },
                    "Coupling": {
                        "score": 6,
                        "status": "WARN",
                        "description": "Dependencias cruzadas entre modulos.",
                        "severity": "MEDIA",
                        "findings": [
                            {
                                "location": "sample.py:2",
                                "issue": "Acoplamento elevado",
                                "suggestion": "Reduzir dependencias entre modulos.",
                                "severity": "MEDIA",
                            }
                        ],
                    },
                },
                "dependencies": {},
                "test_analysis": {
                    "test_functions": 0,
                    "test_classes": 0,
                    "uses_pytest": True,
                    "estimated_coverage": 0,
                    "missing_tests": [
                        "load_user",
                        "save_user",
                        "delete_user",
                        "update_user",
                    ],
                },
                "tool_findings": {},
                "config": {},
            }

            generator = ReportGenerator(str(source), analysis, output_dir=tmp)
            report_json = generator.generate_json_report()
            report_md = generator.generate_markdown_report()

            self.assertIn("action_summary", report_json)
            self.assertEqual(report_json["action_summary"]["top_actions"][0]["title"], "SRP")
            self.assertGreaterEqual(report_json["action_summary"]["total_actions"], 3)
            self.assertIn("Proximas Acoes", report_md)
            self.assertIn("Decisao rapida", report_md)
            self.assertIn("Separar responsabilidades", report_md)

    def test_report_generator_save_reports_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("print('x')\n", encoding="utf-8")

            analysis = {
                "metrics": {
                    "lines_of_code": 1,
                    "code_lines": 1,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "num_classes": 0,
                    "num_functions": 0,
                    "num_imports": 0,
                    "avg_cyclomatic_complexity": 1.0,
                    "max_cyclomatic_complexity": 1,
                    "maintainability_index": 100.0,
                    "maintainability_grade": "A",
                    "comment_ratio": 0,
                },
                "criteria": {},
                "dependencies": {},
                "test_analysis": {},
                "tool_findings": {},
                "config": {},
            }

            generator = ReportGenerator(str(source), analysis, output_dir=tmp)
            files = generator.save_reports(tmp)

            json_path = Path(files["json_report"])
            md_path = Path(files["markdown_report"])
            manifest_path = Path(files["manifest"])

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertTrue(manifest_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
            self.assertIn("analysis", kinds)
            self.assertIn("report", kinds)
            self.assertIn("summary", manifest)
            self.assertEqual(
                manifest["summary"]["analysis_file"],
                str(json_path),
            )

    def test_report_generator_fails_safe_on_empty_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("print('x')\n", encoding="utf-8")

            analysis = {
                "metrics": {
                    "lines_of_code": 1,
                    "code_lines": 1,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "num_classes": 0,
                    "num_functions": 0,
                    "num_imports": 0,
                    "avg_cyclomatic_complexity": 1.0,
                    "max_cyclomatic_complexity": 1,
                    "maintainability_index": 100.0,
                    "maintainability_grade": "A",
                    "comment_ratio": 0,
                },
                "criteria": {},
                "dependencies": {},
                "test_analysis": {},
                "tool_findings": {},
                "config": {},
            }

            generator = ReportGenerator(str(source), analysis, output_dir=tmp)
            generator.generate_markdown_report = lambda: ""

            result = generator.save_reports(tmp)

            self.assertIn("error", result)
            self.assertIn("log_file", result)
            self.assertTrue(Path(result["log_file"]).exists())
            md_path = Path(result["markdown_report"]) if "markdown_report" in result else generator.artifacts.path_for("report", f"{source.stem}_report.md")
            self.assertFalse(md_path.exists() and md_path.stat().st_size == 0)

    def test_refactor_dry_run_keeps_source_unchanged_and_returns_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            original = "def ok():\n    return 1\n"
            source.write_text(original, encoding="utf-8")

            result = refactor_file(
                str(source),
                dry_run=True,
                output_dir=tmp,
                quiet=True,
            )

            self.assertIsNotNone(result)
            self.assertTrue(result["dry_run"])
            self.assertIn("manifest", result)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertTrue(Path(result["manifest"]).exists())

    def test_refactor_aborts_without_overwriting_source_on_invalid_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            original = "def ok():\n    return 1\n"
            source.write_text(original, encoding="utf-8")

            orchestrator = RefactoringOrchestrator(
                str(source),
                dry_run=False,
                output_dir=tmp,
                quiet=True,
            )

            def inject_invalid_code():
                orchestrator.code = "def broken(\n"
                return {"status": "success", "changes_found": 0, "changes_detail": []}

            with patch.object(
                orchestrator,
                "phase2_refactor_structure",
                side_effect=inject_invalid_code,
            ), patch.object(
                orchestrator,
                "phase3_tests",
                return_value={"status": "skipped"},
            ), patch.object(
                orchestrator,
                "phase4_formatting",
                return_value={"status": "success", "tools_used": []},
            ):
                result = orchestrator.execute_refactoring()

            self.assertIn("error", result)
            self.assertIn("manifest", result)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertTrue(Path(result["manifest"]).exists())

    def test_bare_except_detection_reports_bare_except(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def handler():\n"
                "    try:\n"
                "        risky()\n"
                "    except:\n"
                "        pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["BareExcept"]["findings"]
            self.assertTrue(findings)
            self.assertIn("Except sem tipo", findings[0]["issue"])

    def test_bare_except_ignores_typed_except(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def handler():\n"
                "    try:\n"
                "        risky()\n"
                "    except ValueError:\n"
                "        pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["BareExcept"]["findings"]
            self.assertFalse(findings)

    def test_none_comparison_detects_eq_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def check(x):\n"
                "    return x == None\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["NoneComparison"]["findings"]
            self.assertTrue(findings)
            self.assertIn("==", findings[0]["issue"])

    def test_none_comparison_detects_ne_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def check(x):\n"
                "    return x != None\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["NoneComparison"]["findings"]
            self.assertTrue(findings)
            self.assertIn("!=", findings[0]["issue"])

    def test_none_comparison_ignores_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def check(x):\n"
                "    return x is None\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["NoneComparison"]["findings"]
            self.assertFalse(findings)

    def test_none_comparison_ignores_assert(self):
        """v6.1.0 FP fix: `assert x == None` is an explicit assertion, not a bug."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def check(x):\n"
                "    assert x == None\n"
                "    assert x != None\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["NoneComparison"]["findings"]
            self.assertFalse(findings)

    def test_mutable_default_detects_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def append(item, lst=[]):\n"
                "    lst.append(item)\n"
                "    return lst\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["MutableDefault"]["findings"]
            self.assertTrue(findings)
            self.assertIn("Argumento mutavel", findings[0]["issue"])

    def test_mutable_default_detects_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def cache(key, store={}):\n"
                "    return store.get(key)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["MutableDefault"]["findings"]
            self.assertTrue(findings)

    def test_mutable_default_ignores_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def inc(x, delta=1):\n"
                "    return x + delta\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["MutableDefault"]["findings"]
            self.assertFalse(findings)

    def test_shadowing_builtins_detects_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("list = [1, 2, 3]\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ShadowingBuiltins"]["findings"]
            self.assertTrue(findings)
            self.assertIn("list", findings[0]["issue"])

    def test_shadowing_builtins_detects_parameter(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(id, data):\n"
                "    return id\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ShadowingBuiltins"]["findings"]
            self.assertTrue(findings)
            self.assertIn("id", findings[0]["issue"])

    def test_shadowing_builtins_ignores_normal_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(user_id, data):\n"
                "    return user_id\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ShadowingBuiltins"]["findings"]
            self.assertFalse(findings)

    def test_wildcard_import_detects_from_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("from os import *\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["WildcardImport"]["findings"]
            self.assertTrue(findings)
            self.assertIn("import *", findings[0]["issue"])

    def test_wildcard_import_ignores_normal_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("import os\nfrom os import path\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["WildcardImport"]["findings"]
            self.assertFalse(findings)

    def test_many_parameters_detects_7_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(a, b, c, d, e, f, g): pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ManyParameters"]["findings"]
            self.assertTrue(findings)
            self.assertIn("7 parameters", findings[0]["issue"])

    def test_many_parameters_ignores_6_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def ok(a, b, c, d, e, f): pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ManyParameters"]["findings"]
            self.assertFalse(findings)

    def test_many_parameters_detects_with_var_positional(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def lots(a, b, c, d, e, f, *args, **kwargs): pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ManyParameters"]["findings"]
            self.assertTrue(findings)
            self.assertIn("8 parameters", findings[0]["issue"])

    def test_security_detects_eval(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("eval('__import__(\"os\").system(\"ls\")')\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Security"]["findings"]
            self.assertTrue(findings)
            self.assertIn("eval()", findings[0]["issue"])

    def test_security_detects_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("exec('import os')\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Security"]["findings"]
            self.assertTrue(findings)
            self.assertIn("exec()", findings[0]["issue"])

    def test_security_detects_pickle_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("import pickle\ndata = pickle.load(open('x.pkl', 'rb'))\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Security"]["findings"]
            self.assertTrue(findings)
            self.assertIn("pickle.load()", findings[0]["issue"])

    def test_security_detects_input_without_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("x = input()\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Security"]["findings"]
            input_findings = [f for f in findings if "input()" in f["issue"]]
            self.assertTrue(input_findings)

    def test_security_ignores_input_with_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("x = input('Digite algo: ')\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Security"]["findings"]
            input_findings = [f for f in findings if "input()" in f["issue"]]
            self.assertFalse(input_findings)

    def test_async_sync_detects_no_await(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "async def no_await():\n"
                "    return 42\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AsyncSyncMismatch"]["findings"]
            self.assertTrue(findings)
            self.assertIn("nao usa await", findings[0]["issue"])

    def test_async_sync_ignores_async_with_await(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "async def fetch():\n"
                "    return await some_async()\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AsyncSyncMismatch"]["findings"]
            self.assertFalse(findings)

    def test_async_sync_detects_await_in_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def sync_func():\n"
                "    return await something()\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AsyncSyncMismatch"]["findings"]
            self.assertTrue(findings)
            self.assertIn("await usado fora", findings[0]["issue"])

    def test_redundant_if_return_detects_true_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def is_active(user):\n"
                "    if user:\n"
                "        return True\n"
                "    else:\n"
                "        return False\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["RedundantIfReturn"]["findings"]
            self.assertTrue(findings)
            self.assertIn("return True/False", findings[0]["issue"])

    def test_redundant_if_return_detects_false_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def is_disabled(user):\n"
                "    if user:\n"
                "        return False\n"
                "    else:\n"
                "        return True\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["RedundantIfReturn"]["findings"]
            self.assertTrue(findings)
            self.assertIn("return False/True", findings[0]["issue"])

    def test_redundant_if_return_ignores_complex_branches(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def check(x):\n"
                "    if x:\n"
                "        print('ok')\n"
                "        return True\n"
                "    else:\n"
                "        return False\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["RedundantIfReturn"]["findings"]
            self.assertFalse(findings)

    def test_unused_variable_detects_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process():\n"
                "    unused_var = 42\n"
                "    return True\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedVariable"]["findings"]
            self.assertTrue(findings)
            self.assertIn("unused_var", findings[0]["issue"])

    def test_unused_variable_ignores_used_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process():\n"
                "    x = 42\n"
                "    return x\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedVariable"]["findings"]
            self.assertFalse(findings)

    def test_unused_variable_ignores_underscore(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process():\n"
                "    _ = 42\n"
                "    return True\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedVariable"]["findings"]
            self.assertFalse(findings)

    def test_unused_variable_ignores_tuple_unpack_in_for(self):
        """v6.1.0 FP fix: `for name, val in items.items()` — `name` as documentation."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(items):\n"
                "    for name, val in items.items():\n"
                "        print(val)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedVariable"]["findings"]
            self.assertFalse(findings)

    def test_inconsistent_returns_detects_int_vs_str(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def get_val(x):\n"
                "    if x:\n"
                "        return 42\n"
                "    return 'erro'\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["InconsistentReturns"]["findings"]
            self.assertTrue(findings)
            self.assertIn("int", findings[0]["issue"])
            self.assertIn("str", findings[0]["issue"])

    def test_inconsistent_returns_ignores_single_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def get_val(x):\n"
                "    if x:\n"
                "        return 1\n"
                "    return 0\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["InconsistentReturns"]["findings"]
            self.assertFalse(findings)

    def test_range_len_loop_detects_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(items):\n"
                "    for i in range(len(items)):\n"
                "        print(items[i])\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["RangeLenLoop"]["findings"]
            self.assertTrue(findings)
            self.assertIn("range(len(", findings[0]["issue"])

    def test_range_len_loop_ignores_normal_for(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process(items):\n"
                "    for item in items:\n"
                "        print(item)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["RangeLenLoop"]["findings"]
            self.assertFalse(findings)

    def test_dot_keys_detects_in_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "if 'x' in d.keys():\n"
                "    print('found')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DotKeys"]["findings"]
            self.assertTrue(findings)
            self.assertIn(".keys()", findings[0]["issue"])

    def test_dot_keys_ignores_normal_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "if 'x' in d:\n"
                "    print('found')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DotKeys"]["findings"]
            self.assertFalse(findings)

    def test_string_concat_in_loop_aug_assign(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def build(items):\n"
                "    s = ''\n"
                "    for x in items:\n"
                "        s += str(x)\n"
                "    return s\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringConcatInLoop"]["findings"]
            self.assertTrue(findings)
            self.assertIn("dentro de loop", findings[0]["issue"])

    def test_string_concat_in_loop_bin_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def build(items):\n"
                "    s = ''\n"
                "    for x in items:\n"
                "        s = s + str(x)\n"
                "    return s\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringConcatInLoop"]["findings"]
            self.assertTrue(findings)
            self.assertIn("dentro de loop", findings[0]["issue"])

    def test_string_concat_in_loop_ignores_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def build(items):\n"
                "    return ''.join(str(x) for x in items)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringConcatInLoop"]["findings"]
            self.assertFalse(findings)

    def test_any_all_list_comp_detects_any(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = any([x for x in items if x > 0])\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AnyAllListComp"]["findings"]
            self.assertTrue(findings)
            self.assertIn("any(", findings[0]["issue"])

    def test_any_all_list_comp_ignores_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = any(x for x in items if x > 0)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AnyAllListComp"]["findings"]
            self.assertFalse(findings)

    def test_deep_nesting_detects_4_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "for a in xs:\n"
                "    for b in ys:\n"
                "        for c in zs:\n"
                "            for d in ws:\n"
                "                print(d)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DeepNesting"]["findings"]
            self.assertTrue(findings)
            self.assertIn("3 niveis", findings[0]["issue"])

    def test_deep_nesting_ignores_3_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "for a in xs:\n"
                "    for b in ys:\n"
                "        for c in zs:\n"
                "            print(c)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DeepNesting"]["findings"]
            self.assertFalse(findings)

    def test_type_isinstance_detects_eq(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "if type(x) == str:\n"
                "    print('string')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["TypeIsInstance"]["findings"]
            self.assertTrue(findings)
            self.assertIn("type(...)", findings[0]["issue"])

    def test_type_isinstance_ignores_isinstance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "if isinstance(x, str):\n"
                "    print('string')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["TypeIsInstance"]["findings"]
            self.assertFalse(findings)

    def test_unused_iteration_var_detects_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = [do_something() for x in items]\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedIterationVar"]["findings"]
            self.assertTrue(findings)
            self.assertIn("does not use", findings[0]["issue"])

    def test_unused_iteration_var_ignores_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = [x.upper() for x in items]\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["UnusedIterationVar"]["findings"]
            self.assertFalse(findings)

    def test_dict_get_detects_bare_subscript(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "import json\n"
                "data = json.loads(raw)\n"
                "value = data['a']\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DictGet"]["findings"]
            self.assertTrue(findings)
            self.assertIn("Use 'data.get(", findings[0]["suggestion"])

    def test_dict_get_ignores_when_get_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "import json\n"
                "data = json.loads(raw)\n"
                "value = data.get('a')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DictGet"]["findings"]
            self.assertFalse(findings)

    def test_dict_get_ignores_internal_dict_literals(self):
        """v6.1.0 FP fix: internal dict literals should NOT be flagged — keys are known."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "data = {'a': 1, 'b': 2}\n"
                "value = data['a']\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DictGet"]["findings"]
            self.assertFalse(findings)

    def test_manual_accumulate_detects_list_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = []\n"
                "for x in items:\n"
                "    result.append(x * 2)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ManualAccumulate"]["findings"]
            self.assertTrue(findings)
            self.assertIn("append", findings[0]["issue"])

    def test_manual_accumulate_ignores_complex_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "result = []\n"
                "for x in items:\n"
                "    result.append(x)\n"
                "    print('log')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ManualAccumulate"]["findings"]
            self.assertFalse(findings)

    def test_print_leak_detects_print_in_logic(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def calculate(x):\n"
                "    print(f'calculating {x}')\n"
                "    return x * 2\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["PrintLeak"]["findings"]
            self.assertTrue(findings)
            self.assertIn("print() inside", findings[0]["issue"])

    def test_print_leak_ignores_print_in_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def main():\n"
                "    print('hello')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["PrintLeak"]["findings"]
            self.assertFalse(findings)

    def test_print_leak_ignores_module_level_print(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "print('module loaded')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["PrintLeak"]["findings"]
            self.assertFalse(findings)

    def test_tool_warnings_included_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("x = 1\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            if "tool_warnings" in result:
                for w in result["tool_warnings"]:
                    self.assertIn("nao instalado", w)

    def test_cli_json_mode_returns_machine_readable_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def ok():\n"
                "    return 1\n",
                encoding="utf-8",
            )

            analyze_cmd = [
                "python",
                "bin/cli.py",
                "analyze",
                str(source),
                "--no-refactor",
                "--quiet",
                "--json",
            ]
            analyze_result = subprocess.run(
                analyze_cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                analyze_result.returncode,
                0,
                msg=f"stdout={analyze_result.stdout}\nstderr={analyze_result.stderr}",
            )
            analyze_payload = json.loads(analyze_result.stdout)
            self.assertTrue(analyze_payload["success"])
            self.assertEqual(analyze_payload["mode"]["no_refactor"], True)
            self.assertIn("report_files", analyze_payload)

            validate_cmd = [
                "python",
                "bin/cli.py",
                "validate",
                str(source),
                "--json",
            ]
            validate_result = subprocess.run(
                validate_cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                validate_result.returncode,
                0,
                msg=f"stdout={validate_result.stdout}\nstderr={validate_result.stderr}",
            )
            validate_payload = json.loads(validate_result.stdout)
            self.assertTrue(validate_payload["status"] == "success")
            self.assertIn("validations", validate_payload)

    def test_cli_json_info_version_init(self):
        cli_py = str(ROOT / "bin" / "cli.py")
        with tempfile.TemporaryDirectory() as tmp:
            # --version --json
            ver_cmd = ["python", cli_py, "--version", "--json"]
            ver_result = subprocess.run(
                ver_cmd, cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(ver_result.returncode, 0)
            ver_payload = json.loads(ver_result.stdout)
            self.assertTrue(ver_payload["success"])
            self.assertIn("version", ver_payload)

            # info --json
            info_cmd = ["python", cli_py, "info", "--json"]
            info_result = subprocess.run(
                info_cmd, cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(info_result.returncode, 0)
            info_payload = json.loads(info_result.stdout)
            self.assertTrue(info_payload["success"])
            self.assertIn("version", info_payload)
            self.assertIn("python", info_payload)
            self.assertIn("platform", info_payload)

            # init --json (em dir temporario)
            init_cmd = ["python", cli_py, "init", "--json"]
            init_result = subprocess.run(
                init_cmd, cwd=tmp, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(init_result.returncode, 0)
            init_payload = json.loads(init_result.stdout)
            self.assertTrue(init_payload["success"])
            self.assertIn(".analyzer.json", init_payload.get("analyzer_config", ""))
            self.assertIn("project_type", init_payload)

            # init novamente (ja existe) --json — deve manter arquivos e retornar success
            init2_result = subprocess.run(
                init_cmd, cwd=tmp, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(init2_result.returncode, 0)
            init2_payload = json.loads(init2_result.stdout)
            self.assertTrue(init2_payload["success"])
            self.assertFalse(init2_payload["analyzer_config_created"])

            source = Path(tmp) / "sample.py"
            source.write_text("x = 1\n", encoding="utf-8")
            # check --json (deve ter mesma saida que analyze --no-refactor --json)
            check_cmd = ["python", cli_py, "check", str(source), "--quiet", "--json"]
            check_result = subprocess.run(
                check_cmd, cwd=tmp, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(check_result.returncode, 0)
            check_payload = json.loads(check_result.stdout)
            self.assertTrue(check_payload["success"])
            self.assertTrue(check_payload["mode"]["no_refactor"])

    def test_prune_criteria_removes_empty_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("x = 1\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            full_count = len(result["criteria"])
            pruned = prune_criteria(result)
            pruned_count = len(pruned["criteria"])
            self.assertLess(pruned_count, full_count)
            # verify all remaining criteria have findings
            for k, v in pruned["criteria"].items():
                self.assertTrue(v.get("findings"), f"{k} should have findings")
            # verify analysis still has report_files etc.
            if "report_files" in result:
                self.assertIn("report_files", pruned)
            if "metrics" in result:
                self.assertIn("metrics", pruned)

    def test_prune_criteria_keeps_all_with_findings(self):
        mock_analysis = {
            "success": True,
            "criteria": {
                "SRP": {"score": 10, "findings": []},
                "PrintLeak": {"score": 4, "findings": [{"issue": "print in logic"}]},
            },
            "metrics": {"complexity": 5},
        }
        pruned = prune_criteria(mock_analysis)
        self.assertNotIn("SRP", pruned["criteria"])
        self.assertIn("PrintLeak", pruned["criteria"])

    def test_prune_criteria_handles_edge_cases(self):
        pruned_empty = prune_criteria({})
        self.assertEqual(pruned_empty.get("criteria", {}), {})
        self.assertEqual(prune_criteria({"criteria": {}}), {"criteria": {}})
        self.assertEqual(prune_criteria(None), None)
        self.assertEqual(prune_criteria("string"), "string")

    def test_load_config_from_pyproject_toml(self):
        from code_analyzer.config import load_config
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "app.py"
            source.write_text("x = 1\n", encoding="utf-8")
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text(
                '[tool.code-analyzer]\n'
                'max_methods_per_class = 5\n'
                'ignore_criteria = ["PrintLeak"]\n',
                encoding="utf-8",
            )
            config = load_config(str(source), quiet=True)
            self.assertEqual(config["max_methods_per_class"], 5)
            self.assertIn("PrintLeak", config["ignore_criteria"])
            self.assertEqual(config["max_lines_per_class"], 200)

    def test_load_config_json_overrides_toml(self):
        from code_analyzer.config import load_config
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "app.py"
            source.write_text("x = 1\n", encoding="utf-8")
            toml = Path(tmp) / "pyproject.toml"
            toml.write_text(
                '[tool.code-analyzer]\n'
                'max_methods_per_class = 99\n',
                encoding="utf-8",
            )
            json_cfg = Path(tmp) / ".analyzer.json"
            json_cfg.write_text(
                '{"max_methods_per_class": 42}\n',
                encoding="utf-8",
            )
            config = load_config(str(source), quiet=True)
            self.assertEqual(config["max_methods_per_class"], 42)

    def test_missing_super_init_detects_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Base:\n"
                "    def __init__(self):\n"
                "        self.x = 0\n"
                "class Child(Base):\n"
                "    def __init__(self):\n"
                "        self.y = 1\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["MissingSuperInit"]["findings"]
            self.assertTrue(findings)

    def test_missing_super_init_ignores_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Base:\n"
                "    def __init__(self):\n"
                "        self.x = 0\n"
                "class Child(Base):\n"
                "    def __init__(self):\n"
                "        super().__init__()\n"
                "        self.y = 1\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["MissingSuperInit"]["findings"]
            self.assertFalse(findings)

    def test_override_signature_mismatch_detects(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Parent:\n"
                "    def method(self, a, b):\n"
                "        return a + b\n"
                "class Child(Parent):\n"
                "    def method(self, x):\n"
                "        return x\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["OverrideSignatureMismatch"]["findings"]
            self.assertTrue(findings)

    def test_override_signature_ignores_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Parent:\n"
                "    def method(self, a, b):\n"
                "        return a + b\n"
                "class Child(Parent):\n"
                "    def method(self, a, b):\n"
                "        return a * b\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["OverrideSignatureMismatch"]["findings"]
            self.assertFalse(findings)

    def test_abstract_method_not_implemented_detects(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "from abc import ABC, abstractmethod\n"
                "class AbstractBase(ABC):\n"
                "    @abstractmethod\n"
                "    def doit(self):\n"
                "        pass\n"
                "class ConcreteBad(AbstractBase):\n"
                "    pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AbstractMethodNotImplemented"]["findings"]
            self.assertTrue(findings)

    def test_abstract_method_ignores_implemented(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "from abc import ABC, abstractmethod\n"
                "class AbstractBase(ABC):\n"
                "    @abstractmethod\n"
                "    def doit(self):\n"
                "        pass\n"
                "class ConcreteOk(AbstractBase):\n"
                "    def doit(self):\n"
                "        return 42\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["AbstractMethodNotImplemented"]["findings"]
            self.assertFalse(findings)

    def test_string_concat_in_loop_ignores_numeric_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def calculate(items):\n"
                "    complexity = 0\n"
                "    for x in items:\n"
                "        complexity += 1\n"
                "    return complexity\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringConcatInLoop"]["findings"]
            self.assertFalse(findings)

    def test_string_concat_in_loop_ignores_list_accumulator(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def collect(items):\n"
                "    accumulator = []\n"
                "    for x in items:\n"
                "        accumulator += [x]\n"
                "    return accumulator\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringConcatInLoop"]["findings"]
            self.assertFalse(findings)

    def test_dict_get_ignores_type_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "from typing import Dict, List\n"
                "def process(data: Dict[str, int]) -> List[str]:\n"
                "    x: Dict[str, int] = {}\n"
                "    return list(data.keys())\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DictGet"]["findings"]
            self.assertFalse(findings)

    def test_dict_get_ignores_class_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "from typing import Generic, TypeVar\n"
                "T = TypeVar('T')\n"
                "class MyCollection(Generic[T]):\n"
                "    pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DictGet"]["findings"]
            self.assertFalse(findings)

    def test_deep_nesting_ignores_try_except_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "if cond1:\n"
                "    if cond2:\n"
                "        try:\n"
                "            if cond3:\n"
                "                pass\n"
                "        except:\n"
                "            pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DeepNesting"]["findings"]
            self.assertFalse(findings)

    def test_deep_nesting_still_detects_real_nesting_inside_try(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "try:\n"
                "    if cond1:\n"
                "        if cond2:\n"
                "            if cond3:\n"
                "                if cond4:\n"
                "                    pass\n"
                "except:\n"
                "    pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["DeepNesting"]["findings"]
            self.assertTrue(findings)

    def test_coupling_ignores_standard_library_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            imports_code = "\n".join(f"import {mod}" for mod in [
                "os", "sys", "json", "re", "math", "datetime", "pathlib", "typing",
                "collections", "itertools", "functools", "abc", "io", "time", "copy",
                "shutil", "subprocess", "threading", "asyncio", "logging", "unittest",
                "dataclasses", "enum", "tempfile", "ast"
            ])
            source.write_text(
                imports_code + "\n"
                "class Empty:\n"
                "    pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"max_imports": 20})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Coupling"]["findings"]
            self.assertFalse(findings)

    def test_coupling_detects_real_external_imports_excess(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            imports_code = "\n".join(f"import {mod}" for mod in [
                "requests", "flask", "django", "numpy", "pandas", "sqlalchemy"
            ])
            source.write_text(
                imports_code + "\n"
                "class Empty:\n"
                "    pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"max_imports": 5})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Coupling"]["findings"]
            self.assertTrue(findings)

    def test_cohesion_ignores_small_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class SmallClass:\n"
                "    def __init__(self):\n"
                "        self.a1 = 1\n"
                "        self.a2 = 2\n"
                "        self.a3 = 3\n"
                "        self.a4 = 4\n"
                "        self.a5 = 5\n"
                "        self.a6 = 6\n"
                "        self.a7 = 7\n"
                "        self.a8 = 8\n"
                "        self.a9 = 9\n"
                "        self.a10 = 10\n"
                "    def method1(self):\n"
                "        pass\n"
                "    def method2(self):\n"
                "        pass\n"
                "    def method3(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"min_cohesion_methods": 5})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Cohesion"]["findings"]
            self.assertFalse(findings)

    def test_cohesion_detects_low_cohesion_in_large_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class LargeClass:\n"
                "    def __init__(self):\n"
                "        self.a1 = 1\n"
                "        self.a2 = 2\n"
                "        self.a3 = 3\n"
                "        self.a4 = 4\n"
                "        self.a5 = 5\n"
                "        self.a6 = 6\n"
                "    def m1(self):\n"
                "        pass\n"
                "    def m2(self):\n"
                "        pass\n"
                "    def m3(self):\n"
                "        pass\n"
                "    def m4(self):\n"
                "        pass\n"
                "    def m5(self):\n"
                "        pass\n"
                "    def m6(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"min_cohesion_methods": 5, "max_methods_per_class": 10})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Cohesion"]["findings"]
            self.assertTrue(findings)

    def test_generate_tests_false_config_skips_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def hello():\n"
                "    return 'world'\n",
                encoding="utf-8",
            )
            result = refactor_file(
                str(source),
                dry_run=False,
                output_dir=tmp,
                generate_tests=False,
            )
            self.assertNotIn("error", result)
            self.assertEqual(result["phases"]["3_tests"]["status"], "disabled")
            test_files = list(Path(tmp).glob("**/test_sample.py"))
            self.assertEqual(len(test_files), 0)

    def test_check_generates_scaffold_only_if_enabled_and_save(self):
        from code_analyzer.orchestrator import run_pipeline, build_parser
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def hello():\n"
                "    return 'world'\n",
                encoding="utf-8",
            )
            parser = build_parser()
            args = parser.parse_args([str(source), "--no-refactor", "--output", tmp, "--no-tests"])
            exit_code = run_pipeline(args)
            self.assertEqual(exit_code, 0)
            test_files_1 = list(Path(tmp).glob("**/test_sample.py"))
            self.assertEqual(len(test_files_1), 0)

            args2 = parser.parse_args([str(source), "--no-refactor", "--output", tmp])
            exit_code2 = run_pipeline(args2)
            self.assertEqual(exit_code2, 0)
            test_files_2 = list(Path(tmp).glob("**/test_sample.py"))
            self.assertEqual(len(test_files_2), 1)

    def test_tool_warnings_section_in_markdown_and_html_reports(self):
        from code_analyzer.report_generator import ReportGenerator
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("def hello(): pass\n", encoding="utf-8")
            
            analysis_data = {
                "metrics": {
                    "lines_of_code": 1, "code_lines": 1, "comment_lines": 0, "blank_lines": 0,
                    "num_classes": 0, "num_functions": 1, "num_imports": 0,
                    "avg_cyclomatic_complexity": 1.0, "max_cyclomatic_complexity": 1,
                    "maintainability_index": 100.0, "maintainability_grade": "A", "comment_ratio": 0.0
                },
                "criteria": {},
                "tool_warnings": ["ruff nao instalado — analise parcial"]
            }

            generator = ReportGenerator(str(source), analysis_data, output_dir=tmp)
            md_report = generator.generate_markdown_report()
            html_report = generator.generate_html_report()

            # Valida presença no Markdown
            self.assertIn("> [!WARNING]", md_report)
            self.assertIn("ruff nao instalado", md_report)
            self.assertIn("code-analyze setup", md_report)
            
            # Valida presença no HTML
            self.assertIn("Analise Parcial", html_report)
            self.assertIn("code-analyze setup", html_report)
            self.assertIn("border-left:4px solid #ef4444", html_report)

    def test_scaffold_generation_for_classes_and_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Calculator:\n"
                "    def __init__(self, start: int):\n"
                "        self.val = start\n"
                "    def add(self, x: int) -> int:\n"
                "        return self.val + x\n"
                "    async def get_val(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            result = refactor_file(
                str(source),
                dry_run=False,
                output_dir=tmp,
                generate_tests=True,
            )
            self.assertNotIn("error", result)
            test_files = list(Path(tmp).glob("**/test_sample.py"))
            self.assertEqual(len(test_files), 1)
            
            test_content = test_files[0].read_text(encoding="utf-8")
            self.assertIn("from sample import Calculator", test_content)
            self.assertIn("class TestSample:", test_content)
            self.assertIn("def test_calculator_add(self):", test_content)
            self.assertIn("obj = Calculator(0)", test_content)
            self.assertIn("result = obj.add(0)", test_content)
            self.assertIn("assert result is not None", test_content)
            self.assertIn("@pytest.mark.asyncio", test_content)
            self.assertIn("def test_calculator_get_val(self):", test_content)
            self.assertIn("await obj.get_val()", test_content)
            self.assertIn("assert True", test_content)

    def test_interactive_menu_handles_expanded_context(self):
        from code_analyzer.interactive import _get_snippet
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "line 1\nline 2\nline 3\nline 4\nline 5\n"
                "line 6 (target)\n"
                "line 7\nline 8\nline 9\nline 10\nline 11\n",
                encoding="utf-8"
            )
            
            # Contexto padrão = 1 (mostra a anterior, a alvo e a próxima)
            snippet_1 = _get_snippet(str(source), "Linha 6", context_size=1)
            self.assertIn("line 5", snippet_1)
            self.assertIn("line 6 (target)", snippet_1)
            self.assertIn("line 7", snippet_1)
            self.assertNotIn("line 4", snippet_1)
            self.assertNotIn("line 8", snippet_1)
            
            # Contexto expandido = 4
            snippet_4 = _get_snippet(str(source), "Linha 6", context_size=4)
            self.assertIn("line 2", snippet_4)
            self.assertIn("line 6 (target)", snippet_4)
            self.assertIn("line 10", snippet_4)
            self.assertNotIn("line 1\n", snippet_4)
            self.assertNotIn("line 11", snippet_4)

    def test_coupling_ignores_inline_imports_inside_try_except(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def load_module():\n"
                "    try:\n"
                "        import ujson as json\n"
                "    except ImportError:\n"
                "        import json\n"
                "    return json\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Coupling"]["findings"]
            # Apenas deve validar que não há finding de import inline (ou seja, lista vazia)
            inline_findings = [f for f in findings if "dentro da funcao" in f["issue"]]
            self.assertEqual(len(inline_findings), 0)

    def test_cohesion_lcom_precise_cohesive_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Cohesive:\n"
                "    def __init__(self):\n"
                "        self.a = 1\n"
                "        self.b = 2\n"
                "    def m1(self):\n"
                "        return self.a + self.b\n"
                "    def m2(self):\n"
                "        return self.a * self.b\n"
                "    def m3(self):\n"
                "        return self.a - self.b\n"
                "    def m4(self):\n"
                "        return self.a / self.b\n"
                "    def m5(self):\n"
                "        return self.a + self.b\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"min_cohesion_methods": 5})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Cohesion"]["findings"]
            # LCOM deve ser muito próximo de 0.0, não deve ter findings
            self.assertEqual(len(findings), 0)

    def test_cohesion_lcom_precise_uncohesive_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Uncohesive:\n"
                "    def __init__(self):\n"
                "        self.a = 1\n"
                "        self.b = 2\n"
                "        self.c = 3\n"
                "        self.d = 4\n"
                "        self.e = 5\n"
                "    def m1(self):\n"
                "        return self.a\n"
                "    def m2(self):\n"
                "        return self.b\n"
                "    def m3(self):\n"
                "        return self.c\n"
                "    def m4(self):\n"
                "        return self.d\n"
                "    def m5(self):\n"
                "        return self.e\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"min_cohesion_methods": 5})
            self.assertTrue(result["success"])
            findings = result["criteria"]["Cohesion"]["findings"]
            # M = 5, A = 5, sum_m_a = 5 (cada atributo é usado por apenas 1 método)
            # LCOM = (5 - (5/5)) / (5 - 1) = (5 - 1) / 4 = 1.0 (baixíssima coesão)
            # Deve emitir finding
            self.assertEqual(len(findings), 1)
            self.assertIn("LCOM = 1.00", findings[0]["issue"])

    def test_import_exists_detects_non_existent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("import non_existent_module_xyz_123\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ImportExists"]["findings"]
            self.assertEqual(len(findings), 1)
            self.assertIn("non_existent_module_xyz_123", findings[0]["issue"])

    def test_import_exists_ignores_existent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("import os\nimport sys\nfrom json import dumps\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ImportExists"]["findings"]
            self.assertEqual(len(findings), 0)

    def test_api_exists_detects_non_existent_attribute(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "import json\n"
                "json.dumps_invalid_xyz(123)\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ApiExists"]["findings"]
            self.assertEqual(len(findings), 1)
            self.assertIn("dumps_invalid_xyz", findings[0]["issue"])
            self.assertIn("dumps", findings[0]["suggestion"])

    def test_api_exists_detects_non_existent_import_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("from json import dumps_invalid_abc\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["ApiExists"]["findings"]
            self.assertEqual(len(findings), 1)
            self.assertIn("dumps_invalid_abc", findings[0]["issue"])
            self.assertIn("dumps", findings[0]["suggestion"])

    def test_print_leak_detector_groups_multiple_prints(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process_data(x):\n"
                "    print(x)\n"
                "    print('debug')\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["PrintLeak"]["findings"]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["location"], "linhas 2, 3")
            self.assertIn("print() was found 2 times", findings[0]["issue"])

    def test_compact_mode_omits_snippets_in_markdown(self):
        from code_analyzer.report_generator import ReportGenerator
        dummy_analysis = {
            "config": {"compact": True},
            "metrics": {},
            "criteria": {
                "PrintLeak": {
                    "score": 4,
                    "status": "CRITICO",
                    "severity": "MEDIA",
                    "description": "PrintLeak - print() inside library functions may be forgotten debug output",
                    "findings": [
                        {
                            "criterion": "PrintLeak",
                            "location": "linha 5",
                            "line": 5,
                            "severity": "MEDIA",
                            "issue": "print() inside 'process_data()' may be forgotten debug output.",
                            "suggestion": "Replace print() with logging.",
                            "line_content": "print('test')",
                        }
                    ],
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("def process_data():\n    print('test')\n", encoding="utf-8")
            
            # Modo Compacto
            gen_compact = ReportGenerator(str(source), dummy_analysis)
            md_compact = gen_compact.generate_markdown_report()
            self.assertNotIn("Codigo atual", md_compact)
            self.assertNotIn("```python", md_compact)
            self.assertIn("Sugestão: Replace print() with logging.", md_compact)

            # Modo Normal
            dummy_analysis_normal = {
                "config": {"compact": False},
                "metrics": {},
                "criteria": dummy_analysis["criteria"],
            }
            gen_normal = ReportGenerator(str(source), dummy_analysis_normal)
            md_normal = gen_normal.generate_markdown_report()
            self.assertIn("Codigo atual", md_normal)
            self.assertIn("```python", md_normal)

    def test_history_snapshot_saving_and_loading(self):
        from code_analyzer.history import save_history_snapshot, load_history
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        
        dummy_analysis = {
            "metrics": {"maintainability_index": 85.0, "maintainability_grade": "B"},
            "criteria": {
                "SRP": {"score": 8.0, "findings": []},
                "Cohesion": {"score": 9.0, "findings": []}
            }
        }
        
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                source = Path(tmp) / "code.py"
                source.write_text("print('hello')", encoding="utf-8")
                
                # Salvar
                file_path = save_history_snapshot(str(source), dummy_analysis)
                self.assertTrue(file_path.exists())
                
                # Carregar
                history = load_history(str(source))
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["maintainability_index"], 85.0)
                self.assertEqual(history[0]["scores"]["SRP"], 8.0)

    def test_history_cli_command(self):
        from code_analyzer.cli import dispatch
        from code_analyzer.history import save_history_snapshot
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import io
        import json
        
        dummy_analysis = {
            "metrics": {"maintainability_index": 90.0, "maintainability_grade": "A"},
            "criteria": {"SRP": {"score": 7.0}}
        }
        
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                source = Path(tmp) / "code.py"
                source.write_text("print('hello')", encoding="utf-8")
                
                # Salvar snapshot
                save_history_snapshot(str(source), dummy_analysis)
                
                # Testar CLI normal
                f = io.StringIO()
                with patch("sys.stdout", f):
                     code = dispatch(["history", str(source)])
                     self.assertEqual(code, 0)
                     output = f.getvalue()
                     self.assertIn("Histórico de evolução para", output)
                     self.assertIn("SRP (7.0)", output)
                     
                # Testar CLI JSON
                f_json = io.StringIO()
                with patch("sys.stdout", f_json):
                     code_json = dispatch(["history", "--json", str(source)])
                     self.assertEqual(code_json, 0)
                     output_json = json.loads(f_json.getvalue().strip())
                     self.assertTrue(output_json["success"])
                     self.assertEqual(len(output_json["history"]), 1)

    def test_regression_detector_triggers_warning(self):
        from code_analyzer.orchestrator import run_pipeline, build_parser
        from code_analyzer.history import save_history_snapshot
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import io
        
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                source = Path(tmp) / "code.py"
                # Primeira versão: código sem violações
                source.write_text("def run():\n    pass\n", encoding="utf-8")
                
                parser = build_parser()
                # Roda primeira vez
                args1 = parser.parse_args([str(source), "--no-refactor", "--quiet"])
                run_pipeline(args1)
                
                # Segunda versão: introduz print leak para abaixar o score
                source.write_text(
                    "def process():\n"
                    "    print('a')\n"
                    "    print('b')\n",
                    encoding="utf-8"
                )
                
                # Roda segunda vez capturando stdout
                f = io.StringIO()
                with patch("sys.stdout", f):
                    args2 = parser.parse_args([str(source), "--no-refactor"])
                    run_pipeline(args2)
                    output = f.getvalue()
                    # Deve conter o alerta de regressão do PrintLeak
                    self.assertIn("ALERTA DE REGRESSÃO", output)
                    self.assertIn("PrintLeak", output)

    def test_lazy_evaluation_skips_analysis(self):
        from code_analyzer.orchestrator import run_pipeline, build_parser
        from code_analyzer.history import save_history_snapshot
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import io

        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                source = Path(tmp) / "code.py"
                source.write_text("def run():\n    pass\n", encoding="utf-8")

                parser = build_parser()
                # Primeira execução — faz análise completa
                args1 = parser.parse_args([str(source), "--no-refactor", "--quiet"])
                run_pipeline(args1)

                # Segunda execução — mesmo arquivo, deve usar lazy evaluation
                f = io.StringIO()
                with patch("sys.stdout", f):
                    args2 = parser.parse_args([str(source), "--no-refactor", "--quiet"])
                    run_pipeline(args2)
                    output = f.getvalue()
                    self.assertIn("Lazy Evaluation", output)
                    self.assertIn("Reutilizando analise do historico", output)

    def test_lazy_evaluation_force_skips_cache(self):
        from code_analyzer.orchestrator import run_pipeline, build_parser
        from code_analyzer.history import save_history_snapshot
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import io

        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                source = Path(tmp) / "code.py"
                source.write_text("def run():\n    pass\n", encoding="utf-8")

                parser = build_parser()
                # Primeira execução
                args1 = parser.parse_args([str(source), "--no-refactor", "--quiet"])
                run_pipeline(args1)

                # Segunda execução com --force — deve ignorar o cache
                f = io.StringIO()
                with patch("sys.stdout", f):
                    args2 = parser.parse_args([str(source), "--no-refactor", "--force", "--quiet"])
                    run_pipeline(args2)
                    output = f.getvalue()
                    self.assertNotIn("Lazy Evaluation", output)
                    self.assertNotIn("Reutilizando analise do historico", output)

    def test_granular_refactoring_enabled_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "import os\n"
                "import os\n"
                "import sys\n"
                "def func():\n"
                "    msg = f'hello'\n"
                "    print(msg)\n",
                encoding="utf-8",
            )
            result = refactor_file(
                str(source),
                dry_run=False,
                output_dir=tmp,
                quiet=True,
                enabled_rules=["duplicate_imports"],
            )
            self.assertIsNone(result.get("error"))
            phase2 = result["phases"]["2_refactor"]
            changes = phase2.get("changes_detail", [])
            # Só deve ter removido o import duplicado
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["type"], "duplicate_import")

    def test_semantic_duplication_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def process_user(data):\n"
                "    result = []\n"
                "    for item in data:\n"
                "        result.append(item.strip())\n"
                "    return result\n\n"
                "def handle_user_data(items):\n"
                "    output = []\n"
                "    for entry in items:\n"
                "        output.append(entry.strip())\n"
                "    return output\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["SemanticDuplication"]["findings"]
            self.assertEqual(len(findings), 1)
            self.assertIn("process_user", findings[0]["issue"])
            self.assertIn("handle_user_data", findings[0]["issue"])


    def test_semantic_cross_file_duplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_a = Path(tmp) / "a.py"
            source_b = Path(tmp) / "b.py"
            source_a.write_text(
                "def process_user(data):\n"
                "    lines = []\n"
                "    for item in data:\n"
                "        lines.append(item.strip())\n"
                "    return lines\n",
                encoding="utf-8",
            )
            source_b.write_text(
                "def handle_entries(entries):\n"
                "    output = []\n"
                "    for entry in entries:\n"
                "        output.append(entry.strip())\n"
                "    return output\n",
                encoding="utf-8",
            )
            from code_analyzer.analyzer.semantic import compare_files
            result = compare_files(str(source_a), str(source_b))
            duplicates = result["duplicates"]
            self.assertEqual(len(duplicates), 1)
            funcs = duplicates[0]["functions"]
            names = {f["name"] for f in funcs}
            self.assertEqual(names, {"process_user", "handle_entries"})


    def test_string_dispatch_detects_repeated_self_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Router:\n"
                "    def __init__(self, mode):\n"
                "        self.mode = mode\n"
                "    def process(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return data[:10]\n"
                "        return data\n"
                "    def validate(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return len(data) > 0\n"
                "        return True\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"]["StringDispatch"]["findings"]
            self.assertTrue(findings)
            self.assertIn("mode", findings[0]["issue"])
            self.assertIn("Strategy", findings[0]["suggestion"])

    def test_string_dispatch_no_finding_for_single_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Handler:\n"
                "    def __init__(self, kind):\n"
                "        self.kind = kind\n"
                "    def run(self):\n"
                "        if self.kind == 'a':\n"
                "            return 1\n"
                "        return 0\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"].get("StringDispatch", {}).get("findings", [])
            self.assertFalse(findings)

    def test_string_dispatch_ignore_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Router:\n"
                "    def __init__(self, mode):\n"
                "        self.mode = mode\n"
                "    def process(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return data[:10]\n"
                "        return data\n"
                "    def validate(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return True\n"
                "        return False\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {"ignore_criteria": ["StringDispatch"]})
            self.assertTrue(result["success"])
            self.assertNotIn("StringDispatch", result["criteria"])

    def test_pattern_advisor_suggests_strategy_for_string_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "class Router:\n"
                "    def __init__(self, mode):\n"
                "        self.mode = mode\n"
                "    def process(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return data[:10]\n"
                "        return data\n"
                "    def validate(self, data):\n"
                "        if self.mode == 'fast':\n"
                "            return True\n"
                "        return False\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            from code_analyzer.pattern_advisor import get_pattern_advice
            advice = get_pattern_advice(result)
            patterns = [a["pattern"] for a in advice]
            self.assertIn("Strategy", patterns)

    def test_roi_check_insufficient_history_returns_no_warning(self):
        from code_analyzer.history import check_roi_diminishing
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "dummy.py"
            source.write_text("x = 1\n", encoding="utf-8")
            roi = check_roi_diminishing(str(source))
            self.assertFalse(roi["roi_diminishing"])


    # ------------------------------------------------------------------
    # SC1-SC3: Scoring Contextual
    # ------------------------------------------------------------------

    def test_compute_priority_index_high_fanin(self):
        from code_analyzer.project_context import compute_priority_index
        pi = compute_priority_index(fan_in=20, commit_count=30, coverage_pct=0)
        self.assertEqual(pi["label"], "CRITICO")
        self.assertGreaterEqual(pi["score"], 75)

    def test_compute_priority_index_low_priority(self):
        from code_analyzer.project_context import compute_priority_index
        pi = compute_priority_index(fan_in=0, commit_count=0, coverage_pct=100)
        self.assertEqual(pi["label"], "BAIXA")
        self.assertLess(pi["score"], 25)

    def test_compute_priority_index_returns_all_fields(self):
        from code_analyzer.project_context import compute_priority_index
        pi = compute_priority_index(fan_in=5, commit_count=10, coverage_pct=40)
        for key in ("score", "label", "reason", "fan_in", "commit_count", "coverage_pct"):
            self.assertIn(key, pi)

    def test_get_import_fan_in_counts_importers(self):
        from code_analyzer.project_context import get_import_fan_in
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "mymodule.py"
            target.write_text("def foo(): pass\n", encoding="utf-8")
            importer = root / "other.py"
            importer.write_text("from mymodule import foo\n", encoding="utf-8")
            unrelated = root / "third.py"
            unrelated.write_text("x = 1\n", encoding="utf-8")
            count = get_import_fan_in(target, root)
            self.assertEqual(count, 1)

    def test_get_import_fan_in_zero_when_no_importers(self):
        from code_analyzer.project_context import get_import_fan_in
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "isolated.py"
            target.write_text("x = 1\n", encoding="utf-8")
            count = get_import_fan_in(target, root)
            self.assertEqual(count, 0)

    def test_load_project_context_includes_fan_in_and_commits(self):
        from code_analyzer.project_context import load_project_context
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("x = 1\n", encoding="utf-8")
            ctx = load_project_context(str(source))
            self.assertIn("fan_in", ctx)
            self.assertIn("commit_count", ctx)
            self.assertIsInstance(ctx["fan_in"], int)
            self.assertIsInstance(ctx["commit_count"], int)

    def test_analysis_result_includes_priority_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text("def foo(): return 1\n", encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            ctx = result.get("project_context", {})
            self.assertIn("fan_in", ctx)

    # ------------------------------------------------------------------
    # CF: Cross-file analysis
    # ------------------------------------------------------------------

    def test_compare_directory_finds_cross_file_duplicates(self):
        from code_analyzer.analyzer.semantic import compare_directory
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text(
                "def process(items):\n"
                "    result = []\n"
                "    for item in items:\n"
                "        result.append(item.strip())\n"
                "    return result\n",
                encoding="utf-8",
            )
            (root / "b.py").write_text(
                "def handle(entries):\n"
                "    result = []\n"
                "    for entry in entries:\n"
                "        result.append(entry.strip())\n"
                "    return result\n",
                encoding="utf-8",
            )
            result = compare_directory(str(root))
            self.assertGreaterEqual(result["duplicate_count"], 1)
            self.assertGreaterEqual(result["files_scanned"], 2)

    def test_compare_directory_no_duplicates(self):
        from code_analyzer.analyzer.semantic import compare_directory
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def foo(): return 1\n", encoding="utf-8")
            (root / "b.py").write_text("def bar(): return 2 + 2\n", encoding="utf-8")
            result = compare_directory(str(root))
            self.assertEqual(result["duplicate_count"], 0)

    # ------------------------------------------------------------------
    # DF: Data-flow extractor
    # ------------------------------------------------------------------

    def test_dataflow_extractor_detects_cluster_in_long_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            # Two disjoint chains of variables — each chain spans many lines
            # and shares variables only within itself.
            # Function > 50 lines with two isolated chains of variables.
            # Chain A (a01..a20): each statement uses only a* variables.
            # Chain B (b01..b20): each statement uses only b* variables.
            # No cross-chain dependency → two separate extractable clusters.
            chain_a = ["    a01 = 10\n"]
            for i in range(2, 21):
                prev = f"a{i-1:02d}"
                chain_a.append(f"    a{i:02d} = {prev} + {i}\n")
            chain_b = ["    b01 = 20\n"]
            for i in range(2, 21):
                prev = f"b{i-1:02d}"
                chain_b.append(f"    b{i:02d} = {prev} * {i}\n")
            chain_c = ["    c01 = 30\n"]
            for i in range(2, 16):
                prev = f"c{i-1:02d}"
                chain_c.append(f"    c{i:02d} = {prev} - {i}\n")
            body = chain_a + chain_b + chain_c
            code = "def big_process():\n" + "".join(body)
            source.write_text(code, encoding="utf-8")
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"].get("DataFlowExtractor", {}).get("findings", [])
            self.assertTrue(len(findings) >= 1)

    def test_dataflow_extractor_skips_short_functions(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def short(x):\n"
                "    a = x + 1\n"
                "    b = a * 2\n"
                "    return b\n",
                encoding="utf-8",
            )
            result = run_analysis(str(source), {})
            self.assertTrue(result["success"])
            findings = result["criteria"].get("DataFlowExtractor", {}).get("findings", [])
            self.assertFalse(findings)

    def test_dataflow_extractor_ignore_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            lines = ["def big(data):\n"]
            for i in range(30):
                lines.append(f"    var_{i} = data[{i}] * 2\n")
            lines.append("    return var_0\n")
            source.write_text("".join(lines), encoding="utf-8")
            result = run_analysis(str(source), {"ignore_criteria": ["DataFlowExtractor"]})
            self.assertTrue(result["success"])
            self.assertNotIn("DataFlowExtractor", result["criteria"])


    # ------------------------------------------------------------------
    # v4.0.0 — µ1: Purity Classifier
    # ------------------------------------------------------------------

    def test_purity_pure_no_self(self):
        import ast as _ast
        from code_analyzer.analyzer.purity import classify_block
        code = textwrap.dedent("""\
            def process(x, y):
                result = x * 2
                total = result + y
                output = total / 2
                final = output + 1
                return final
        """)
        tree = _ast.parse(code)
        func = next(n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef))
        candidate = {"start_line": 2, "end_line": 6}
        info = classify_block(func, candidate)
        self.assertEqual(info["purity"], "pure")
        self.assertEqual(info["reasons"], [])

    def test_purity_side_effect_self_access(self):
        import ast as _ast
        from code_analyzer.analyzer.purity import classify_block
        code = textwrap.dedent("""\
            def process(self, x):
                val = self.config * x
                result = val + self.offset
                output = result * 2
                return output
        """)
        tree = _ast.parse(code)
        func = next(n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef))
        candidate = {"start_line": 2, "end_line": 5}
        info = classify_block(func, candidate)
        self.assertEqual(info["purity"], "side_effect")
        self.assertTrue(any("self" in r for r in info["reasons"]))

    def test_purity_side_effect_open_call(self):
        import ast as _ast
        from code_analyzer.analyzer.purity import classify_block
        code = textwrap.dedent("""\
            def load(path):
                fh = open(path)
                data = fh.read()
                fh.close()
                return data
        """)
        tree = _ast.parse(code)
        func = next(n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef))
        candidate = {"start_line": 2, "end_line": 4}
        info = classify_block(func, candidate)
        self.assertEqual(info["purity"], "side_effect")
        self.assertTrue(any("open" in r for r in info["reasons"]))

    def test_purity_classify_file_returns_map(self):
        import ast as _ast
        from code_analyzer.analyzer.purity import classify_file
        from code_analyzer.analyzer.dataflow import analyze_file
        # Build a function long enough to trigger dataflow (>50 lines)
        body = "\n".join(
            f"    var_{i:02d} = var_{i-1:02d} + {i}" if i > 0 else "    var_00 = x"
            for i in range(55)
        )
        code = f"def big_fn(x):\n{body}\n    return var_54\n"
        tree = _ast.parse(code)
        df = analyze_file(tree)
        pmap = classify_file(tree, df)
        # pmap may be empty if no cluster passes filters — just check type
        self.assertIsInstance(pmap, dict)

    # ------------------------------------------------------------------
    # v4.0.0 — µ3: Equivalence Test Generation
    # ------------------------------------------------------------------

    def test_equivalence_test_generated_pure(self):
        import textwrap as _tw
        from code_analyzer.analyzer.equivalence import generate_equivalence_test
        candidate = {
            "start_line": 2,
            "end_line": 5,
            "variables": ["result", "total"],
            "suggested_name": "_compute",
            "purity": "pure",
            "reasons": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mod.py"
            src.write_text("def fn(x):\n    result = x * 2\n    total = result + 1\n    return total\n", encoding="utf-8")
            content = generate_equivalence_test(str(src), "fn", candidate)
        self.assertIn("def test_equivalence_", content)
        self.assertIn("Alta", content)
        self.assertIn("_compute", content)
        # Must be valid Python
        compile(content, "<test>", "exec")

    def test_equivalence_test_generated_side_effect(self):
        from code_analyzer.analyzer.equivalence import generate_equivalence_test
        candidate = {
            "start_line": 2,
            "end_line": 5,
            "variables": ["val", "output"],
            "suggested_name": "_load_data",
            "purity": "side_effect",
            "reasons": ["acessa self.config"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mod.py"
            src.write_text("def fn(self):\n    val = self.config\n    output = val * 2\n    return output\n", encoding="utf-8")
            content = generate_equivalence_test(str(src), "fn", candidate)
        self.assertIn("pytest.skip", content)
        self.assertIn("Media", content)
        compile(content, "<test>", "exec")

    # ------------------------------------------------------------------
    # v4.0.0 — µ5: Fingerprint Index
    # ------------------------------------------------------------------

    def test_fingerprint_index_created(self):
        from code_analyzer.analyzer.fingerprint_index import update_index, get_index_path
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            (src_dir / "a.py").write_text("def foo(x):\n    return x + 1\n", encoding="utf-8")
            (src_dir / "b.py").write_text("def bar(y):\n    return y * 2\n", encoding="utf-8")
            index = update_index(src_dir)
            idx_path = get_index_path(src_dir)
            self.assertTrue(idx_path.exists())
            self.assertIsInstance(index, dict)
            # Each fingerprint maps to a list of entries
            for entries in index.values():
                self.assertIsInstance(entries, list)
                for e in entries:
                    self.assertIn("func_name", e)
                    self.assertIn("mtime", e)

    def test_fingerprint_index_incremental(self):
        from code_analyzer.analyzer.fingerprint_index import update_index
        import time
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            f = src_dir / "a.py"
            f.write_text("def foo(x):\n    return x\n", encoding="utf-8")
            idx1 = update_index(src_dir)
            # Collect mtime from first index
            first_mtime = next(iter(idx1.values()))[0]["mtime"] if idx1 else 0.0
            # Second call without touching file — mtime unchanged, carried over
            idx2 = update_index(src_dir)
            second_mtime = next(iter(idx2.values()))[0]["mtime"] if idx2 else 0.0
            self.assertEqual(first_mtime, second_mtime)

    def test_compare_directory_fuzzy_threshold(self):
        from code_analyzer.analyzer.semantic import compare_directory
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # Two structurally similar (but not identical) functions
            (d / "a.py").write_text(
                "def process_a(x, y, z):\n    result = x + y\n    total = result * z\n    return total\n",
                encoding="utf-8",
            )
            (d / "b.py").write_text(
                "def process_b(a, b, c):\n    result = a + b\n    total = result * c\n    return total\n",
                encoding="utf-8",
            )
            # Exact match — these ARE identical in structure after normalization
            result_exact = compare_directory(tmp, threshold=1.0)
            result_fuzzy = compare_directory(tmp, threshold=0.5)
            # fuzzy should find at least as many as exact
            self.assertGreaterEqual(result_fuzzy["duplicate_count"], result_exact["duplicate_count"])
            self.assertEqual(result_fuzzy["threshold"], 0.5)


class TestIdentityComparison(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("IdentityComparison", {}).get("findings", [])

    def test_is_string_literal_detected(self):
        findings = self._run('x = "x"\nif x is "admin":\n    pass\n')
        self.assertEqual(len(findings), 1)
        self.assertIn("'admin'", findings[0]["issue"])

    def test_is_not_int_detected(self):
        findings = self._run("status = 0\nif status is not 200:\n    pass\n")
        self.assertEqual(len(findings), 1)
        self.assertIn("is not", findings[0]["issue"])

    def test_is_none_not_flagged(self):
        findings = self._run("x = None\nif x is None:\n    pass\n")
        self.assertEqual(len(findings), 0)

    def test_equality_not_flagged(self):
        findings = self._run('x = "x"\nif x == "admin":\n    pass\n')
        self.assertEqual(len(findings), 0)


class TestOrmInLoop(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("OrmInLoop", {}).get("findings", [])

    def test_objects_in_for_loop(self):
        code = (
            "import django\n"
            "users = []\n"
            "for user in users:\n"
            "    profile = Profile.objects.get(user=user)\n"
        )
        findings = self._run(code)
        self.assertGreater(len(findings), 0)
        self.assertIn("N+1", findings[0]["issue"])

    def test_no_orm_in_loop_clean(self):
        findings = self._run("for i in range(10):\n    print(i)\n")
        self.assertEqual(len(findings), 0)

    def test_outside_loop_not_flagged(self):
        code = "import django\nprofiles = Profile.objects.all()\n"
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_list_comprehension_orm(self):
        code = (
            "import django\n"
            "ids = [1, 2, 3]\n"
            "users = [User.objects.get(id=i) for i in ids]\n"
        )
        findings = self._run(code)
        self.assertGreater(len(findings), 0, "N+1 em list comprehension deve ser detectado")

    def test_related_manager_without_direct_django_import(self):
        # Arquivo que importa só do app, sem 'from django.*' diretamente
        code = (
            "from myapp.models import Order, OrderItem\n"
            "def process(orders):\n"
            "    for order in orders:\n"
            "        items = order.items.all()\n"
        )
        findings = self._run(code)
        self.assertGreater(len(findings), 0, "related_manager.all() deve ser detectado mesmo sem import django direto")

    def test_standalone_filter_builtin_not_flagged(self):
        # Python builtin filter() não deve disparar
        code = (
            "items = [1, 2, 3]\n"
            "for batch in items:\n"
            "    result = list(filter(lambda x: x > 0, batch))\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 0, "filter() builtin não deve ser confundido com ORM")


class TestMassAssignment(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("MassAssignment", {}).get("findings", [])

    def test_fields_all_in_meta(self):
        code = (
            "class UserForm(ModelForm):\n"
            "    class Meta:\n"
            "        model = None\n"
            "        fields = '__all__'\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)
        self.assertIn("__all__", findings[0]["issue"])

    def test_serializer_fields_all(self):
        code = (
            "class UserSerializer(ModelSerializer):\n"
            "    class Meta:\n"
            "        model = None\n"
            "        fields = '__all__'\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)

    def test_explicit_fields_not_flagged(self):
        code = (
            "class UserForm(ModelForm):\n"
            "    class Meta:\n"
            "        model = None\n"
            "        fields = ['name', 'email']\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_non_form_class_not_flagged(self):
        findings = self._run("class MyView:\n    fields = '__all__'\n")
        self.assertEqual(len(findings), 0)


class TestSaveSideEffects(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("SaveSideEffects", {}).get("findings", [])

    def test_send_mail_in_save(self):
        code = (
            "class Order(Model):\n"
            "    def save(self, *args, **kwargs):\n"
            "        super().save(*args, **kwargs)\n"
            "        send_mail('subject', 'body', 'from@x.com', ['to@x.com'])\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)
        self.assertIn("save()", findings[0]["issue"])

    def test_requests_post_in_save(self):
        code = (
            "import requests\n"
            "class Webhook(Model):\n"
            "    def save(self, *args, **kwargs):\n"
            "        super().save(*args, **kwargs)\n"
            "        requests.post(self.url, json={'event': 'saved'})\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)

    def test_clean_save_not_flagged(self):
        code = (
            "class Post(Model):\n"
            "    def save(self, *args, **kwargs):\n"
            "        self.title = self.title.strip()\n"
            "        super().save(*args, **kwargs)\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_non_model_save_not_flagged(self):
        code = (
            "class MyService:\n"
            "    def save(self):\n"
            "        send_mail('hi', 'body', 'a@b.com', ['c@d.com'])\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestHardcodedSecrets(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("HardcodedSecrets", {}).get("findings", [])

    def test_api_key_literal_detected(self):
        findings = self._run('API_KEY = "sk-proj-abc123xyz456"\n')
        self.assertEqual(len(findings), 1)
        self.assertIn("API_KEY", findings[0]["issue"])

    def test_password_literal_detected(self):
        findings = self._run('DATABASE_PASSWORD = "mysecretpass123"\n')
        self.assertEqual(len(findings), 1)
        self.assertIn("DATABASE_PASSWORD", findings[0]["issue"])

    def test_env_var_not_flagged(self):
        findings = self._run('API_KEY = os.environ.get("API_KEY")\n')
        self.assertEqual(len(findings), 0)

    def test_placeholder_not_flagged(self):
        findings = self._run('API_KEY = "your-api-key-here"\n')
        self.assertEqual(len(findings), 0)

    def test_unrelated_var_not_flagged(self):
        findings = self._run('MAX_RETRIES = "three"\n')
        self.assertEqual(len(findings), 0)


class TestInjectionRisk(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("InjectionRisk", {}).get("findings", [])

    def test_raw_fstring_detected(self):
        code = (
            "query = 'x'\n"
            "User.objects.raw(f\"SELECT * FROM auth_user WHERE name='{query}'\")\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)
        self.assertIn("SQL", findings[0]["issue"])

    def test_cursor_execute_fstring_detected(self):
        code = (
            "q = 'x'\n"
            "cursor.execute(f\"SELECT * FROM users WHERE name='{q}'\")\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)

    def test_os_system_fstring_detected(self):
        code = (
            "import os\n"
            "query = 'x'\n"
            "os.system(f\"grep -R {query} /data\")\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)
        self.assertIn("command injection", findings[0]["issue"].lower())

    def test_raw_literal_not_flagged(self):
        code = 'User.objects.raw("SELECT * FROM auth_user WHERE id = %s", [user_id])\n'
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_subprocess_fstring_detected(self):
        code = (
            "import subprocess\n"
            "cmd = 'x'\n"
            "subprocess.run(f\"ls {cmd}\")\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)


class TestContextManagerLeak(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("ContextManagerLeak", {}).get("findings", [])

    def test_open_without_with_detected(self):
        code = "f = open('file.txt', 'r')\ndata = f.read()\nf.close()\n"
        findings = self._run(code)
        self.assertEqual(len(findings), 1)
        self.assertIn("with", findings[0]["suggestion"])

    def test_open_with_context_manager_not_flagged(self):
        code = "with open('file.txt', 'r') as f:\n    data = f.read()\n"
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_open_in_function_without_with_detected(self):
        code = (
            "def read_file(path):\n"
            "    f = open(path)\n"
            "    return f.read()\n"
        )
        findings = self._run(code)
        self.assertEqual(len(findings), 1)


class TestFeatureEnvy(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("FeatureEnvy", {}).get("findings", [])

    def test_envious_method_flagged(self):
        code = textwrap.dedent("""\
            class Order:
                def __init__(self, customer):
                    self.customer = customer
                def get_customer_address(self):
                    return self.customer.address.street + ", " + self.customer.address.city
                def get_customer_email(self):
                    return self.customer.profile.email
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)
        self.assertIn("customer", findings[0]["issue"])

    def test_normal_method_not_flagged(self):
        code = textwrap.dedent("""\
            class Order:
                def __init__(self, price, qty):
                    self.price = price
                    self.qty = qty
                def total(self):
                    return self.price * self.qty
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_single_foreign_access_not_flagged(self):
        code = textwrap.dedent("""\
            class Notifier:
                def notify(self, user):
                    return user.email
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_collection_methods_on_own_attr_not_flagged(self):
        """append/pop on own list attribute is data management, not feature envy."""
        code = textwrap.dedent("""\
            class SessionContext:
                def __init__(self):
                    self._lock = None
                    self.frustration_history = []
                def add_frustration_sample(self, score):
                    self.frustration_history.append(score)
                    if len(self.frustration_history) > 10:
                        self.frustration_history.pop(0)
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_dict_update_on_own_attr_not_flagged(self):
        """dict.update() on own attribute is data management, not feature envy."""
        code = textwrap.dedent("""\
            class Cache:
                def __init__(self):
                    self.store = {}
                def put(self, key, value):
                    self.store.update({key: value})
                    self.store.setdefault('_count', 0)
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestShotgunSurgery(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("ShotgunSurgery", {}).get("findings", [])

    def test_constant_in_three_classes_flagged(self):
        code = textwrap.dedent("""\
            class Config:
                TAX_RATE = 0.18
            class Product:
                def price(self, p): return p * (1 + Config.TAX_RATE)
            class Invoice:
                def total(self, a): return a * (1 + Config.TAX_RATE)
            class Report:
                def summary(self, s): return s * (1 + Config.TAX_RATE)
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)
        self.assertIn("TAX_RATE", findings[0]["issue"])

    def test_constant_in_two_classes_not_flagged(self):
        code = textwrap.dedent("""\
            class Config:
                RATE = 0.1
            class A:
                def calc(self): return Config.RATE
            class B:
                def calc(self): return Config.RATE
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_self_access_not_flagged(self):
        code = textwrap.dedent("""\
            class A:
                def m1(self): return self.x
                def m2(self): return self.x
                def m3(self): return self.x
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestMassAssignmentGenericMeta(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("MassAssignment", {}).get("findings", [])

    def test_plain_class_meta_all_flagged(self):
        code = textwrap.dedent("""\
            class UserForm:
                class Meta:
                    fields = '__all__'
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)

    def test_explicit_fields_not_flagged(self):
        code = textwrap.dedent("""\
            class UserForm:
                class Meta:
                    fields = ['name', 'email']
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestMassAssignmentExcludeEmpty(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("MassAssignment", {}).get("findings", [])

    def test_exclude_empty_list_in_meta_flagged(self):
        code = textwrap.dedent("""\
            class UserForm:
                class Meta:
                    model = User
                    exclude = []
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)

    def test_exclude_empty_tuple_in_meta_flagged(self):
        code = textwrap.dedent("""\
            class UserSerializer(ModelSerializer):
                class Meta:
                    model = User
                    exclude = ()
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)

    def test_exclude_nonempty_not_flagged(self):
        code = textwrap.dedent("""\
            class UserForm:
                class Meta:
                    model = User
                    exclude = ['password', 'is_staff']
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_exclude_empty_in_dangerous_base_flagged(self):
        code = textwrap.dedent("""\
            class UserForm(ModelForm):
                exclude = []
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)


class TestStringDispatchParam(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("StringDispatch", {}).get("findings", [])

    def test_param_attr_dispatch_three_branches_flagged(self):
        code = textwrap.dedent("""\
            class Processor:
                def process(self, order):
                    if order.type == "digital":
                        pass
                    elif order.type == "physical":
                        pass
                    elif order.type == "subscription":
                        pass
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)

    def test_param_attr_dispatch_two_branches_not_flagged(self):
        code = textwrap.dedent("""\
            class Processor:
                def process(self, order):
                    if order.type == "digital":
                        pass
                    elif order.type == "physical":
                        pass
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestUnusedVariableFixes(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("UnusedVariable", {}).get("findings", [])

    def test_class_attribute_not_flagged(self):
        code = textwrap.dedent("""\
            class Config:
                TAX_RATE = 0.18
            class Product:
                def price(self, p): return p * (1 + Config.TAX_RATE)
        """)
        findings = self._run(code)
        names = [f["issue"] for f in findings]
        self.assertFalse(any("TAX_RATE" in n for n in names))

    def test_all_caps_constant_not_flagged(self):
        code = "API_KEY = 'sk-abc123'\nDATABASE_PASSWORD = 'secret'\n"
        findings = self._run(code)
        names = [f["issue"] for f in findings]
        self.assertFalse(any("API_KEY" in n or "DATABASE_PASSWORD" in n for n in names))

    def test_class_meta_fields_not_flagged(self):
        code = textwrap.dedent("""\
            class UserForm:
                class Meta:
                    fields = '__all__'
        """)
        findings = self._run(code)
        names = [f["issue"] for f in findings]
        self.assertFalse(any("fields" in n for n in names))

    def test_local_unused_still_flagged(self):
        code = textwrap.dedent("""\
            def calculate():
                unused = 42
                return 1
        """)
        findings = self._run(code)
        self.assertTrue(any("unused" in f["issue"] for f in findings))


class TestLSPDetector(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("LSP", {}).get("findings", [])

    def test_square_rectangle_violation_detected(self):
        code = textwrap.dedent("""\
            class Rectangle:
                def set_width(self, w): self.width = w
                def set_height(self, h): self.height = h
            class Square(Rectangle):
                def set_width(self, w):
                    self.width = w
                    self.height = w
                def set_height(self, h):
                    self.width = h
                    self.height = h
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)
        self.assertIn("LSP", findings[0]["issue"])

    def test_not_implemented_in_subclass_not_flagged(self):
        code = textwrap.dedent("""\
            class Animal:
                def speak(self): pass
            class Fish(Animal):
                def speak(self): raise NotImplementedError
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_clean_subclass_not_flagged(self):
        code = textwrap.dedent("""\
            class Shape:
                def area(self): return 0
            class Circle(Shape):
                def set_radius(self, r): self.radius = r
                def area(self): return 3.14 * self.radius ** 2
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestInconsistentReturnsExceptFix(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("InconsistentReturns", {}).get("findings", [])

    def test_none_in_except_not_flagged(self):
        code = textwrap.dedent("""\
            def safe_divide(a, b):
                try:
                    return a / b
                except ZeroDivisionError:
                    return None
                except TypeError:
                    return None
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_mixed_types_outside_except_still_flagged(self):
        code = textwrap.dedent("""\
            def bad(x):
                if x > 0:
                    return "positive"
                return 42
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)

    def test_all_builtin_treated_as_bool(self):
        """all() returns bool — mixing with bool literal is not inconsistent."""
        code = textwrap.dedent("""\
            def is_strategy_looping(history, name, window=3):
                if not history or len(history) < window:
                    return False
                recent = history[-window:]
                return all(s == name for s in recent)
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_max_builtin_treated_as_float(self):
        """max() returns numeric — mixing with float literal is not inconsistent."""
        code = textwrap.dedent("""\
            def get_trend(samples):
                if len(samples) < 2:
                    return 0.0
                delta = samples[-1] - samples[0]
                return max(-1.0, min(1.0, delta))
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)


class TestOrmInLoopDictFP(unittest.TestCase):
    def _run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("OrmInLoop", {}).get("findings", [])

    def test_dict_get_in_loop_not_flagged(self):
        """dict.get() in a loop should NOT trigger OrmInLoop even in Django files."""
        code = textwrap.dedent("""\
            from django.conf import settings
            def filter_funcs(all_funcs, error_line):
                for name, meta in all_funcs.items():
                    start = meta.get("lineno", 0)
                    end = meta.get("end_lineno", 99999)
                    if start <= error_line <= end:
                        return name
                return None
        """)
        findings = self._run(code)
        self.assertEqual(len(findings), 0)

    def test_orm_chained_still_flagged(self):
        """Model.objects.filter() in loop must still be detected."""
        code = textwrap.dedent("""\
            from django.db import models
            def process(items):
                for item in items:
                    obj = item.related.filter(active=True)
        """)
        findings = self._run(code)
        self.assertGreater(len(findings), 0)


class TestInitCommand(unittest.TestCase):
    def _run_init(self, cwd: Path, json_mode: bool = False):
        from code_analyzer.cli import _handle_init
        import os
        old = os.getcwd()
        try:
            os.chdir(cwd)
            return _handle_init(json_mode=json_mode)
        finally:
            os.chdir(old)

    def test_init_generic_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            self._run_init(cwd)
            self.assertTrue((cwd / ".analyzer.json").exists())
            self.assertTrue((cwd / ".pre-commit-config.yaml").exists())

    def test_init_detects_django_via_manage_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "manage.py").write_text("# django", encoding="utf-8")
            self._run_init(cwd)
            cfg = json.loads((cwd / ".analyzer.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["architecture_style"], "django")

    def test_init_detects_fastapi_via_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "requirements.txt").write_text("fastapi>=0.100\nuvicorn\n", encoding="utf-8")
            self._run_init(cwd)
            cfg = json.loads((cwd / ".analyzer.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["architecture_style"], "fastapi")

    def test_init_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            original = '{"architecture_style": "flask", "min_score": 9.0}'
            (cwd / ".analyzer.json").write_text(original, encoding="utf-8")
            (cwd / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
            self._run_init(cwd)
            self.assertEqual((cwd / ".analyzer.json").read_text(encoding="utf-8"), original)
            self.assertEqual((cwd / ".pre-commit-config.yaml").read_text(encoding="utf-8"), "repos: []\n")

    def test_init_precommit_contains_version(self):
        from code_analyzer import __version__
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            self._run_init(cwd)
            content = (cwd / ".pre-commit-config.yaml").read_text(encoding="utf-8")
            self.assertIn(f"rev: v{__version__}", content)

    def test_init_json_mode_returns_project_type(self):
        import io as _io
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            captured = _io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured
            try:
                self._run_init(cwd, json_mode=True)
            finally:
                sys.stdout = old_stdout
            result = json.loads(captured.getvalue())
            self.assertTrue(result["success"])
            self.assertIn("project_type", result)


class TestMinScoreGate(unittest.TestCase):
    """Tests for --min-score / pre-commit hook exit code behavior."""

    def _run_pipeline(self, code: str, min_score: float, extra_args: list | None = None):
        import argparse
        from code_analyzer.orchestrator import run_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "sample.py"
            src.write_text(code, encoding="utf-8")
            args = argparse.Namespace(
                file=str(src),
                no_refactor=True,
                no_tests=True,
                dry_run=False,
                interactive=False,
                quiet=True,
                json_mode=False,
                html=False,
                output_dir=None,
                compact=False,
                force=False,
                patch_only=False,
                min_score=min_score,
            )
            return run_pipeline(args)

    def test_min_score_pass_returns_zero(self):
        code = "x = 1\n"
        result = self._run_pipeline(code, min_score=0.0)
        self.assertEqual(result, 0)

    def test_min_score_fail_returns_one(self):
        # Force a score below 10 with many violations
        code = textwrap.dedent("""\
            import os, sys, re, json, math, datetime, pathlib, typing, itertools
            import collections, functools, abc, io, time, copy, shutil
            import subprocess, threading, asyncio, logging
            import requests, flask, django, numpy, pandas, sqlalchemy

            password = "secret123"
            api_key = "sk-live-abc123"

            class GodClass:
                def m1(self): pass
                def m2(self): pass
                def m3(self): pass
                def m4(self): pass
                def m5(self): pass
                def m6(self): pass
                def m7(self): pass
                def m8(self): pass
                def m9(self): pass
                def m10(self): pass
                def m11(self): pass
        """)
        result = self._run_pipeline(code, min_score=10.0)
        self.assertEqual(result, 1)


class TestTestPainMetrics(unittest.TestCase):
    """v5.0.0: Test Pain analysis metrics."""

    def _run_tp(self, source_code: str, test_code: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text(source_code, encoding="utf-8")
            test = Path(tmp) / "test_module.py"
            test.write_text(test_code, encoding="utf-8")
            from code_analyzer.analyzer.test_pain import analyze_test_pain
            return analyze_test_pain(str(src))

    def test_tp1_full_coverage(self):
        source = "def foo(): pass\ndef bar(): pass\n"
        test_code = "def test_foo(): pass\ndef test_bar(): pass\n"
        result = self._run_tp(source, test_code)
        self.assertEqual(result["tp1"]["covered"], 2)
        self.assertEqual(result["tp1"]["total"], 2)
        self.assertEqual(result["tp1"]["score"], 100.0)

    def test_tp1_partial_coverage(self):
        source = "def foo(): pass\ndef bar(): pass\ndef baz(): pass\n"
        test_code = "def test_foo(): pass\n"
        result = self._run_tp(source, test_code)
        self.assertEqual(result["tp1"]["covered"], 1)
        self.assertEqual(result["tp1"]["total"], 3)
        self.assertAlmostEqual(result["tp1"]["score"], 33.3, delta=0.5)

    def test_tp1_no_test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "module.py"
            src.write_text("def foo(): pass\n", encoding="utf-8")
            from code_analyzer.analyzer.test_pain import analyze_test_pain
            result = analyze_test_pain(str(src))
            self.assertEqual(result["aggregate"], 0.0)
            self.assertIsNone(result["test_file"])

    def test_tp2_no_mocks(self):
        source = "def add(a, b): return a + b\n"
        test_code = "def test_add(): assert add(1, 2) == 3\n"
        result = self._run_tp(source, test_code)
        self.assertEqual(result["tp2"]["mock_count"], 0)
        self.assertEqual(result["tp2"]["density"], 0.0)
        self.assertEqual(result["tp2"]["score"], 100.0)

    def test_tp2_high_mock_density(self):
        source = "def process(): pass\n"
        test_code = (
            "from unittest.mock import patch\n"
            "class TestProcess:\n"
            "    @patch('module.db')\n"
            "    @patch('module.cache')\n"
            "    @patch('module.api')\n"
            "    @patch('module.queue')\n"
            "    @patch('module.storage')\n"
            "    def test_process(self, *args): pass\n"
        )
        result = self._run_tp(source, test_code)
        self.assertGreaterEqual(result["tp2"]["mock_count"], 5)
        self.assertGreater(result["tp2"]["density"], 0.3)
        self.assertLess(result["tp2"]["score"], 50.0)

    def test_tp3_simple_tests(self):
        source = "def foo(): pass\n"
        test_code = "def test_foo(): assert True\n"
        result = self._run_tp(source, test_code)
        self.assertLessEqual(result["tp3"]["avg_complexity"], 2.0)
        self.assertGreaterEqual(result["tp3"]["score"], 80.0)

    def test_tp4_isolated(self):
        source = "def foo(): pass\n"
        test_code = "def test_foo(): assert True\n"
        result = self._run_tp(source, test_code)
        self.assertEqual(result["tp4"]["score"], 100.0)
        self.assertEqual(result["tp4"]["external_deps"], [])

    def test_tp4_db_dependent(self):
        source = "def foo(): pass\n"
        test_code = "from django.db import models\n\ndef test_foo(): pass\n"
        result = self._run_tp(source, test_code)
        self.assertEqual(result["tp4"]["score"], 60.0)
        self.assertIn("django.db", result["tp4"]["external_deps"][0])

    def test_aggregate_computation(self):
        source = "def foo(): pass\ndef bar(): pass\n"
        test_code = "def test_foo(): pass\ndef test_bar(): pass\n"
        result = self._run_tp(source, test_code)
        # Full coverage + no mocks + simple tests + isolated = ~100 aggregate
        self.assertGreaterEqual(result["aggregate"], 90.0)

    def test_production_risk_includes_test_pain(self):
        from code_analyzer.analyzer.scoring import production_risk_score
        result = production_risk_score(
            {"avg_cyclomatic_complexity": 3, "num_imports": 5},
            {},
            {"estimated_coverage": 50},
            {"aggregate": 80},
        )
        self.assertIn("test_pain", result["components"])
        self.assertGreater(result["components"]["test_pain"], 0)


class TestScoringFixes(unittest.TestCase):
    """B1 — MI uses average CC; B2 — production risk labels."""

    def test_mi_large_file_with_many_methods_not_zero(self):
        from code_analyzer.analyzer.scoring import maintainability_index
        # Simulates intent_classifier.py: 702 lines, avg CC 3.09, ~80 methods total
        lines = ["x = 1"] * 600 + [""] * 102  # 600 non-empty, 702 total
        mi = maintainability_index(lines, cyclomatic_complexity=247, functions_count=80)
        self.assertGreater(mi, 0, "MI deve ser > 0 para arquivo razoável com muitos métodos")

    def test_mi_uses_average_not_total_cc(self):
        from code_analyzer.analyzer.scoring import maintainability_index
        lines = ["x = 1"] * 50
        mi_total = maintainability_index(lines, cyclomatic_complexity=100, functions_count=1)
        mi_avg = maintainability_index(lines, cyclomatic_complexity=100, functions_count=50)
        self.assertGreater(mi_avg, mi_total, "MI com CC médio deve ser maior que com CC total")

    def test_production_risk_75_is_bom(self):
        from code_analyzer.analyzer.scoring import production_risk_score
        # High coverage, low complexity, few imports → score ~75
        result = production_risk_score(
            {"avg_cyclomatic_complexity": 4, "num_imports": 6},
            {},
            {"estimated_coverage": 70},
            {"aggregate": 70},
        )
        self.assertGreaterEqual(result["score"], 65)
        self.assertEqual(result["label"], "Bom")

    def test_production_risk_labels_full_range(self):
        from code_analyzer.analyzer.scoring import production_risk_score
        def score_for(coverage, cc, imports, alta_count, tp):
            criteria = {f"C{i}": {"severity": "ALTA", "findings": ["x"]} for i in range(alta_count)}
            return production_risk_score(
                {"avg_cyclomatic_complexity": cc, "num_imports": imports},
                criteria,
                {"estimated_coverage": coverage},
                {"aggregate": tp},
            )
        self.assertEqual(score_for(100, 1, 0, 0, 100)["label"], "Seguro")
        self.assertEqual(score_for(70, 4, 6, 1, 70)["label"], "Bom")
        self.assertEqual(score_for(40, 8, 10, 2, 40)["label"], "Risco")
        self.assertEqual(score_for(0, 20, 20, 5, 0)["label"], "Critico")


class TestAgentsCompliance(unittest.TestCase):
    """AgentsCompliance detector — valida regras do AGENTS.md ## [rules]."""

    def _run(self, source_code: str, rules_block: str, filename: str = "views.py") -> list:
        with tempfile.TemporaryDirectory() as tmp:
            agents = Path(tmp) / "AGENTS.md"
            agents.write_text(
                f"# AGENTS.md\n\n## [rules]\n{rules_block}\n\n## [thresholds]\nmin_score: 7.0\n",
                encoding="utf-8",
            )
            src = Path(tmp) / filename
            src.write_text(source_code, encoding="utf-8")
            result = run_analysis(str(src), {})
        self.assertTrue(result["success"])
        return result["criteria"].get("AgentsCompliance", {}).get("findings", [])

    def test_forbidden_pattern_flagged(self):
        findings = self._run(
            "class Meta:\n    fields = '__all__'\n",
            "forbidden: ** -> no: fields='__all__'",
        )
        self.assertGreater(len(findings), 0)
        self.assertIn("__all__", findings[0]["issue"])

    def test_forbidden_pattern_clean(self):
        findings = self._run(
            "class Meta:\n    fields = ['name', 'email']\n",
            "forbidden: ** -> no: fields='__all__'",
        )
        self.assertEqual(len(findings), 0)

    def test_decorator_missing_flagged(self):
        findings = self._run(
            "def my_view(request):\n    return 'ok'\n",
            "decorator: ** -> must_have: @login_required",
        )
        self.assertGreater(len(findings), 0)
        self.assertIn("login_required", findings[0]["issue"])

    def test_decorator_present_clean(self):
        findings = self._run(
            "from django.contrib.auth.decorators import login_required\n"
            "@login_required\ndef my_view(request):\n    return 'ok'\n",
            "decorator: ** -> must_have: @login_required",
        )
        self.assertEqual(len(findings), 0)

    def test_param_missing_flagged(self):
        findings = self._run(
            "def create_order(product_id):\n    pass\n",
            "param: ** -> must_have: usuario",
            filename="services.py",
        )
        self.assertGreater(len(findings), 0)
        self.assertIn("usuario", findings[0]["issue"])

    def test_param_present_clean(self):
        findings = self._run(
            "def create_order(usuario, product_id):\n    pass\n",
            "param: ** -> must_have: usuario",
            filename="services.py",
        )
        self.assertEqual(len(findings), 0)

    def test_no_agents_md_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "views.py"
            src.write_text("def view(request): pass\n", encoding="utf-8")
            result = run_analysis(str(src), {})
        findings = result["criteria"].get("AgentsCompliance", {}).get("findings", [])
        self.assertEqual(len(findings), 0)

    def test_glob_restricts_to_matching_files(self):
        # Rule only applies to views.py — services.py should be ignored
        findings = self._run(
            "def create_order(product_id):\n    pass\n",
            "param: **/services.py -> must_have: usuario",
            filename="views.py",
        )
        self.assertEqual(len(findings), 0, "Glob nao corresponde — nao deve flaggar")

    def test_init_generates_agents_md_django(self):
        from code_analyzer.agents_rules import generate_agents_md
        content = generate_agents_md("django", "6.1.0")
        self.assertIn("## [rules]", content)
        self.assertIn("login_required", content)
        self.assertIn("fields='__all__'", content)
        self.assertIn("## [thresholds]", content)

    def test_parse_rules_extracts_all_types(self):
        from code_analyzer.agents_rules import parse_rules
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "# AGENTS.md\n\n"
                "## [rules]\n"
                "param:     apps/services/** -> must_have: usuario\n"
                "decorator: apps/views/**   -> must_have: @login_required\n"
                "forbidden: **              -> no: fields='__all__'\n"
                "\n## [thresholds]\nmin_score: 7.0\n"
            )
            fname = f.name
        rules = parse_rules(Path(fname))
        self.assertEqual(len(rules), 3)
        types = {r.rule_type for r in rules}
        self.assertEqual(types, {"param", "decorator", "forbidden"})


class TestFindingHash(unittest.TestCase):
    """SL1 — deterministic finding_id via sha256(filepath|criterion|snippet)."""

    def _get_findings(self, code: str, filepath: str = "test.py") -> list:
        from code_analyzer.analyzer.context import AnalysisContext
        import ast
        tree = ast.parse(code)
        ctx = AnalysisContext(
            code=code,
            lines=code.splitlines(),
            filepath=filepath,
            classes={},
            functions=[],
            imports=[],
            import_nodes=[],
            tree=tree,
        )
        from code_analyzer.analyzer.detection_runner import detect_all
        criteria = detect_all(ctx)
        findings = []
        for crit in criteria.values():
            findings.extend(crit.get("findings", []))
        return findings

    def test_finding_id_is_present(self):
        code = "x = {'a': 1}\nfor k, v in x.items():\n    pass\n"
        findings = self._get_findings(code)
        if findings:
            self.assertIn("finding_id", findings[0])

    def test_finding_id_is_deterministic(self):
        from code_analyzer.analyzer.detectors import Finding
        f = Finding(
            criterion="SRP",
            location="linha 1",
            line=1,
            severity="ALTA",
            issue="teste",
            suggestion="fix",
            line_content="class Foo: pass",
        )
        id1 = f.to_dict("src/foo.py")["finding_id"]
        id2 = f.to_dict("src/foo.py")["finding_id"]
        self.assertEqual(id1, id2)

    def test_finding_id_differs_by_criterion(self):
        from code_analyzer.analyzer.detectors import Finding
        base = dict(location="l1", line=1, severity="ALTA", issue="x", suggestion="y", line_content="pass")
        f1 = Finding(criterion="SRP", **base)
        f2 = Finding(criterion="GodClass", **base)
        self.assertNotEqual(f1.to_dict("f.py")["finding_id"], f2.to_dict("f.py")["finding_id"])

    def test_finding_id_differs_by_filepath(self):
        from code_analyzer.analyzer.detectors import Finding
        f = Finding(criterion="SRP", location="l1", line=1, severity="ALTA", issue="x", suggestion="y", line_content="pass")
        self.assertNotEqual(f.to_dict("a.py")["finding_id"], f.to_dict("b.py")["finding_id"])

    def test_finding_id_stable_ignores_surrounding_whitespace(self):
        from code_analyzer.analyzer.detectors import _finding_hash
        h1 = _finding_hash("f.py", "SRP", "  class Foo: pass  ")
        h2 = _finding_hash("f.py", "SRP", "class Foo: pass")
        self.assertEqual(h1, h2)

    def test_finding_id_is_8_hex_chars(self):
        from code_analyzer.analyzer.detectors import _finding_hash
        h = _finding_hash("f.py", "SRP", "class Foo: pass")
        self.assertEqual(len(h), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestConfidenceField(unittest.TestCase):
    """IL1 — confidence: float on Finding and context-sensitive rules in 5 noisy detectors."""

    def _run(self, code: str, detector_name: str):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.py"
            p.write_text(textwrap.dedent(code), encoding="utf-8")
            result = run_analysis(str(p))
            return result.get("criteria", {}).get(detector_name, {}).get("findings", [])

    # --- Finding dataclass ---

    def test_confidence_default_is_1(self):
        from code_analyzer.analyzer.detectors import Finding
        f = Finding(criterion="X", location="l1", line=1, severity="ALTA", issue="x", suggestion="y")
        self.assertEqual(f.confidence, 1.0)

    def test_confidence_exposed_in_to_dict(self):
        from code_analyzer.analyzer.detectors import Finding
        f = Finding(criterion="X", location="l1", line=1, severity="ALTA", issue="x", suggestion="y", confidence=0.7)
        self.assertIn("confidence", f.to_dict("f.py"))
        self.assertAlmostEqual(f.to_dict("f.py")["confidence"], 0.7)

    # --- DictGet: external source → 0.9 ---

    def test_dict_get_confidence_external(self):
        code = """\
            import json
            def parse(raw):
                data = json.loads(raw)
                return data['key']
        """
        findings = self._run(code, "DictGet")
        self.assertTrue(findings, "expected DictGet finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.9)

    # --- InconsistentReturns: primitives → 0.85, custom class → 0.65 ---

    def test_inconsistent_returns_primitives_confidence(self):
        code = """\
            def f(x):
                if x:
                    return 1
                return "hello"
        """
        findings = self._run(code, "InconsistentReturns")
        self.assertTrue(findings, "expected InconsistentReturns finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.85)

    def test_inconsistent_returns_custom_class_confidence(self):
        code = """\
            def f(x):
                if x:
                    return MyClass()
                return 42
        """
        findings = self._run(code, "InconsistentReturns")
        self.assertTrue(findings, "expected InconsistentReturns finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.65)

    # --- LayerSeparation: raw I/O → 0.85, infra-modules → 0.55 ---

    def test_layer_separation_raw_io_confidence(self):
        code = """\
            class Service:
                def run(self):
                    with open('f') as fp:
                        return fp.read()
                def process(self, data):
                    return data.strip()
        """
        findings = self._run(code, "LayerSeparation")
        raw_io = [f for f in findings if "I/O" in f["issue"] or "open" in f["issue"]]
        self.assertTrue(raw_io, "expected raw I/O finding")
        self.assertAlmostEqual(raw_io[0]["confidence"], 0.85)

    def test_layer_separation_infra_modules_confidence(self):
        code = """\
            import requests
            class Service:
                def fetch(self, url):
                    return requests.get(url).json()
                def process(self, data):
                    return data
        """
        findings = self._run(code, "LayerSeparation")
        infra = [f for f in findings if "infraestrutura" in f["issue"]]
        self.assertTrue(infra, "expected infra-modules finding")
        self.assertAlmostEqual(infra[0]["confidence"], 0.55)

    # --- OrmInLoop → 0.9 ---

    def test_orm_in_loop_confidence(self):
        code = """\
            from django.db import models
            def process(ids):
                for i in ids:
                    obj = MyModel.objects.get(pk=i)
        """
        findings = self._run(code, "OrmInLoop")
        self.assertTrue(findings, "expected OrmInLoop finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.9)

    # --- FeatureEnvy: high ratio → 0.85, borderline → 0.65 ---

    def test_feature_envy_high_ratio_confidence(self):
        code = """\
            class A:
                def work(self):
                    self.other.x
                    self.other.y
                    self.other.z
                    self.other.w
                    self.other.v
        """
        findings = self._run(code, "FeatureEnvy")
        self.assertTrue(findings, "expected FeatureEnvy finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.85)

    def test_feature_envy_borderline_confidence(self):
        code = """\
            class A:
                def work(self):
                    self.own_attr
                    self.other.x
                    self.other.y
        """
        findings = self._run(code, "FeatureEnvy")
        self.assertTrue(findings, "expected FeatureEnvy finding")
        self.assertAlmostEqual(findings[0]["confidence"], 0.65)


class TestIntentStore(unittest.TestCase):
    """IL4 — IntentStore: persist, query, apply_intents, legacy migration."""

    def _store(self, tmp):
        from code_analyzer.intent_store import IntentStore
        return IntentStore(tmp)

    def test_get_returns_none_for_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            self.assertIsNone(store.get("nonexistent"))

    def test_save_and_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.save("abc123", "bug", note="real issue", criterion="SRP", location="f.py:10")
            intent = store.get("abc123")
            self.assertIsNotNone(intent)
            self.assertEqual(intent["answer"], "bug")
            self.assertEqual(intent["note"], "real issue")
            self.assertEqual(intent["criterion"], "SRP")

    def test_skip_not_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.save("abc123", "skip")
            self.assertIsNone(store.get("abc123"))
            # file should not be created for skip-only session
            import os
            self.assertFalse(os.path.exists(os.path.join(tmp, ".analyzer_intent.json")))

    def test_is_silenced_for_intentional(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.save("id1", "intentional")
            store.save("id2", "other_mechanism")
            store.save("id3", "bug")
            self.assertTrue(store.is_silenced("id1"))
            self.assertTrue(store.is_silenced("id2"))
            self.assertFalse(store.is_silenced("id3"))
            self.assertFalse(store.is_silenced("unknown"))

    def test_is_confirmed_for_bug(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.save("id1", "bug")
            store.save("id2", "intentional")
            self.assertTrue(store.is_confirmed("id1"))
            self.assertFalse(store.is_confirmed("id2"))
            self.assertFalse(store.is_confirmed("unknown"))

    def test_apply_intents_removes_silenced_and_recalculates_score(self):
        from code_analyzer.intent_store import IntentStore, apply_intents
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save("sil1", "intentional")
            criteria = {
                "Det": {
                    "score": 6,
                    "status": "PARCIAL",
                    "severity": "MEDIA",
                    "description": "d",
                    "penalty_per_finding": 2,
                    "findings": [
                        {"finding_id": "sil1", "confidence": 0.5, "issue": "x", "suggestion": "y", "location": "l", "line": 1, "line_content": ""},
                        {"finding_id": "keep1", "confidence": 0.9, "issue": "x", "suggestion": "y", "location": "l", "line": 2, "line_content": ""},
                    ],
                }
            }
            result = apply_intents(criteria, store)
            self.assertEqual(len(result["Det"]["findings"]), 1)
            self.assertEqual(result["Det"]["findings"][0]["finding_id"], "keep1")
            self.assertEqual(result["Det"]["score"], 8)  # 10 - 1*2

    def test_apply_intents_sets_confidence_1_for_confirmed_bug(self):
        from code_analyzer.intent_store import IntentStore, apply_intents
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save("bug1", "bug")
            criteria = {
                "Det": {
                    "score": 8,
                    "status": "PARCIAL",
                    "severity": "MEDIA",
                    "description": "d",
                    "penalty_per_finding": 2,
                    "findings": [
                        {"finding_id": "bug1", "confidence": 0.5, "issue": "x", "suggestion": "y", "location": "l", "line": 1, "line_content": ""},
                    ],
                }
            }
            result = apply_intents(criteria, store)
            self.assertEqual(result["Det"]["findings"][0]["confidence"], 1.0)
            self.assertEqual(len(result["Det"]["findings"]), 1)

    def test_legacy_migration(self):
        import json, os
        from code_analyzer.intent_store import IntentStore
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / ".analyzer_silenced.json"
            legacy.write_text(json.dumps({
                "aabbccdd": {"silenced_at": "2026-01-01T00:00:00", "reason": "known FP", "count": 3}
            }), encoding="utf-8")
            store = IntentStore(tmp)
            intent = store.get("aabbccdd")
            self.assertIsNotNone(intent)
            self.assertEqual(intent["answer"], "intentional")
            self.assertEqual(intent["note"], "known FP")
            self.assertFalse(os.path.exists(str(legacy)), "legacy file should be deleted after migration")
            self.assertTrue(os.path.exists(os.path.join(tmp, ".analyzer_intent.json")))


class TestIntentSession(unittest.TestCase):
    """IL3 — run_intent_session: non-interactive paths."""

    def _make_criteria(self, confs):
        from code_analyzer.analyzer.scoring import wrap_criterion
        findings = [
            {"finding_id": f"id{i}", "confidence": c, "location": f"l{i}",
             "line": i, "line_content": "", "issue": "x", "suggestion": "y"}
            for i, c in enumerate(confs, 1)
        ]
        return {"Det": wrap_criterion("Det", "MEDIA", "d", findings, 2)}

    def test_non_tty_applies_intents_only(self):
        """When ask_questions=False, session applies existing intents without asking."""
        from code_analyzer.intent_session import run_intent_session
        from code_analyzer.intent_store import IntentStore
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save("id1", "intentional", criterion="Det", location="l1")
            criteria = self._make_criteria([0.5, 0.9])
            result = run_intent_session("f.py", criteria, store, ask_questions=False)
            # id1 (confidence 0.5, silenced) should be removed
            remaining = result["Det"]["findings"]
            ids = [f["finding_id"] for f in remaining]
            self.assertNotIn("id1", ids)
            self.assertIn("id2", ids)

    def test_limit_zero_applies_intents_without_asking(self):
        from code_analyzer.intent_session import run_intent_session
        from code_analyzer.intent_store import IntentStore
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save("id1", "bug", criterion="Det", location="l1")
            criteria = self._make_criteria([0.5])
            result = run_intent_session("f.py", criteria, store, limit=0, ask_questions=False)
            # bug confirmed → confidence=1.0
            self.assertEqual(result["Det"]["findings"][0]["confidence"], 1.0)

    def test_no_questions_when_all_certain(self):
        """Queue is empty when all findings have high confidence — no IO needed."""
        from code_analyzer.intent_session import run_intent_session
        from code_analyzer.intent_store import IntentStore
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            criteria = self._make_criteria([0.9, 1.0, 0.85])
            # ask_questions=False forces non-interactive; all findings stay
            result = run_intent_session("f.py", criteria, store, ask_questions=False)
            self.assertEqual(len(result["Det"]["findings"]), 3)

    def test_session_returns_criteria_dict(self):
        from code_analyzer.intent_session import run_intent_session
        from code_analyzer.intent_store import IntentStore
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            criteria = self._make_criteria([0.5])
            result = run_intent_session("f.py", criteria, store, ask_questions=False)
            self.assertIsInstance(result, dict)
            self.assertIn("Det", result)
            self.assertIn("findings", result["Det"])


class TestQuestionQueue(unittest.TestCase):
    """IL2 — build_question_queue: triage, ordering, limit."""

    def _make_criteria(self, entries):
        """Helper: entries = list of (name, severity, penalty, findings_confs)."""
        from code_analyzer.analyzer.scoring import wrap_criterion
        criteria = {}
        for name, severity, penalty, confs in entries:
            findings = [
                {
                    "finding_id": f"{name}_{i}",
                    "location": f"linha {i}",
                    "line": i,
                    "line_content": "pass",
                    "issue": f"issue {i}",
                    "suggestion": "fix it",
                    "confidence": c,
                }
                for i, c in enumerate(confs, 1)
            ]
            crit = wrap_criterion(name, severity, f"desc {name}", findings, penalty)
            criteria[name] = crit
        return criteria

    def test_queue_excludes_high_confidence(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("DetA", "ALTA", 4, [0.9, 0.95]),
        ])
        queue = build_question_queue(criteria)
        self.assertEqual(queue, [], "findings com confidence >= 0.70 não devem entrar na fila")

    def test_queue_includes_low_confidence(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("DetA", "MEDIA", 2, [0.5, 0.9]),
        ])
        queue = build_question_queue(criteria, limit=5)
        self.assertEqual(len(queue), 1)
        self.assertAlmostEqual(queue[0]["confidence"], 0.5)
        self.assertEqual(queue[0]["criterion"], "DetA")

    def test_queue_ordered_by_impact(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("Baixo",  "BAIXA", 1, [0.5]),   # impact = 1*1 = 1
            ("Alto",   "ALTA",  4, [0.5]),   # impact = 4*3 = 12
            ("Medio",  "MEDIA", 2, [0.5]),   # impact = 2*2 = 4
        ])
        queue = build_question_queue(criteria, limit=10)
        impacts = [q["impact"] for q in queue]
        self.assertEqual(impacts, sorted(impacts, reverse=True))
        self.assertEqual(queue[0]["criterion"], "Alto")

    def test_queue_limit_respected(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("Det", "MEDIA", 2, [0.3, 0.4, 0.5, 0.6]),
        ])
        queue = build_question_queue(criteria, limit=2)
        self.assertEqual(len(queue), 2)

    def test_queue_empty_when_all_certain(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("DetA", "ALTA", 4, [1.0, 0.9, 0.85]),
            ("DetB", "MEDIA", 2, [0.8, 0.75]),
        ])
        queue = build_question_queue(criteria)
        self.assertEqual(queue, [])

    def test_queue_item_has_required_keys(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        criteria = self._make_criteria([
            ("Det", "MEDIA", 2, [0.5]),
        ])
        queue = build_question_queue(criteria, limit=1)
        self.assertEqual(len(queue), 1)
        for key in ("finding_id", "criterion", "location", "line", "line_content",
                    "issue", "suggestion", "confidence", "impact", "severity"):
            self.assertIn(key, queue[0], f"missing key: {key}")

    def test_queue_skips_already_answered_findings(self):
        from code_analyzer.analyzer.detection_runner import build_question_queue
        from code_analyzer.intent_store import IntentStore
        criteria = self._make_criteria([
            ("Det", "MEDIA", 2, [0.5, 0.4]),
        ])
        # grab the finding_id of the first finding
        fid = criteria["Det"]["findings"][0]["finding_id"]
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save(fid, "intentional")
            queue = build_question_queue(criteria, limit=10, intent_store=store)
            answered_ids = [q["finding_id"] for q in queue]
            self.assertNotIn(fid, answered_ids, "already-answered finding must not appear in queue")


class TestIntentReport(unittest.TestCase):
    """IL5 — write_intent_md generates INTENT.md from stored answers."""

    def _store_with(self, tmp: str, entries: list) -> "IntentStore":
        from code_analyzer.intent_store import IntentStore
        store = IntentStore(tmp)
        for finding_id, answer, note, criterion, location in entries:
            store.save(finding_id, answer, note=note, criterion=criterion, location=location)
        return store

    def test_empty_store_does_not_create_file(self):
        from code_analyzer.intent_report import write_intent_md
        from code_analyzer.intent_store import IntentStore
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            result = write_intent_md(store, Path(tmp))
            self.assertFalse(result)
            self.assertFalse((Path(tmp) / "INTENT.md").exists())

    def test_intentional_answer_appears_in_padroes_section(self):
        from code_analyzer.intent_report import write_intent_md
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with(tmp, [
                ("fid1", "intentional", "", "DictGet", "core.py:15"),
            ])
            write_intent_md(store, Path(tmp))
            content = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            self.assertIn("Padrões Intencionais", content)
            self.assertIn("DictGet", content)
            self.assertIn("core.py:15", content)
            self.assertNotIn("Bugs Confirmados", content)
            self.assertNotIn("Outro Mecanismo", content)

    def test_bug_answer_appears_in_bugs_section(self):
        from code_analyzer.intent_report import write_intent_md
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with(tmp, [
                ("fid2", "bug", "", "LayerSeparation", "views.py:42"),
            ])
            write_intent_md(store, Path(tmp))
            content = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            self.assertIn("Bugs Confirmados", content)
            self.assertIn("LayerSeparation", content)
            self.assertNotIn("Padrões Intencionais", content)

    def test_other_mechanism_with_note_appears(self):
        from code_analyzer.intent_report import write_intent_md
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with(tmp, [
                ("fid3", "other_mechanism", "Django middleware gerencia", "ContextManagerLeak", "mw.py:30"),
            ])
            write_intent_md(store, Path(tmp))
            content = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            self.assertIn("Outro Mecanismo", content)
            self.assertIn("Django middleware gerencia", content)
            self.assertIn("mw.py:30", content)

    def test_mixed_answers_produce_correct_sections(self):
        from code_analyzer.intent_report import write_intent_md
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with(tmp, [
                ("fid4", "bug",        "",     "InjectionRisk",   "api.py:88"),
                ("fid5", "intentional","",     "DictGet",         "util.py:5"),
                ("fid6", "other_mechanism","x","FeatureEnvy",     "svc.py:20"),
            ])
            write_intent_md(store, Path(tmp))
            content = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            self.assertIn("Bugs Confirmados (1)", content)
            self.assertIn("Padrões Intencionais (1)", content)
            self.assertIn("Outro Mecanismo (1)", content)

    def test_write_is_idempotent(self):
        from code_analyzer.intent_report import write_intent_md
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store_with(tmp, [
                ("fid7", "intentional", "", "DictGet", "x.py:1"),
            ])
            write_intent_md(store, Path(tmp))
            first = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            write_intent_md(store, Path(tmp))
            second = (Path(tmp) / "INTENT.md").read_text(encoding="utf-8")
            # timestamps may differ by 1s, compare structure
            first_lines = [l for l in first.splitlines() if not l.startswith("> Última")]
            second_lines = [l for l in second.splitlines() if not l.startswith("> Última")]
            self.assertEqual(first_lines, second_lines)


class TestDerivedInference(unittest.TestCase):
    """IL6 — _find_similar and _offer_derived_inference."""

    def _make_criteria(self, criterion: str, finding_ids: list, locations: list) -> dict:
        from code_analyzer.analyzer.scoring import wrap_criterion
        findings = [
            {
                "finding_id": fid,
                "location": loc,
                "line": i + 1,
                "line_content": "pass",
                "issue": "issue",
                "suggestion": "fix",
                "confidence": 0.5,
            }
            for i, (fid, loc) in enumerate(zip(finding_ids, locations))
        ]
        crit = wrap_criterion(criterion, "MEDIA", "desc", findings, 2)
        return {criterion: crit}

    def test_find_similar_returns_same_criterion(self):
        from code_analyzer.intent_session import _find_similar
        from code_analyzer.intent_store import IntentStore
        criteria = self._make_criteria("DictGet", ["f1", "f2", "f3"], ["a.py:1", "a.py:2", "a.py:3"])
        question = {"finding_id": "f1", "criterion": "DictGet"}
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            similar = _find_similar(question, criteria, store)
            self.assertEqual(len(similar), 2)
            ids = {f["finding_id"] for f in similar}
            self.assertIn("f2", ids)
            self.assertIn("f3", ids)

    def test_find_similar_excludes_current_finding(self):
        from code_analyzer.intent_session import _find_similar
        from code_analyzer.intent_store import IntentStore
        criteria = self._make_criteria("DictGet", ["f1", "f2"], ["a.py:1", "a.py:2"])
        question = {"finding_id": "f1", "criterion": "DictGet"}
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            similar = _find_similar(question, criteria, store)
            self.assertNotIn("f1", [f["finding_id"] for f in similar])

    def test_find_similar_excludes_already_answered(self):
        from code_analyzer.intent_session import _find_similar
        from code_analyzer.intent_store import IntentStore
        criteria = self._make_criteria("DictGet", ["f1", "f2", "f3"], ["a.py:1", "a.py:2", "a.py:3"])
        question = {"finding_id": "f1", "criterion": "DictGet"}
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            store.save("f2", "intentional")
            similar = _find_similar(question, criteria, store)
            ids = [f["finding_id"] for f in similar]
            self.assertNotIn("f2", ids)
            self.assertIn("f3", ids)

    def test_find_similar_different_criterion_excluded(self):
        from code_analyzer.intent_session import _find_similar
        from code_analyzer.intent_store import IntentStore
        from code_analyzer.analyzer.scoring import wrap_criterion
        criteria = {
            "DictGet": self._make_criteria("DictGet", ["f1", "f2"], ["a.py:1", "a.py:2"])["DictGet"],
            "FeatureEnvy": self._make_criteria("FeatureEnvy", ["f3"], ["a.py:9"])["FeatureEnvy"],
        }
        question = {"finding_id": "f1", "criterion": "DictGet"}
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            similar = _find_similar(question, criteria, store)
            ids = [f["finding_id"] for f in similar]
            self.assertNotIn("f3", ids)

    def test_offer_inference_saves_batch_when_confirmed(self):
        from code_analyzer.intent_session import _offer_derived_inference
        from code_analyzer.intent_store import IntentStore
        similar = [
            {"finding_id": "fx", "location": "a.py:5"},
            {"finding_id": "fy", "location": "a.py:6"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            with unittest.mock.patch("builtins.input", return_value="s"):
                count = _offer_derived_inference(similar, "intentional", "", "DictGet", store)
            self.assertEqual(count, 2)
            self.assertIsNotNone(store.get("fx"))
            self.assertIsNotNone(store.get("fy"))
            self.assertEqual(store.get("fx")["answer"], "intentional")

    def test_offer_inference_saves_nothing_when_declined(self):
        from code_analyzer.intent_session import _offer_derived_inference
        from code_analyzer.intent_store import IntentStore
        similar = [{"finding_id": "fz", "location": "a.py:7"}]
        with tempfile.TemporaryDirectory() as tmp:
            store = IntentStore(tmp)
            with unittest.mock.patch("builtins.input", return_value="n"):
                count = _offer_derived_inference(similar, "intentional", "", "DictGet", store)
            self.assertEqual(count, 0)
            self.assertIsNone(store.get("fz"))


if __name__ == "__main__":
    unittest.main()
