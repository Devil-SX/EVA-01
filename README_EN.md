<h1 align="center">EVA-01</h1>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="version">
  <img src="https://img.shields.io/badge/Python-1890_lines-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Shell-248_lines-4EAA25?logo=gnubash&logoColor=white" alt="Shell">
  <img src="https://img.shields.io/badge/Markdown-24_lines-000000?logo=markdown&logoColor=white" alt="Markdown">
</p>

<p align="center">
  <a href="./README.md">中文</a> | <b><a href="./README_EN.md">English</a></b>
</p>

<p align="center">
  <img src="./eva.jpg" width="100%" alt="EVA-01">
</p>

A prototype testing platform for automating life. Converts requirement documents (specs) into structured PRDs, then lets Claude Code autonomously implement all user stories in a loop. The goal is to explore efficient human-AI collaboration in the age of rapidly advancing AI.

---

## Design Philosophy

### Compute Leverage & the Human Bottleneck

The more AI compute a person can orchestrate, the further their capabilities extend — this is **compute leverage**. But every AI run requires human decisions and review, and human attention is finite — this is the **human bottleneck**.

Three variables capture the dynamics:

- $v$ — average human interactions per hour of AI runtime
- $T$ — total daily AI runtime (compute leverage)
- $X = vT$ — total daily human-AI interactions, bounded by $X_{\text{threshold}}$

The objective is clear: **maximize $T$, minimize $X$, which means driving $v$ as low as possible.**

The value of $v$ determines two distinct work modes:

| Mode | Characteristic | Interactions/hr $v$ | Leverage $T$ ($X$=50) |
|------|---------------|:---:|:---:|
| Fatigued | Interactions hit the ceiling, human chained to AI | 10 | 5h |
| | | 5 | 10h |
| Comfortable | Interactions well below ceiling, human reaps AI benefits | 1 | 50h |
| | | 0.5 | 100h |

**Conclusion: $v$ must drop below 1 interaction per hour for sufficient leverage without burnout.**

### Three Paths to Lower $v$

1. **Smarter** — Reduce rework, fewer interactions needed
   - Upfront: Enforce structured workflows — every change must pass tests, AI self-verifies coverage
   - Feedback: Automatically capture runtime issues, continuously learn from external patterns

2. **Batching** — Concentrate interactions, reduce context-switching
   - Run tasks in bulk, review results together
   - Polish specs with AI assistance upfront to minimize mid-run surprises

3. **Simplify** — Make each interaction lighter
   - Auto-generate structured reports with clear entry points and action paths

### Radiation Effect

EVA-01 is an **experimental platform**, not a closed tool. The methodology refined here — spec-driven development, autonomous loops, observational feedback — is not confined to this repository. It can radiate to any project that needs AI automation. EVA-01 validates the workflow; other repositories reuse it.

---

## Quick Start

```bash
# Install
./install.sh

# Go to your project
cd your-project

# Write a spec, convert to PRD, then auto-implement
spec-to-prd my-feature.md
impl-prd
```

Uninstall: `./uninstall.sh`

After installation, the following commands are available in `~/.local/bin/`:

| Command | Description |
|---------|-------------|
| `spec-to-prd` | Convert spec to PRD JSON with automatic project analysis |
| `impl-prd` | Autonomous loop to implement PRD user stories |
| `observe-impl` | Analyze execution logs, generate reports, push GitHub Issues |

---

## Command Reference

### spec-to-prd

Converts spec markdown to PRD JSON. Automatically analyzes the project structure to generate a compatible PRD.

```bash
spec-to-prd <SPEC_FILE> [OPTIONS]
```

Automatically collected project context:

| Content | Description |
|---------|-------------|
| Directory tree | File tree (max 4 levels, excludes node_modules, etc.) |
| Config files | package.json, pyproject.toml, tsconfig.json, etc. |
| README | Project documentation |
| Git info | Current branch, commit count |

The generated PRD follows existing code style, references files to modify, considers the tech stack, and builds incrementally.

| Parameter | Short | Description |
|-----------|-------|-------------|
| `SPEC_FILE` | - | Spec markdown file path (required) |
| `--output FILE` | `-o` | Output path (default: `.prd/prds/<name>.json`) |
| `--project NAME` | `-p` | Project name (default: inferred from filename) |
| `--model MODEL` | `-m` | Claude model: opus/sonnet/haiku (default: sonnet) |
| `--timeout MINUTES` | - | Timeout in minutes (default: 15) |

```bash
spec-to-prd my-feature.md              # Basic usage
spec-to-prd my-feature.md -m opus      # Use opus model
spec-to-prd my-feature.md -o out.json  # Custom output path
```

---

### impl-prd

Autonomously implements PRD user stories in a loop.

```bash
impl-prd [OPTIONS]
```

| Parameter | Description |
|-----------|-------------|
| `--prd FILE` | PRD file path (default: latest in `.prd/prds/`) |
| `--max-iterations N` | Max iterations (default: 50) |
| `--timeout MINUTES` | Output timeout in minutes (default: 15) |
| `--model`, `-m` | Claude model (default: sonnet) |
| `--no-progress-threshold N` | Stall threshold (default: 3) |
| `--resume` | Resume from last state |
| `--status` | Show current state and exit |
| `--reset` | Reset state, start fresh |
| `--verbose` | Verbose output |
| `--no-observe` | Skip auto-running observe-impl on completion |

> impl-prd runs with `--dangerously-skip-permissions` by default for fully autonomous execution. It automatically calls `observe-impl` on completion.

```bash
impl-prd                          # Start implementing
impl-prd -m opus                  # Use opus model
impl-prd --resume                 # Resume previous session
impl-prd --status                 # Check current state
```

#### Exit Mechanisms

| Mechanism | Trigger | Default |
|-----------|---------|---------|
| Completion | All stories pass | - |
| Max iterations | Reached `--max-iterations` | 50 |
| Output timeout | No Claude output for N min | 15 min |
| Stall breaker | N consecutive loops with no story completed | 3 |
| Rate limit | Exceeded hourly call limit | 100/hr |
| User interrupt | Ctrl+C | - |

---

### observe-impl

Analyzes impl-prd execution logs, generates reports, and optionally pushes GitHub Issues.

```bash
observe-impl [OPTIONS]
```

Pipeline: Read session logs -> Claude analysis -> Save report -> Create Issues if needed

| Parameter | Short | Description |
|-----------|-------|-------------|
| `--session PATH` | `-s` | Session directory path |
| `--latest` | `-l` | Analyze most recent session |
| `--no-issue` | - | Don't create GitHub Issues |
| `--model MODEL` | `-m` | Claude model (default: haiku) |
| `--timeout MINUTES` | - | Timeout in minutes (default: 10) |
| `--verbose` | `-v` | Verbose output |

```bash
observe-impl --latest                # Analyze latest session
observe-impl --latest --no-issue     # Report only, no Issues
observe-impl --latest -m sonnet      # Deeper analysis with sonnet
```

---

## Directory Structure

Automatically created on first `spec-to-prd` run:

```
your-project/
└── .prd/
    ├── specs/          # Original spec markdowns
    ├── prds/           # Generated PRD JSONs
    ├── logs/           # Execution logs
    │   └── session_YYYYMMDD_HHMMSS/
    │       ├── config.json           # Runtime config snapshot
    │       ├── prd_snapshot.json     # PRD snapshot
    │       ├── args.json             # CLI arguments
    │       ├── session.log           # Main log
    │       ├── loop_001.log          # Per-loop output
    │       ├── summary.json          # Run summary
    │       └── observation_report.md # Observation report
    ├── config.json     # Project config
    └── state.json      # Run state (for resume)
```

### Configuration

```json
{
  "max_calls_per_hour": 100,
  "max_iterations": 50,
  "timeout_minutes": 15,
  "output_format": "stream",
  "allowed_tools": ["Write", "Read", "Edit", "Bash(git *)", "Bash(npm *)", "Bash(pytest)"],
  "session_expiry_hours": 24,
  "max_consecutive_failures": 3,
  "no_progress_threshold": 3
}
```

| Option | Description | Default |
|--------|-------------|---------|
| `max_calls_per_hour` | Max API calls per hour | 100 |
| `max_iterations` | Max loop iterations | 50 |
| `timeout_minutes` | Claude timeout (minutes) | 15 |
| `output_format` | Output format: stream / json | stream |
| `allowed_tools` | Allowed tool list | - |
| `session_expiry_hours` | Session expiry (hours) | 24 |
| `max_consecutive_failures` | Max consecutive failures | 3 |
| `no_progress_threshold` | No-progress threshold | 3 |

---

## Internal Protocol

### PRD JSON Format

```json
{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "source_spec": "specs/feature-name.md",
  "created_at": "2026-02-02T10:30:00",
  "updated_at": "2026-02-02T11:00:00",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Typecheck passes"],
      "priority": 1,
      "passes": false,
      "notes": "",
      "completed_at": null
    }
  ]
}
```

### Completion Signals

When Claude completes a story:

```
---RALPH_STATUS---
STATUS: COMPLETE
STORY_ID: US-001
STORY_PASSED: true
FILES_MODIFIED: [file1.py, file2.py]
EXIT_SIGNAL: false
---END_RALPH_STATUS---
```

When all stories are complete:

```
<promise>COMPLETE</promise>
```
