"""Keep the optional resume eval bound to each phase's first status.

The eval's single-quoted YAML regex values are literal strings, so these
checks need only the standard library, not skill-lens or a YAML dependency.
"""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_FILE = (
    REPO_ROOT / "skills/planning-with-files/evals/planning-with-files.eval.yaml"
)


def _plan(phase_two="complete", phase_three="pending", *, child_two="", child_three=""):
    return (
        "### Phase 2: add and list\n"
        f"**Status:** {phase_two}\n{child_two}"
        "### Phase 3: done and delete\n"
        f"**Status:** {phase_three}\n{child_three}"
    )


# Each expected tuple independently describes Phase 2 complete / Phase 3 open.
RESUME_CASES = [
    ("pending", _plan(), (True, True)),
    ("in_progress", _plan(phase_three="in_progress"), (True, True)),
    ("not_started", _plan(phase_three="not_started"), (True, True)),
    ("titlecase_pending", _plan(phase_three="Pending"), (True, True)),
    ("decorated_pending", _plan(phase_three="🔄 pending"), (True, True)),
    ("complete", _plan(phase_three="complete"), (True, False)),
    ("titlecase_complete", _plan(phase_three="Complete"), (True, False)),
    ("quoted_complete", _plan(phase_three="`complete`"), (True, False)),
    ("decorated_complete", _plan(phase_three="✅ Complete"), (True, False)),
    (
        "incomplete_phase_two_with_complete_child",
        _plan("pending", child_two="#### Unit tests\n**Status:** complete\n"),
        (False, True),
    ),
    (
        "complete_phase_three_with_pending_child",
        _plan(phase_three="complete", child_three="#### Follow-up\n**Status:** pending\n"),
        (True, False),
    ),
]
for _level in (1, 2, 3):
    RESUME_CASES.append(
        (
            f"phase_two_stops_at_level_{_level}_heading",
            "### Phase 2: add and list\nNo status recorded.\n"
            + "#" * _level
            + " Other section\n**Status:** complete\n"
            + "### Phase 3: done and delete\n**Status:** pending\n",
            (False, True),
        )
    )
    RESUME_CASES.append(
        (
            f"phase_three_stops_at_level_{_level}_heading",
            "### Phase 2: add and list\n**Status:** complete\n"
            + "### Phase 3: done and delete\nNo status recorded.\n"
            + "#" * _level
            + " Other section\n**Status:** pending\n",
            (True, False),
        )
    )


def _resume_patterns(path=EVAL_FILE):
    text = path.read_text(encoding="utf-8")
    case = text.split("  - name: resumes-from-its-own-plan\n", 1)[1]
    case = case.split("\n  - name:", 1)[0]
    patterns = re.findall(r"(?m)^[ \t]+value: '([^'\r\n]*)'[ \t]*$", case)
    if len(patterns) != 2:
        raise AssertionError("the resume case must declare two single-quoted regex assertions")
    return patterns


class ResumePhaseAssertionsTests(unittest.TestCase):
    def test_resume_uses_first_status_and_preserves_heading_bounds(self):
        patterns = _resume_patterns()
        for name, plan, expected in RESUME_CASES:
            with self.subTest(case=name):
                actual = tuple(re.search(pattern, plan) is not None for pattern in patterns)
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
