"""Guard PR342's selected-plan readers against unsafe legacy fallback (#336).

The same observable contract runs against the bash repair and the existing
PowerShell reference. No model, host session history or user plan is needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOOKS = Path(__file__).resolve().parents[1] / ".cursor" / "hooks"
SH = shutil.which("sh")
PS = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")
READERS = ("session-start", "user-prompt-submit", "post-tool-use", "stop")


class SelectionContract:
    powershell = False

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pwf-cursor-selection-")
        self.cwd = Path(self.temp.name)
        self.plan(self.cwd, "UNRELATED_ROOT")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def plan(self, directory: Path, marker: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** in_progress\n", encoding="utf-8"
        )
        (directory / "progress.md").write_text(marker + "-PROGRESS\n", encoding="utf-8")

    def run_readers(self, *, cwd: Path | None = None, **extra: str) -> dict[str, str]:
        env = dict(os.environ)
        for key in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"):
            env.pop(key, None)
        env.update(extra)
        result = {}
        for name in READERS:
            path = HOOKS / (name + (".ps1" if self.powershell else ".sh"))
            command = (
                [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
                if self.powershell else [SH, str(path)]
            )
            proc = subprocess.run(
                command, cwd=cwd or self.cwd, env=env, input="{}",
                capture_output=True, text=True, encoding="utf-8-sig", timeout=30,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            result[name] = proc.stdout.strip()
        return result

    def assert_refused(self, outputs: dict[str, str]) -> None:
        self.assertNotIn("UNRELATED_ROOT", outputs["user-prompt-submit"])
        self.assertNotIn("UNRELATED_ROOT", outputs["session-start"])
        self.assertEqual({}, json.loads(outputs["post-tool-use"]))
        self.assertEqual("", outputs["stop"])

    def assert_selected(self, outputs: dict[str, str], marker: str) -> None:
        self.assertIn(marker, outputs["user-prompt-submit"])
        self.assertIn(marker + "-PROGRESS", outputs["user-prompt-submit"])
        self.assertIn(marker, json.loads(outputs["session-start"])["additional_context"])
        self.assertIn("Update progress.md", json.loads(outputs["post-tool-use"])["additional_context"])
        self.assertIn("Task incomplete (0/1 phases done)", outputs["stop"])

    def test_ambiguous_named_plans_refuse_every_reader(self) -> None:
        self.plan(self.cwd / ".planning/alpha", "ALPHA")
        self.plan(self.cwd / ".planning/beta", "BETA")
        (self.cwd / ".planning/.active_plan").write_text("alpha\n")
        self.assert_refused(self.run_readers())

    def test_missing_project_root_pin_refuses_every_reader(self) -> None:
        self.assert_refused(self.run_readers(PWF_PLAN_ROOT=str(self.cwd / "missing")))

    def test_relative_project_root_pin_refuses_every_reader(self) -> None:
        self.plan(self.cwd / "relative", "UNRELATED_ROOT_RELATIVE")
        self.assert_refused(self.run_readers(PWF_PLAN_ROOT="relative"))

    def test_active_pointer_directory_refuses_every_reader(self) -> None:
        (self.cwd / ".planning/.active_plan").mkdir(parents=True)
        self.assert_refused(self.run_readers())

    def test_unsafe_pointer_with_named_candidate_refuses_every_reader(self) -> None:
        self.plan(self.cwd / ".planning/alpha", "UNRELATED_ROOT_NAMED")
        (self.cwd / ".planning/.active_plan").mkdir()
        self.assert_refused(self.run_readers())

    def test_unused_unsafe_pointer_does_not_override_explicit_plan_id(self) -> None:
        self.plan(self.cwd / ".planning/alpha", "EXPLICIT_NAMED")
        (self.cwd / ".planning/.active_plan").mkdir()
        self.assert_selected(self.run_readers(PLAN_ID="alpha"), "EXPLICIT_NAMED")

    def test_named_only_plan_remains_selected(self) -> None:
        project = self.cwd / "named-project"
        self.plan(project / ".planning/alpha", "NAMED_ONLY")
        self.assert_selected(self.run_readers(cwd=project, PLAN_ID="alpha"), "NAMED_ONLY")

    def test_explicit_project_root_legacy_plan_remains_selected(self) -> None:
        project = self.cwd / "pinned-project"
        self.plan(project, "PINNED_LEGACY")
        self.assert_selected(self.run_readers(PWF_PLAN_ROOT=str(project)), "PINNED_LEGACY")

    def test_explicit_project_root_named_plan_remains_selected(self) -> None:
        project = self.cwd / "pinned-project"
        self.plan(project / ".planning/alpha", "PINNED_NAMED")
        self.assert_selected(
            self.run_readers(PWF_PLAN_ROOT=str(project), PLAN_ID="alpha"), "PINNED_NAMED"
        )

    def test_stale_pointer_preserves_legitimate_legacy_fallback(self) -> None:
        (self.cwd / ".planning").mkdir()
        (self.cwd / ".planning/.active_plan").write_text("missing\n")
        self.assert_selected(self.run_readers(), "UNRELATED_ROOT")

    def test_disabled_reader_outputs_remain_noops(self) -> None:
        self.plan(self.cwd / ".planning/alpha", "NAMED_DISABLED")
        output = self.run_readers(PLAN_ID="alpha", PLANNING_DISABLED="1")
        self.assertEqual({}, json.loads(output["session-start"]))
        self.assertEqual("", output["user-prompt-submit"])
        self.assertEqual({}, json.loads(output["post-tool-use"]))
        self.assertEqual("", output["stop"])


@unittest.skipUnless(SH, "requires POSIX sh")
class CursorBashSelectionTests(SelectionContract, unittest.TestCase):
    pass


@unittest.skipUnless(PS, "requires PowerShell reference")
class CursorPowerShellSelectionTests(SelectionContract, unittest.TestCase):
    powershell = True
