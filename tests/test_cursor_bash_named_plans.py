"""Named-plan coverage for Cursor's bash hook route (issue #336).

Mirrors tests/test_cursor_powershell_named_plans.py for the hooks.json path:
explicit PLAN_ID must beat a root task_plan.md, stop.sh must evaluate the
selected plan's phases, and a missing PLAN_ID must fail closed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_HOOKS = REPO_ROOT / ".cursor" / "hooks"
SCRUB_VARS = ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED")


@unittest.skipUnless(shutil.which("sh"), "requires a POSIX sh")
class CursorBashNamedPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="pwf-cursor-bash-named-")
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def clean_env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        for name in SCRUB_VARS:
            env.pop(name, None)
        env.update(extra)
        return env

    def write_root_plan(
        self,
        marker: str = "ROOT-PLAN-MARKER",
        *,
        status: str = "complete",
    ) -> None:
        (self.workspace / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** {status}\n",
            encoding="utf-8",
        )
        (self.workspace / "progress.md").write_text(
            "ROOT-PROGRESS-MARKER\n", encoding="utf-8"
        )

    def write_named_plan(
        self,
        slug: str,
        marker: str,
        *,
        active: bool = False,
        status: str = "in_progress",
    ) -> Path:
        plan_dir = self.workspace / ".planning" / slug
        plan_dir.mkdir(parents=True)
        (plan_dir / "task_plan.md").write_text(
            f"# {marker}\n### Phase 1\n**Status:** {status}\n",
            encoding="utf-8",
        )
        (plan_dir / "progress.md").write_text(
            f"{marker}-PROGRESS\n", encoding="utf-8"
        )
        if active:
            (self.workspace / ".planning" / ".active_plan").write_text(
                f"{slug}\n", encoding="utf-8"
            )
        return plan_dir

    def run_hook(
        self,
        name: str,
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        script = CURSOR_HOOKS / f"{name}.sh"
        return subprocess.run(
            ["sh", str(script)],
            cwd=str(self.workspace),
            env=env or self.clean_env(),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=60,
        )

    def test_plan_id_overrides_root_and_active_pointer(self) -> None:
        self.write_root_plan("ROOT_ONLY", status="complete")
        self.write_named_plan("other", "OTHER_ONLY", active=True, status="pending")
        self.write_named_plan("selected", "SELECTED_ONLY", status="in_progress")

        env = self.clean_env(PLAN_ID="selected")
        submit = self.run_hook("user-prompt-submit", env=env)
        stop = self.run_hook("stop", env=env)
        post = self.run_hook("post-tool-use", env=env)
        start = self.run_hook("session-start", env=env)

        self.assertEqual(0, submit.returncode, submit.stderr)
        self.assertIn("SELECTED_ONLY", submit.stdout)
        self.assertIn("SELECTED_ONLY-PROGRESS", submit.stdout)
        self.assertNotIn("ROOT_ONLY", submit.stdout)
        self.assertNotIn("OTHER_ONLY", submit.stdout)

        self.assertEqual(0, stop.returncode, stop.stderr)
        self.assertIn("Task incomplete (0/1 phases done)", stop.stdout)

        self.assertEqual(0, post.returncode, post.stderr)
        self.assertIn("Update progress.md", json.loads(post.stdout)["additional_context"])

        self.assertEqual(0, start.returncode, start.stderr)
        self.assertIn("SELECTED_ONLY", json.loads(start.stdout)["additional_context"])

    def test_missing_plan_id_fails_closed(self) -> None:
        self.write_root_plan("ROOT_ONLY", status="complete")
        self.write_named_plan("selected", "SELECTED_ONLY", active=True)

        env = self.clean_env(PLAN_ID="missing")
        submit = self.run_hook("user-prompt-submit", env=env)
        stop = self.run_hook("stop", env=env)
        post = self.run_hook("post-tool-use", env=env)

        self.assertEqual(0, submit.returncode, submit.stderr)
        self.assertIn("PLAN_ID does not name a plan directory", submit.stdout)
        self.assertNotIn("ROOT_ONLY", submit.stdout)
        self.assertNotIn("SELECTED_ONLY", submit.stdout)

        self.assertEqual(0, stop.returncode, stop.stderr)
        self.assertEqual("", stop.stdout.strip())

        self.assertEqual(0, post.returncode, post.stderr)
        self.assertEqual({}, json.loads(post.stdout))

    def test_legacy_root_still_works_without_named_plans(self) -> None:
        self.write_root_plan()
        result = self.run_hook("user-prompt-submit")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ROOT-PLAN-MARKER", result.stdout)
