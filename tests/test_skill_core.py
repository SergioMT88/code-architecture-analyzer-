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
                "data = {'a': 1}\n"
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
                "data = {'a': 1}\n"
                "value = data.get('a')\n",
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
                "tool_warnings": ["pylint nao instalado — analise parcial", "ruff nao instalado — analise parcial"]
            }
            
            generator = ReportGenerator(str(source), analysis_data, output_dir=tmp)
            md_report = generator.generate_markdown_report()
            html_report = generator.generate_html_report()
            
            # Valida presença no Markdown
            self.assertIn("> [!WARNING]", md_report)
            self.assertIn("pylint nao instalado", md_report)
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
        from code_analyzer.orchestrator import _get_snippet
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


if __name__ == "__main__":
    unittest.main()
