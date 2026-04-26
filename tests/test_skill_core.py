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

from analyzer import run_analysis  # noqa: E402
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

    def test_cli_json_mode_returns_machine_readable_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.py"
            source.write_text(
                "def ok():\n"
                "    return 1\n",
                encoding="utf-8",
            )

            analyze_cmd = [
                "node",
                "bin/cli.js",
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
            if analyze_result.returncode != 0 and "spawn EPERM" in analyze_result.stderr:
                self.skipTest("Node child_process spawn is blocked in this environment")
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
                "node",
                "bin/cli.js",
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
            self.assertTrue(Path(orchestrator.backup_path).exists())


if __name__ == "__main__":
    unittest.main()
