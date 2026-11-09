#!/usr/bin/env sh
# Report phase completion status for task_plan.md (stdout only, always exit 0).
# Default plan path: .kiro/plan/task_plan.md (relative to current directory).

# Explicit creation validation; the existing localized advisory path stays unchanged.
VALIDATE=0
VALIDATION_PLAN=""
for _arg in "$@"; do
    case "$_arg" in
        --validate) VALIDATE=1 ;;
        *) [ -z "$VALIDATION_PLAN" ] && VALIDATION_PLAN="$_arg" ;;
    esac
done
if [ "$VALIDATE" -eq 1 ]; then
    PLAN_FILE="${VALIDATION_PLAN:-.kiro/plan/task_plan.md}"
    [ -f "$PLAN_FILE" ] || { echo "[planning-with-files] Plan format invalid: task_plan.md was not found." >&2; exit 1; }
fi

# Creation validation is deliberately separate from advisory/gated completion.
# Keep one native status per phase, including the existing inline form. This
# never repairs or writes the plan, changes attestation, or weakens Stop guards.
if [ "$VALIDATE" -eq 1 ]; then
    awk '
        function finish_phase() {
            if (in_phase && statuses != 1) invalid = 1
        }
        /^### Phase([ \t]|$)/ {
            finish_phase()
            phases++
            in_phase = 1
            statuses = 0
        }
        !/^### Phase([ \t]|$)/ && /^#[ \t]|^##[ \t]|^###[ \t]/ {
            finish_phase()
            in_phase = 0
        }
        in_phase {
            line = $0
            statuses += gsub(/\*\*Status:\*\*[ \t]+(pending|in_progress|complete)([^[:alnum:]_]|$)/, "&", line)
            line = $0
            statuses += gsub(/\[(pending|in_progress|complete)\]/, "&", line)
        }
        END {
            finish_phase()
            if (!phases || invalid) {
                print "[planning-with-files] Plan format invalid: use ### Phase headings with exactly one native status per phase."
                exit 1
            }
            printf "[planning-with-files] Plan format valid (%d phases).\n", phases
        }
    ' "$PLAN_FILE"
    exit "$?"
fi

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

PLAN_FILE="${1:-.kiro/plan/task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
  echo "[planning-with-files] No task plan at $PLAN_FILE — run bootstrap or specify path."
  exit 0
fi

TOTAL=$(grep -c "### Phase" "$PLAN_FILE" 2>/dev/null || echo 0)
COMPLETE=$(grep -cF "**Status:** complete" "$PLAN_FILE" 2>/dev/null || echo 0)
IN_PROGRESS=$(grep -cF "**Status:** in_progress" "$PLAN_FILE" 2>/dev/null || echo 0)
PENDING=$(grep -cF "**Status:** pending" "$PLAN_FILE" 2>/dev/null || echo 0)

if [ "$COMPLETE" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
  COMPLETE=$(grep -c "\[complete\]" "$PLAN_FILE" 2>/dev/null || echo 0)
  IN_PROGRESS=$(grep -c "\[in_progress\]" "$PLAN_FILE" 2>/dev/null || echo 0)
  PENDING=$(grep -c "\[pending\]" "$PLAN_FILE" 2>/dev/null || echo 0)
fi

: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"
: "${PENDING:=0}"

# issue #191: TOTAL=0 -> not phase-structured, stay silent
if [ "$TOTAL" -eq 0 ]; then
    exit 0
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
  echo "[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL)."
else
  echo "[planning-with-files] In progress ($COMPLETE/$TOTAL phases complete)."
  if [ "$IN_PROGRESS" -gt 0 ]; then
    echo "[planning-with-files] $IN_PROGRESS phase(s) in_progress."
  fi
  if [ "$PENDING" -gt 0 ]; then
    echo "[planning-with-files] $PENDING phase(s) pending."
  fi
fi
exit 0
