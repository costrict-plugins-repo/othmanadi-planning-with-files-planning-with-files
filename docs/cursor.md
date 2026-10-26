# Cursor IDE Setup

How to use planning-with-files with Cursor IDE — now with full hook support.

---

## Installation

### Option 1: Copy into .cursor (Recommended)

Run from your project root:

Before copying, check `.cursor/hooks/` for user-owned scripts with the same names
as the supplied scripts, such as `stop.sh`. Back up or rename those files and
update their existing registrations first; the copy replaces same-named scripts.

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p .cursor/skills
cp -r planning-with-files/.cursor/skills/planning-with-files .cursor/skills/
cp -r planning-with-files/.cursor/hooks .cursor/
cp planning-with-files/.cursor/hooks.windows.json .cursor/
if [ -e .cursor/hooks.json ]; then
  echo "Kept the existing .cursor/hooks.json. Merge the planning-with-files entries into it."
else
  cp planning-with-files/.cursor/hooks.json .cursor/
fi
```

This copies the skill files, hook scripts, and hooks config to your project. It
works whether or not the project already has a `.cursor` directory. The skill
lands in `.cursor/skills/planning-with-files/` and the scripts in
`.cursor/hooks/`, next to any rules, skills, and hooks you already have. Do not
use `cp -r planning-with-files/.cursor .cursor`. When `.cursor` already exists,
`cp` copies into it and creates `.cursor/.cursor/`, where Cursor does not look.

The commands never overwrite an existing `hooks.json`. If they printed the
"Kept the existing" message, merge the entries as described in
[Existing hooks.json](#existing-hooksjson). A script of yours in `.cursor/hooks/`
with the same name as one of ours (for example `stop.sh`) is overwritten, so
rename it first.

### Option 2: Manual setup

1. Copy `.cursor/skills/planning-with-files/` to `.cursor/skills/planning-with-files/` in your project
2. Copy `.cursor/hooks.json` to `.cursor/hooks.json`, or merge it into an existing one (see below)
3. Copy the files in `.cursor/hooks/` to `.cursor/hooks/`

### Existing hooks.json

If your project already has `.cursor/hooks.json`, keep it and add the
planning-with-files registrations to it:

1. For each event in `planning-with-files/.cursor/hooks.json` (`sessionStart`,
   `preToolUse`, `postToolUse`, `stop`), append its entry to the array with the
   same name in your file. Create the array if your file has no such event.
2. Leave your existing entries, other events, and `"version": 1` as they are.

For example, a project that already registered an `afterFileEdit` hook and its
own `stop` hook ends up with:

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [
      { "command": ".cursor/hooks/format.sh" }
    ],
    "sessionStart": [
      { "command": ".cursor/hooks/session-start.sh", "timeout": 5 }
    ],
    "preToolUse": [
      { "command": ".cursor/hooks/pre-tool-use.sh", "matcher": "Write|Edit|Shell|Read", "timeout": 5 }
    ],
    "postToolUse": [
      { "command": ".cursor/hooks/post-tool-use.sh", "matcher": "Write|Edit", "timeout": 5 }
    ],
    "stop": [
      { "command": ".cursor/hooks/notify.sh" },
      { "command": ".cursor/hooks/stop.sh", "timeout": 10, "loop_limit": 3 }
    ]
  }
}
```

If the four entries are already there from an earlier install, there is nothing
to merge.

---

## Hooks Support

Cursor now supports hooks natively via `.cursor/hooks.json`. This skill includes four hooks that mirror the Claude Code experience:

| Hook | Purpose | Cursor Feature |
|------|---------|----------------|
| `sessionStart` | Injects the selected plan and recent progress | Adds plan context when a conversation starts |
| `preToolUse` | Allows tool operations using Cursor's permission schema | Keeps tools available |
| `postToolUse` | Reminds to update plan after file edits through additional context | Prevents forgetting updates |
| `stop` | Checks if all phases are complete | **Auto-continues** if incomplete |

The session start hooks return plan content in Cursor's `additional_context`
field. They run when a conversation is created; `beforeSubmitPrompt` cannot
inject context. Cursor Cloud Agents do not run `sessionStart`, so they do not
receive plan context through this hook. The native PowerShell hooks
(`hooks.windows.json`) resolve the
same selected plan directory as the planning scripts, through the shared
`.cursor/skills/planning-with-files/scripts/resolve-plan-dir.ps1`, which must
therefore be present next to the hooks. The rules are the ones every route
applies: an explicit `PLAN_ID` is binding and fails closed when it names no
plan; `PWF_PLAN_ROOT` pins the project and fails closed when it is not an
absolute local directory; with one named plan, `.active_plan` or the newest
plan selects it; with two or more named plans, `PLAN_ID` is required and
nothing is injected until it is set; a stale pointer falls through to the
root `task_plan.md` like `inject-plan.sh`, while a pointer that is a directory
or a link fails closed. Each refusal prints one notice naming the cause.

The bash hooks (`hooks.json`) resolve the same selected plan directory as the
PowerShell route, through `.cursor/hooks/resolve-plan-dir.sh` (a thin forwarder
onto the skill-owned `resolve-plan-dir.sh`). An explicit `PLAN_ID` selects
`.planning/<slug>/` even when a root `task_plan.md` exists; a missing or unsafe
`PLAN_ID` fails closed rather than injecting the root plan.

Two differences from the Claude Code and Codex routes are deliberate. Session
isolation (`.planning/sessions/` with `.attached` markers) is not implemented on
Cursor, which has no session identity to attach; an armed project injects the
selected plan as if isolation were off. The stop hook answers only in JSON, so
an explicit `PLAN_ID` or `PWF_PLAN_ROOT` that resolves to no plan lets the agent
stop silently where `check-complete.sh` would print a notice.

### How the Stop Hook Works

The stop hook is the most powerful feature. When the agent tries to stop:

1. It checks `task_plan.md` for phase completion status
2. If all phases are complete → allows the agent to stop
3. If phases are incomplete → sends a `followup_message` that auto-prompts the agent to keep working

This means the agent **cannot stop until all phases are done** (up to `loop_limit` of 3 retries).

### Hook Files

```
your-project/
├── .cursor/
│   ├── hooks.json                  ← Hook configuration (bash scripts)
│   ├── hooks.windows.json          ← Hook configuration (PowerShell scripts)
│   ├── hooks/
│   │   ├── session-start.sh        ← JSON session context response (bash)
│   │   ├── session-start.ps1       ← JSON session context response (PowerShell)
│   │   ├── user-prompt-submit.sh   ← Shared bash plan context renderer
│   │   ├── pre-tool-use.sh         ← Pre-tool-use script
│   │   ├── post-tool-use.sh        ← Post-tool-use script
│   │   ├── stop.sh                 ← Completion check script
│   │   ├── user-prompt-submit.ps1  ← PowerShell versions (named plans too)
│   │   ├── pre-tool-use.ps1
│   │   ├── post-tool-use.ps1
│   │   ├── stop.ps1
│   │   └── resolve-plan-context.ps1 ← Shared PowerShell plan selection
│   └── skills/
│       └── planning-with-files/
│           ├── SKILL.md
│           ├── examples.md
│           ├── reference.md
│           ├── scripts/            ← incl. resolve-plan-dir.ps1, used by the .ps1 hooks
│           └── templates/
├── task_plan.md                     ← Your planning files (created per task)
├── findings.md
├── progress.md
└── ...
```

---

## Windows Setup

The default `hooks.json` uses bash scripts (works on macOS, Linux, and Windows with Git Bash).

**If you need native PowerShell**, rename the config files:

```powershell
# Back up the default config
Rename-Item .cursor\hooks.json hooks.unix.json

# Use the PowerShell config
Rename-Item .cursor\hooks.windows.json hooks.json
```

The `.cursor/hooks.windows.json` file uses PowerShell to execute the `.ps1` hook scripts directly.

If you merged the entries into an existing `hooks.json`, do not rename the files,
because that would drop your own hooks. Replace the four planning-with-files
entries in your `hooks.json` with the matching entries from
`.cursor/hooks.windows.json` instead.

---

## What Each Hook Does

### SessionStart Hook

**Triggers:** When Cursor creates a new conversation

**What it does:** Returns the selected plan and recent progress in
`additional_context`, which Cursor adds to the initial conversation context.
The shell hook uses Python 3 to JSON-escape plan text; the PowerShell hook uses
`ConvertTo-Json`.

### PreToolUse Hook

**Triggers:** Before Write, Edit, Shell, or Read operations

**What it does:** Always returns `{"permission":"allow"}`. It does not inject plan context because `preToolUse` only accepts permission responses.

### PostToolUse Hook

**Triggers:** After Write or Edit operations

**What it does:** Returns a reminder to update `progress.md` and `task_plan.md` in `additional_context` when a plan exists.

**Claude Code equivalent:** `echo '[planning-with-files] File updated...'`

### Stop Hook

**Triggers:** When the agent tries to stop working

**What it does:**
1. Counts total phases (`### Phase` headers) in `task_plan.md`
2. Counts completed phases (supports both `**Status:** complete` and `[complete]` formats)
3. If incomplete, returns `followup_message` to auto-continue
4. Capped at 3 retries via `loop_limit` to prevent infinite loops

**Claude Code equivalent:** `scripts/check-complete.sh` — but Cursor's version is **more powerful** because it can auto-continue the agent instead of just reporting status.

---

## Skill Files

The `.cursor/skills/planning-with-files/SKILL.md` file contains all the planning guidelines:

- Core 3-file planning pattern
- Templates (task_plan.md, findings.md, progress.md)
- The 2-Action Rule
- The 3-Strike Error Protocol
- Read vs Write Decision Matrix

Cursor automatically loads skills from `.cursor/skills/` when you open a project.

---

## Templates

The templates in `.cursor/skills/planning-with-files/templates/` are used when starting a new task:

- `task_plan.md` - Phase tracking template
- `findings.md` - Research storage template
- `progress.md` - Session logging template

The agent copies these to your project root when starting a new planning session.

---

## Tips for Cursor Users

1. **Pin the planning files:** Keep task_plan.md open in a split view for easy reference.

2. **Trust the hooks:** The stop hook will prevent premature completion — you don't need to manually verify phase status.

3. **Use explicit prompts for complex tasks:**
   ```
   This is a complex task. Let's use the planning-with-files pattern.
   Start by creating task_plan.md with the goal and phases.
   ```

4. **Check hook logs:** If hooks aren't working, check Cursor's output panel for hook execution logs.

---

## Compatibility with Claude Code

Your planning files (task_plan.md, findings.md, progress.md) are fully compatible between Cursor and Claude Code. You can switch between them without any changes to your planning files.

---

## Need Help?

Open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
