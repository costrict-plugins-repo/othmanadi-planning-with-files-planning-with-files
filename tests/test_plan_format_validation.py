"""Explicit creation validation must reject plans that native tracking cannot see."""
from __future__ import annotations

import os
import codecs
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PWSH = shutil.which("pwsh") or shutil.which("powershell")
WINDOWS_POWERSHELL = shutil.which("powershell") if os.name == "nt" else None
BOM_FILES = (
    ".kiro/skills/planning-with-files/assets/scripts/check-complete.ps1",
    *(f"skills/i18n/planning-with-files-{lang}/scripts/check-complete.ps1"
      for lang in ("ar", "de", "es", "zh", "zht")),
    "skills/i18n/planning-with-files-es/scripts/init-session.ps1",
)
BAD_PLANS = (
    "# Todo CLI implementation\n\n## Phases\n"
    "- [x] Read project requirements.\n"
    "- [x] Implement the standard-library CLI and durable JSON storage.\n"
    "- [x] Verify commands, persistence, and errors with isolated integration tests.\n",
    "# Todo CLI implementation\n\n## Phases\n"
    "1. Read acceptance requirements, complete.\n"
    "2. Implement standard-library CLI and persistence, complete.\n"
    "3. Verify commands, persistence, and errors, complete.\n",
)
VALID = "# Work\n\n### Phase 1: Inspect\n**Status:** in_progress\n\n### Phase 2: Verify\n**Status:** pending\n"


def child_env():
    return {k: v for k, v in os.environ.items()
            if k not in {"PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"}}


class PlanFormatValidationTests(unittest.TestCase):
    def runtimes(self):
        yield "sh", ["sh", str(SCRIPTS / "check-complete.sh")], "--validate"
        if PWSH:
            yield "powershell", [PWSH, "-NoProfile", "-File", str(SCRIPTS / "check-complete.ps1")], "-Validate"

    def check(self, command, cwd, *args):
        return subprocess.run([*command, *args], cwd=cwd, env=child_env(),
                              capture_output=True, text=True, encoding="utf-8", check=False)

    def test_saved_untrackable_plan_shapes_fail_explicit_validation_without_rewrite(self):
        for runtime, command, flag in self.runtimes():
            for bad in BAD_PLANS:
                with self.subTest(runtime=runtime, shape=bad), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    plan = root / "task_plan.md"
                    plan.write_text(bad, encoding="utf-8")
                    result = self.check(command, root, flag)
                    self.assertNotEqual(0, result.returncode, result.stdout)
                    self.assertIn("phase", (result.stdout + result.stderr).lower())
                    self.assertEqual(bad, plan.read_text(encoding="utf-8"))
                    self.assertEqual(["task_plan.md"], sorted(p.name for p in root.iterdir()))

    def test_phase_heading_case_must_match_the_native_completion_counter(self):
        for runtime, command, flag in self.runtimes():
            for heading in ("### phase 1: Inspect", "### PHASE 1: Inspect"):
                with self.subTest(runtime=runtime, heading=heading), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "task_plan.md").write_text(heading + "\n**Status:** pending\n", encoding="utf-8")
                    self.assertEqual("", self.check(command, root).stdout.strip())
                    self.assertNotEqual(0, self.check(command, root, flag).returncode)

    @unittest.skipUnless(WINDOWS_POWERSHELL, "requires Windows PowerShell 5.1 encoding behavior")
    def test_spanish_initializer_preserves_accents_in_windows_powershell(self):
        script = ROOT / "skills" / "i18n" / "planning-with-files-es" / "scripts" / "init-session.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.check([WINDOWS_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("intención", (root / "task_plan.md").read_text(encoding="utf-8-sig"))

    def test_windows_powershell_sources_retain_their_utf8_bom(self):
        # These seven sources already shipped a BOM. WinPS 5.1 uses ANSI for
        # UTF-8 source without one, corrupting literals or even parsing them.
        for name in BOM_FILES:
            with self.subTest(source=name):
                self.assertTrue((ROOT / name).read_bytes().startswith(codecs.BOM_UTF8))

    @unittest.skipUnless(WINDOWS_POWERSHELL, "requires Windows PowerShell 5.1 encoding behavior")
    def test_localized_validation_and_advisory_work_in_windows_powershell(self):
        markers = {
            "ar": ("المرحلة", "الحالة:"),
            "de": ("Phase", "Status:"),
            "es": ("Phase", "Estado:"),
            "zh": ("阶段", "状态："),
            "zht": ("階段", "狀態："),
        }
        routes = [(ROOT / ".kiro/skills/planning-with-files/assets/scripts/check-complete.ps1", "Phase", "Status:")]
        routes += [(ROOT / "skills/i18n" / f"planning-with-files-{lang}" / "scripts/check-complete.ps1", phase, status)
                   for lang, (phase, status) in markers.items()]
        for script, phase, status in routes:
            with self.subTest(source=str(script)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan = root / "task_plan.md"
                plan.write_text(f"### {phase} 1: Inspect\n**{status}** pending\n", encoding="utf-8-sig")
                command = [WINDOWS_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
                for flags in (("-Validate", "-PlanFile", str(plan)), ("-PlanFile", str(plan))):
                    result = subprocess.run([*command, *flags], cwd=root, env=child_env(), capture_output=True,
                                            text=True, encoding="utf-8", errors="replace", check=False)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("valid (1 phases)" if "-Validate" in flags else "0/1", result.stdout)

    def test_one_status_per_phase_is_required_not_only_an_aggregate_count(self):
        bad = "### Phase 1\n**Status:** complete\n**Status:** pending\n### Phase 2\nNo status yet.\n"
        for runtime, command, flag in self.runtimes():
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "task_plan.md").write_text(bad, encoding="utf-8")
                self.assertNotEqual(0, self.check(command, root, flag).returncode)

    def test_validation_accepts_pending_work_and_existing_inline_status_format(self):
        for runtime, command, flag in self.runtimes():
            for valid in (VALID, "### Phase 1: Inspect [complete]\n### Phase 2: Verify [pending]\n"):
                with self.subTest(runtime=runtime, plan=valid), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "task_plan.md").write_text(valid, encoding="utf-8")
                    result = self.check(command, root, flag)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("2", result.stdout)

    def test_validation_of_missing_explicit_file_fails_without_creating_files(self):
        for runtime, command, flag in self.runtimes():
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result = self.check(command, root, flag, "missing.md")
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(list(root.iterdir()))

    def test_default_advisory_retains_silent_zero_phase_compatibility(self):
        for runtime, command, _ in self.runtimes():
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "task_plan.md").write_text(BAD_PLANS[0], encoding="utf-8")
                result = self.check(command, root)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stdout.strip())

    def test_initializer_output_is_valid_and_native_completion_counts_five_phases(self):
        for runtime, command, flag in self.runtimes():
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init = (["sh", str(SCRIPTS / "init-session.sh")] if runtime == "sh" else
                        [PWSH, "-NoProfile", "-File", str(SCRIPTS / "init-session.ps1")])
                result = self.check(init, root)
                self.assertEqual(0, result.returncode, result.stderr)
                validated = self.check(command, root, flag)
                self.assertEqual(0, validated.returncode, validated.stderr)
                self.assertIn("5", validated.stdout)
                native = self.check(command, root)
                self.assertIn("0/5", native.stdout)

    def test_doctor_reports_untrackable_existing_plan_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "task_plan.md"
            plan.write_text(BAD_PLANS[0], encoding="utf-8")
            result = self.check(["sh", str(SCRIPTS / "plan-doctor.sh")], root)
            lines = [line for line in result.stdout.splitlines() if "plan format:" in line]
            self.assertEqual(1, len(lines), result.stdout)
            self.assertTrue(lines[0].startswith("FAIL"), lines)
            self.assertEqual(BAD_PLANS[0], plan.read_text(encoding="utf-8"))

    def test_translated_initializers_keep_their_native_tracking_contract(self):
        for language in ("ar", "de", "es", "zh", "zht"):
            scripts = ROOT / "skills" / "i18n" / f"planning-with-files-{language}" / "scripts"
            runtimes = [("sh", ["sh"], ".sh", "--validate")]
            if PWSH:
                runtimes.append(("powershell", [PWSH, "-NoProfile", "-File"], ".ps1", "-Validate"))
            for runtime, shell, suffix, flag in runtimes:
                with self.subTest(language=language, runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    init = self.check([*shell, str(scripts / ("init-session" + suffix))], root)
                    self.assertEqual(0, init.returncode, init.stderr)
                    command = [*shell, str(scripts / ("check-complete" + suffix))]
                    result = self.check(command, root, flag)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("5 phases", result.stdout)
                    completion = self.check(command, root)
                    self.assertIn("0/5", completion.stdout)

    def test_kiro_validation_uses_its_existing_default_plan_path(self):
        scripts = ROOT / ".kiro" / "skills" / "planning-with-files" / "assets" / "scripts"
        runtimes = [("sh", ["sh", str(scripts / "check-complete.sh")], "--validate")]
        if PWSH:
            runtimes.append(("powershell", [PWSH, "-NoProfile", "-File", str(scripts / "check-complete.ps1")], "-Validate"))
        for runtime, command, flag in runtimes:
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan = root / ".kiro" / "plan" / "task_plan.md"
                plan.parent.mkdir(parents=True)
                plan.write_text(VALID, encoding="utf-8")
                result = self.check(command, root, flag)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Plan format valid (2 phases)", result.stdout)
                plan.write_text(BAD_PLANS[0], encoding="utf-8")
                self.assertNotEqual(0, self.check(command, root, flag).returncode)


if __name__ == "__main__":
    unittest.main()
