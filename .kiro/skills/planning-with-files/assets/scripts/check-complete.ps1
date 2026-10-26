# Report phase completion status for task_plan.md (stdout only, always exit 0).
# Default plan path: .kiro/plan/task_plan.md (relative to current directory).

param(
    [string]$PlanFile = ".kiro/plan/task_plan.md",
    [switch]$Validate
)

if ($Validate) {
    if (-not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) { Write-Output '[planning-with-files] Plan format invalid: task_plan.md was not found.'; exit 1 }
    $content = Get-Content -LiteralPath $PlanFile -Raw
}

# Explicit creation validation never mutates a plan or changes Stop behavior.
if ($Validate) {
    $phases = 0
    $statuses = 0
    $inPhase = $false
    $invalid = $false
    foreach ($line in ($content -split '\r?\n')) {
        if ($line -cmatch '^### Phase(?:[ \t]|$)') {
            if ($inPhase -and $statuses -ne 1) { $invalid = $true }
            $phases++
            $inPhase = $true
            $statuses = 0
        } elseif ($line -match '^#{1,3}[ \t]') {
            if ($inPhase -and $statuses -ne 1) { $invalid = $true }
            $inPhase = $false
        }
        if ($inPhase) {
            $statuses += ([regex]::Matches($line, '\*\*Status:\*\*[ \t]+(?:pending|in_progress|complete)(?:[^\p{L}\p{N}_]|$)')).Count
            $statuses += ([regex]::Matches($line, '\[(?:pending|in_progress|complete)\]')).Count
        }
    }
    if ($inPhase -and $statuses -ne 1) { $invalid = $true }
    if ($phases -eq 0 -or $invalid) {
        Write-Output '[planning-with-files] Plan format invalid: use ### Phase headings with exactly one native status per phase.'
        exit 1
    }
    Write-Output ('[planning-with-files] Plan format valid (' + $phases + ' phases).')
    exit 0
}

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path $PlanFile)) {
    Write-Host "[planning-with-files] No task plan at $PlanFile — run bootstrap or specify path."
    exit 0
}

$content = Get-Content $PlanFile -Raw
$TOTAL = ([regex]::Matches($content, "### Phase")).Count
$COMPLETE = ([regex]::Matches($content, "\*\*Status:\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*Status:\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*Status:\*\* pending")).Count

if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host "[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL)."
} else {
    Write-Host "[planning-with-files] In progress ($COMPLETE/$TOTAL phases complete)."
    if ($IN_PROGRESS -gt 0) {
        Write-Host "[planning-with-files] $IN_PROGRESS phase(s) in_progress."
    }
    if ($PENDING -gt 0) {
        Write-Host "[planning-with-files] $PENDING phase(s) pending."
    }
}
exit 0
