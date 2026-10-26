# skill-lens eval

A repeatable with-and-without check for `planning-with-files`, run by
[skill-lens](https://github.com/EmadMokhtar/skill-evaluator). Two cases, measured on two
agents: Claude Code (a CLI product) and PydanticAI (an agent SDK).

## Run it

```bash
uv tool install "skill-lens[pydantic-ai]==0.25.0"
skill-lens run skills/planning-with-files --baseline none --repeat 5 \
  --runner claude-code --runner pydantic-ai
```

- `--baseline none` runs every case a second time with no skill loaded; `--repeat 5` runs each
  arm five times.
- `claude-code` runs with a temporary home directory (see
  [How a run is isolated](#how-a-run-is-isolated)), so the login saved in your own home
  directory or keychain does not reach it. Export `CLAUDE_CODE_OAUTH_TOKEN` (create one with
  `claude setup-token`) or `ANTHROPIC_API_KEY`. `pydantic-ai` and the judge use
  `OPENAI_API_KEY`.
- With only Claude Code, set `judge = "claude-code"` in `skill-lens.toml` and run
  `--runner claude-code` alone. Without a supported sandbox backend, also pass
  `--no-allow-scripts` and `--product-sandbox auto`. The first disables skill-lens's framework
  script tool; Claude Code still runs its own shell commands. The second runs Claude Code with
  a temporary home directory but no sandbox, and the report says so.
- Add `--json-output report.json` to keep every hook the skill ran (see
  [What the hooks did](#what-the-hooks-did)).
- The exit code is the CI contract: `0` the gate passed, `1` it failed, `2` a mistake in the
  eval files.

## What the cases check

### `creates-the-three-files`

`creates-the-three-files` is eval 1 (todo-cli) from [evals.md](evals.md), with the same seven
assertions plus two on the contents:

| Check | How |
| --- | --- |
| `task_plan.md`, `findings.md`, `progress.md` exist | file assertions |
| `## Goal`, `### Phase`, `**Status:**`, `## Errors Encountered` in `task_plan.md` | regex / contains |
| `findings.md` records something: a bullet with text, or a table row | regex |
| `progress.md` records a concrete action, not only template fields | LLM judge |

Every check accepts the files in either place the skill uses: the project root (legacy layout)
or a named plan directory, `.planning/<date>-<slug>/`. Each filename must have exactly one
match. skill-lens checks each filename on its own, so files split across different plan
directories can still pass. This case does not verify that all three files share one directory.

### `resumes-from-its-own-plan`

This case tests the skill's main claim: a fresh session resumes from the files an earlier
session wrote. It runs as two sessions against one workspace. Each session is a new agent
process with no conversation history; only the files carry over.

1. "Build a Python CLI todo tool with persistence, in three phases. Phase 1: design the
   storage format and the commands. Phase 2: implement add and list. Phase 3: implement done
   and delete. Do phase 1 only, then stop."
2. "Continue the todo tool from where the last session stopped. Do the next phase only, then
   stop."

Session 2 is not told which phase is next, so it has to find out from the files. Under Claude
Code the skill's `UserPromptSubmit` hook is also meant to put the plan into the session's
context; see [What the hooks did](#what-the-hooks-did) for whether it did. Every check runs
after session 2 and looks for the work session 2 was asked to do. The checks cannot tell
which session did that work (see [Known limits](#known-limits)):

| Check | How |
| --- | --- |
| `task_plan.md` marks Phase 2 `complete` | regex on the `### Phase 2` section |
| `task_plan.md` does not mark Phase 3 `complete` | regex on the `### Phase 3` section |
| `progress.md` records concrete work on `add` and `list` | LLM judge |
| `progress.md` has an entry for phase 1 before its entries for the `add` and `list` work | LLM judge |

Both files must have exactly one match, so a session 2 that starts a second plan instead of
continuing the first one fails.

## Results

Contributor-reported measurements using skill-lens 0.25.0, planning-with-files v3.25.1
(`99402ce`), Claude Code 2.1.289, with the configuration in this repository: both sandboxes
required, `sandbox-exec` on macOS. Judge: `openai:gpt-6-luna`. Five runs per arm; tokens,
cost and latency are means per run. Both cases ran in one run, which cost $5.87 in all.

These measurements predate the maintainer correction that binds each resume
phase check to its first status line. The corrected assertions were verified
offline; the model evaluations and reported costs below were not rerun.

### `creates-the-three-files`

| Runner and model | With skill | Without skill | Tokens | Cost | Latency |
| --- | --- | --- | --- | --- | --- |
| `claude-code`, `claude-sonnet-4-6` | 2/5 | 0/5 | 340k (111k without) | $0.31 ($0.13) | 61 s (30 s) |
| `pydantic-ai`, `openai:gpt-6-luna` | 5/5 | 0/5 | 275k (7k without) | $0.016 ($0.002) | 187 s (18 s) |

Total: $2.28 for the 20 runs, plus $0.004 for the judge.

Claude Code's pass count changes from run to run: two earlier runs of this case, one on
skill-lens 0.23.0 and planning-with-files v3.25.0 and one on 0.25.0, both gave 3/5.
PydanticAI gave 5/5 every time.

Observations from these runs:

- Without the skill, neither agent wrote a planning file in any of the 10 runs.
- **Claude Code sometimes creates the files and leaves them empty.** All three failed runs left
  `findings.md` as the empty template that `init-session.sh` writes. The earlier runs showed
  the same pattern, and the contributor also observed it with Sonnet under PydanticAI. This
  small sample does not isolate model, runner or environment effects. `gpt-6-luna` filled
  every file in the five runs with the skill.
- **Both layouts happen.** PydanticAI used the project root in 3 of 5 runs and a named plan
  directory in 2; Claude Code always used a named directory.
- **The hooks did nothing visible.** Each Claude Code run with the skill ran 13 to 19 hooks.
  All exited 0, and none printed anything; see [What the hooks did](#what-the-hooks-did).

### `resumes-from-its-own-plan`

Tokens, cost and latency add up both sessions of a run.

| Runner and model | With skill | Without skill | Tokens | Cost | Latency |
| --- | --- | --- | --- | --- | --- |
| `claude-code`, `claude-sonnet-4-6` | 4/5 | 0/5 | 643k (146k without) | $0.54 ($0.17) | 90 s (32 s) |
| `pydantic-ai`, `openai:gpt-6-luna` | 0/5 | 0/5 | 268k (15k without) | $0.010 ($0.003) | 175 s (39 s) |

Total: $3.57 for the 20 runs, plus $0.005 for the judge.

Observations from these runs:

- Without the skill, no run wrote a plan, so session 2 had none to continue and every check
  failed.
- **Claude Code resumed in all five runs; four passed.** Session 2 found the one named plan,
  marked Phase 2 complete, left Phase 3 open, and kept session 1's entries in the log. The
  failed run did the same, but wrote its phases as `## Phase N` headings instead of the
  template's `### Phase N`, so neither regex found the sections.
- **PydanticAI left Phase 3 open in every run, but no run passed.** In all five runs the final
  `progress.md` had no entry for phase 1. The report does not record tool calls, so it does
  not show how session 1's entries were lost; one possible cause is that skill-lens's
  `write_file` tool replaces a whole file. In 3 runs session 2 also left Phase 2
  `in_progress`, because it could not run the tests it wrote: a framework runner has no
  shell, and `run_script` runs only the skill's own scripts.
- **The hooks did nothing visible here either.** Each Claude Code run with the skill ran 25 to
  42 hooks across its two sessions, with `UserPromptSubmit` and `Stop` once per session. All
  exited 0, and none printed anything.

## How a run is isolated

- Every run gets its own new temporary directory, and the two arms never share one.
- Claude Code starts with `--setting-sources project --strict-mcp-config
  --no-session-persistence`, so the runner's own settings, hooks and MCP servers stay out and
  no session is saved. The skill's frontmatter hooks do run.
- Claude Code runs with permission prompts off, inside skill-lens's product sandbox
  (`product_sandbox = "required"`): `sandbox-exec` on macOS, `bwrap` on Linux. Each case gets
  a temporary home directory, deleted when the case ends, and an environment built from an
  allowlist. Claude Code cannot change files outside its working directory and its own
  temporary directories, and cannot read other skill-lens temporary directories, such as the
  other arm's workspace.
- **It can still read the rest of your files.** The sandbox allows reads anywhere you can
  read, network access (Claude Code must reach its provider), and requests to system services
  that act outside it. Treat it as a guard against accidents, not against a hostile skill.
- The skill's hooks resolve `$HOME` to the temporary home. Their fallback to
  `$HOME/.claude/skills/planning-with-files/` finds nothing there, so a personal install no
  longer affects a run, and the `~/.cache/pwf-pretool` cache is deleted with the case.
- Without a working backend the run stops before it spends anything. `--product-sandbox auto`
  runs it anyway with only the temporary home directory and the allowlist. That keeps personal
  installs out, but it is not a sandbox: Claude Code can then write anywhere you can. The
  report's `claude-code` line says which of the two applied.
- PydanticAI runs the skill's scripts through skill-lens's own sandbox (`sandbox-exec` on
  macOS, `bwrap` on Linux). The configuration requires a working sandbox backend for script
  execution and refuses to fall back to unsandboxed scripts. This framework path needs a
  supported backend; it is unavailable on native Windows. With only Claude Code available,
  use the CLI-only runner and judge configuration above with `--no-allow-scripts` and
  `--product-sandbox auto`. Sandbox
  preflight otherwise runs even for a CLI-only run.

## What the hooks did

The skill's hooks (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `PreCompact`) are
half of how it works, and only Claude Code runs them. Under `claude-code`, skill-lens records
every hook that ran, in order: its name (`PreToolUse:Write`), its outcome, its exit code, and
its stdout and stderr.

- A case that does not pass lists the hooks that did not succeed under `failed hooks:`.
- `--json-output` keeps every hook, successful ones included, under `hooks`.
- Hooks are reported, never checked: a failed hook does not fail a case by itself. Exit code
  `2` is how a hook blocks on purpose, and Claude Code reports it as `error` too.
- Every hook command in `SKILL.md` ends in `exit 0`, including when it cannot find its script.
  So `success` shows that a hook ran, not that it did its work; its stdout shows what it added
  to the session.
- PydanticAI does not run the hooks, so a PydanticAI result says nothing about them.

In the runs in [Results](#results), every hook exited 0 and none printed anything. Run by hand
in a copy of a kept workspace, with `CLAUDE_SKILL_DIR` set, the `UserPromptSubmit` hook prints
the plan. Each hook command looks for its script under `${CLAUDE_SKILL_DIR}`, then under
`$HOME/.claude/`, and exits 0 silently when it finds neither. The most likely reading is that
Claude Code 2.1.289 does not set `CLAUDE_SKILL_DIR` for a skill's hooks, and the temporary
home has no personal install to fall back to. That reading has not been confirmed. If it is
right, the Claude Code results measure the skill without the context its hooks add.

## Budgets

- A `budget:` block is checked after a run ends. Only its `max_tokens` also stops a run while it
  spends, and only under PydanticAI (see the last bullet).
- Claude Code stops a run itself at `--max-budget-usd` (`1.00` in `skill-lens.toml`); such a run
  is reported as errored.
- The Claude Code runner's timeout (`timeout_seconds`, 600 here) also stops its run. This
  setting does not impose an overall timeout on the PydanticAI runner.
- `max_spend_usd` (`10.00` in `skill-lens.toml`, or `--max-spend`) caps the whole run. Once
  the recorded spend of every run and every judge call reaches it, no new case starts. Cases
  already running finish, the rest are reported as not run, and the gate fails.
- A PydanticAI run stops at its own default of 50 model requests. A `budget: max_tokens` in a
  case would stop it earlier, while it spends, and fail that case. Neither case sets one, so
  `creates-the-three-files` keeps the same checks as eval 1.

## Known limits

- `resumes-from-its-own-plan` checks the planning files, not the code: it does not test that
  `add` and `list` work. A first session that ignored "then stop" and finished phase 2 itself,
  followed by a second session that changed nothing, could still pass every check.
- Under PydanticAI the agent has no shell, so it cannot run the code it writes. A session that
  wants to test a phase before it marks the phase complete leaves it `in_progress`.
- The two regexes look for `### Phase N` headings, as in the template. A plan written with
  another heading level fails them even when it resumed correctly, as one Claude Code run did.
- Hooks are reported, not checked. No case asserts that a hook fired.
- The product sandbox does not stop reads outside the working directory or network access.
- Running the eval costs money (about $5.87 for the 40 runs above) and needs
  `CLAUDE_CODE_OAUTH_TOKEN` (or `ANTHROPIC_API_KEY`) and `OPENAI_API_KEY`.
