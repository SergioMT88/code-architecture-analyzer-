import json
import tempfile
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyzer import run_analysis, prune_criteria  # noqa: E402
from artifact_manager import ArtifactRegistry  # noqa: E402
from refactorer import RefactoringOrchestrator, refactor_file  # noqa: E402
from report_generator import ReportGenerator  # noqa: E402


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
            self.assertIn("7 parametros", findings[0]["issue"])

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
            self.assertIn("8 parametros", findings[0]["issue"])

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
            self.assertIn("nao usa", findings[0]["issue"])

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
            self.assertIn("Print dentro de", findings[0]["issue"])

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
            self.assertIn(".analyzer.json", init_payload.get("file", ""))

            # init novamente (ja existe) --json
            init2_result = subprocess.run(
                init_cmd, cwd=tmp, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(init2_result.returncode, 0)
            init2_payload = json.loads(init2_result.stdout)
            self.assertFalse(init2_payload["success"])

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
        from orchestrator import load_config
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
        from orchestrator import load_config
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


if __name__ == "__main__":
    unittest.main()
