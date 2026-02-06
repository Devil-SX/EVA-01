#!/usr/bin/env python3
"""
observe-impl: Analyze impl-prd session logs and report issues.

Usage:
    observe-impl --session <SESSION_DIR>
    observe-impl --latest           # Analyze the most recent session
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports when run directly
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from claude_cli import ClaudeCLI, check_claude_installed
from config import find_project_root


# Prompt template for analyzing session logs
OBSERVE_PROMPT = '''You are a log analyzer for impl-prd execution sessions.

## Task
Analyze the implementation session logs and generate a structured report with GitHub issues.

## Session Directory
{session_dir}

## Project Root
{project_root}

## Create GitHub Issues
{create_issue}

## Analysis Steps

### Step 0: Framework Detection and GitHub Info

**Step 0.1: Detect prd-loop framework**
The project uses prd-loop framework: {uses_prd}

**Step 0.2: Get GitHub user info**
Run these commands to get GitHub information:
```bash
gh api user --jq ".login"
gh repo list --json name,url --limit 100
```

**Step 0.3: Detect other frameworks**
1. Read project structure and key files (package.json, pyproject.toml, etc.)
2. Check if project imports/uses any framework from user's repos
3. Record detected frameworks for issue routing in Step 3

### Step 1: Read all relevant files
1. Read `summary.json` for overall session statistics
2. Read `session.log` for main execution flow
3. Read `prd_snapshot.json` for task description
4. Read `loop_*.log` files for detailed Claude interactions

### Step 2: Write the observation report
Write a markdown report to: {session_dir}/observation_report.md

**IMPORTANT**: The report MUST follow this EXACT structure.
Note: The report is stored locally and may contain original project information for debugging.
The GitHub issues will be sanitized according to the Privacy Sanitization Guidelines below.

```markdown
# Implementation Session Observation Report

## 1. Summary

| Item | Value |
|------|-------|
| Session ID | `YYYYMMDD_HHMMSS` |
| Duration | Xh Ym Zs |
| Stories Progress | X/Y completed (Z this session) |
| Loop Results | A successful, B failed |
| Exit Reason | complete/circuit_breaker/user_interrupt/etc |
| GitHub Issues | #N, #M (or "None" if no issues created) |

## 2. Task Description

Based on the PRD (from prd_snapshot.json):
- **Project**: [project name]
- **Description**: [project description]
- **User Stories**:
  - US-001: [title] - [status: passed/pending]
  - US-002: [title] - [status: passed/pending]
  - ...

## 3. Session Analysis

### 3.1 Timeline Overview
Brief chronological overview of what happened during the session.

### 3.2 Loop-by-Loop Analysis

| Loop | Story | Duration | Result | Notes |
|------|-------|----------|--------|-------|
| #1 | US-001 | 5m 30s | Passed | First attempt success |
| #2 | US-002 | 8m 15s | Failed | Type check errors |
| ... | ... | ... | ... | ... |

### 3.3 Performance Analysis
- **Longest Loop**: Loop #X (Ym Zs) - [reason why it took long]
- **Fastest Loop**: Loop #Y (Zm Ws)
- **Average Loop Duration**: Xm Ys
- **Total API Time**: Xh Ym

## 4. Task-Specific Issues

Issues related to the specific implementation task (code problems, test failures, etc.)

### Issue 4.1: [Short Title]
- **Loop(s)**: #N, #M
- **Story**: US-XXX
- **Problem**: [Description of what went wrong]
- **Root Cause**: [Analysis of why it happened]
- **Suggestion**: [How to fix or improve]

### Issue 4.2: ...

(If no task-specific issues: "No task-specific issues found.")

## 5. Workflow Issues

Issues related to the prd-loop workflow itself (not the specific task)

### Issue 5.1: [Short Title]
- **Type**: timeout/circuit_breaker/rate_limit/tool_error/etc
- **Loop(s)**: #N
- **Problem**: [Description]
- **Impact**: [How it affected the session]
- **Suggestion**: [How to improve the workflow]

Examples of workflow issues:
- Timeout without proper recovery
- Circuit breaker triggered incorrectly
- Rate limiting issues
- Tool permission problems
- PRD parsing errors
- State management bugs

(If no workflow issues: "No workflow issues found.")

## 6. GitHub Issues Created

List of GitHub issues created for this session:
- Issue #N: [Title] - [Category: task/workflow]
- Issue #M: [Title] - [Category: task/workflow]

(If no issues created: "No GitHub issues created - session completed successfully.")
```

### Privacy Sanitization Guidelines

When creating GitHub issues, you MUST sanitize content to avoid leaking user project information to the public repository.

**MUST Sanitize (Replace with generic terms):**
| Original Content | Sanitized Version |
|-----------------|-------------------|
| Project name (e.g., "VerilogVis") | "Target Project" |
| Full paths `/home/user/proj/src/auth.py` | `<project>/src/<module>.py` |
| Specific User Story descriptions | Generic descriptions like "authentication feature", "data processing module" |
| Business code snippets | Pseudocode or structure-only (e.g., "function that processes user input") |
| Sensitive error messages with paths/user data | Remove paths and user-specific data |
| File names that reveal project purpose | `<module>.py`, `<config>.json` |
| Variable/function names from user code | Generic names like `userFunction`, `dataHandler` |

**MUST Preserve (Keep as-is):**
- Session ID (e.g., `20260202_222621`) - needed to correlate with local logs
- Loop numbers (e.g., `Loop #5`)
- Error types (`TypeError`, `TimeoutError`, `FileNotFoundError`, etc.)
- Generic problem pattern descriptions
- prd-loop tool/workflow errors (these are from this project, not user's)
- Fix suggestions (in generic terms)

**Sanitization Example:**

Original:
> Session 20260202_222621 in VerilogVis project failed at Loop #5.
> The story "Implement WaveDrom timing diagram parser for /home/sdu/pure_auto/verilog_vis/src/timing/" encountered TypeError.
> Error in parse_waveform() at line 45.

Sanitized:
> Session 20260202_222621 failed at Loop #5.
> A story implementing a "diagram parser feature" encountered TypeError in `<project>/src/<module>/`.
> Error in a parsing function.

### Step 3: Route and Resolve Issues

#### Step 3.1: Prepare Issues Directory
```bash
mkdir -p {session_dir}/issues
```

#### Step 3.2: Determine Issue Routing

**Routing Rules:**
| Issue Type | Route To | Condition |
|-----------|----------|-----------|
| Workflow Issue | `Devil-SX/prd-loop` | Issues about prd-loop workflow itself |
| User-Framework Issue | User's framework repo | Issues about a framework from user's repos (detected in Step 0) |
| Task Issue | Target project repo | Project-specific implementation issues |

**For target project routing, ensure GitHub remote exists:**
```bash
cd {project_root}
git remote get-url origin 2>/dev/null || (git init 2>/dev/null; gh repo create $(basename {project_root}) --private --source=. --push 2>/dev/null) || true
```

#### Step 3.3: Check for CLAUDE.md Resolvable Patterns

Analyze loop logs to find patterns that can be documented as solutions:

**Resolvable patterns (update CLAUDE.md):**
1. **Repeated failure then success** - Operation failed multiple times, then succeeded. Document what made it work.
2. **Pattern recognition** - Same error type keeps appearing with a clear workaround.
3. **Configuration/environment issues** - Project-specific settings that need to be remembered.

**NOT resolvable (keep issue open):**
- No clear solution found
- One-time random errors
- Requires code changes to fix (actual bugs)

**If resolvable pattern found:**
1. Generate solution summary for CLAUDE.md
2. Append to `{project_root}/CLAUDE.md` (create if not exists)
3. Mark issue with "auto-resolved" label
4. Create GitHub issue, then close it with comment: "Auto-resolved: Solution documented in CLAUDE.md"

#### Step 3.4: Save Issues to Local Files

For EACH issue, apply Privacy Sanitization Guidelines and save to:
`{session_dir}/issues/issue_NNN_ROUTE.md`
- NNN: Three-digit sequence (001, 002, ...)
- ROUTE: `prd-loop`, `framework-{{name}}`, or `project`

**File format:**
```markdown
# impl-prd ROUTE issue: [Sanitized Title]

**Labels:** impl-prd-TYPE, [auto-resolved if applicable]
**Route:** REPO_NAME

## Body

Session ID: YYYYMMDD_HHMMSS
Related loops: #N, #M

### Problem
[Sanitized problem description]

### Root Cause
[Analysis - sanitized if contains project-specific details]

### Suggested Fix
[Generic suggestions]
```

**IMPORTANT:** Always save issue files, even when `--no-issue` is used.

#### Step 3.5: Create GitHub Issues (if applicable)

If create_issue is "yes":

**Create labels if needed:**
```bash
gh label create -R REPO "impl-prd-task" --color "d73a4a" --description "Task-specific issues" 2>/dev/null || true
gh label create -R REPO "impl-prd-workflow" --color "0075ca" --description "Workflow issues" 2>/dev/null || true
gh label create -R REPO "auto-resolved" --color "0e8a16" --description "Auto-resolved with CLAUDE.md update" 2>/dev/null || true
```

**Create issues to their routed repositories:**
```bash
gh issue create -R ROUTED_REPO \
  --title "impl-prd TYPE issue: [brief title]" \
  --label "impl-prd-TYPE" \
  --body "..."
```

**For auto-resolved issues, close immediately:**
```bash
gh issue close -R ROUTED_REPO ISSUE_NUMBER --comment "Auto-resolved: Solution documented in project CLAUDE.md"
```

**Do NOT create issues if:**
- Session completed successfully with no problems
- Only minor warnings encountered
- create_issue is "no"

#### Step 3.6: Update Report

After creating issues, update Section 6 of the report with issue numbers and their routed repositories.

## Important Notes
- Be thorough but concise in your analysis
- Focus on actionable insights
- If a loop file is very long, focus on error sections and key decision points
- Clearly distinguish between task issues (code/test problems) and workflow issues (prd-loop problems)
- Each issue should be atomic and actionable
'''


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze impl-prd session logs and report issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--session", "-s",
        type=str,
        help="Path to session directory",
    )
    parser.add_argument(
        "--latest", "-l",
        action="store_true",
        help="Analyze the most recent session",
    )
    parser.add_argument(
        "--no-issue",
        action="store_true",
        help="Don't create GitHub issue",
    )
    parser.add_argument(
        "--model", "-m",
        choices=["opus", "sonnet", "haiku"],
        default="haiku",
        help="Claude model to use (default: haiku)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Claude timeout in minutes (default: 10)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    return parser.parse_args()


def find_latest_session(logs_dir: Path) -> Path | None:
    """Find the most recent session directory (session_YYYYMMDD_HHMMSS format)."""
    if not logs_dir.exists():
        return None

    sessions = sorted(logs_dir.glob("session_*"), reverse=True)
    return sessions[0] if sessions else None


def cleanup_previous_observation(session_dir: Path) -> None:
    """Remove previous observation files if they exist."""
    files_to_remove = [
        session_dir / "observation.log",
        session_dir / "observation_report.md",
        # Also clean up old naming convention
        session_dir / "observe.log",
    ]

    for file_path in files_to_remove:
        if file_path.exists():
            file_path.unlink()
            print(f"Removed previous: {file_path.name}")


def run_observe(session_dir: Path, create_issue: bool = True, model: str = "haiku", timeout_minutes: int = 10) -> bool:
    """
    Run observation analysis on a session directory.

    Args:
        session_dir: Path to the session directory
        create_issue: Whether to create GitHub issue for issues found
        model: Claude model to use
        timeout_minutes: Timeout for Claude execution

    Returns:
        True if observation completed successfully, False otherwise
    """
    print(f"\n{'=' * 60}")
    print(f"observe-impl: Analyzing session {session_dir.name}")
    print(f"{'=' * 60}")

    # Clean up previous observation files
    cleanup_previous_observation(session_dir)

    # Check for required files
    summary_file = session_dir / "summary.json"
    if not summary_file.exists():
        print(f"Warning: summary.json not found in {session_dir}")
        print("Session may be incomplete or still running")

    # Detect prd-loop framework
    project_root = session_dir.parent.parent.parent  # .prd/logs/session_xxx -> project_root
    uses_prd = (project_root / ".prd").exists()

    # Build prompt
    prompt = OBSERVE_PROMPT.format(
        session_dir=session_dir,
        project_root=project_root,
        uses_prd="yes" if uses_prd else "no",
        create_issue="yes" if create_issue else "no",
    )

    # Configure allowed tools
    allowed_tools = [
        "Read",
        "Glob",
        "Write",
        # GitHub CLI
        "Bash(gh api *)",           # Get user info
        "Bash(gh repo list *)",     # List user repos
        "Bash(gh repo create *)",   # Create private repo for target project
        "Bash(gh issue create *)",  # Create issues
        "Bash(gh issue close *)",   # Close auto-resolved issues
        "Bash(gh label create *)",  # Create labels
        # Git commands
        "Bash(git init *)",         # Initialize git
        "Bash(git remote *)",       # Check/add remote
        # Filesystem
        "Bash(mkdir *)",            # Create directories
    ]

    # Execute Claude
    cli = ClaudeCLI(
        output_timeout_minutes=timeout_minutes,
        allowed_tools=allowed_tools,
        model=model,
        dangerously_skip_permissions=True,
    )

    print(f"\nAnalyzing with Claude ({model})...\n")

    # Open log file for stream output
    observation_log_path = session_dir / "observation.log"
    with open(observation_log_path, "w", encoding="utf-8") as log_file:
        result = cli.execute(prompt, log_file=log_file)

    if result.timeout:
        print(f"\nError: Analysis timed out ({result.timeout_reason})")
        return False

    if not result.success:
        print(f"\nError: Analysis failed (exit code {result.exit_code})")
        return False

    # Check if report was created
    report_file = session_dir / "observation_report.md"
    if report_file.exists():
        print(f"\n{'=' * 60}")
        print(f"Observation complete!")
        print(f"Report saved to: {report_file}")
        print(f"Log saved to: {observation_log_path}")
        print(f"{'=' * 60}")
    else:
        print(f"\nWarning: Report file not created at {report_file}")

    return True


def main():
    args = parse_args()

    # Determine session directory
    session_dir = None

    if args.session:
        session_dir = Path(args.session)
        if not session_dir.is_absolute():
            # Try relative to current directory first
            if not session_dir.exists():
                # Try relative to .prd/logs
                project_root = find_project_root()
                if project_root:
                    session_dir = project_root / ".prd" / "logs" / args.session

    elif args.latest:
        # Find latest session from .prd/logs
        project_root = find_project_root()
        if project_root:
            logs_dir = project_root / ".prd" / "logs"
            session_dir = find_latest_session(logs_dir)
            if not session_dir:
                print("Error: No session directories found in .prd/logs/")
                return 1
        else:
            print("Error: .prd directory not found")
            print("Run from a project directory with .prd/logs/")
            return 1
    else:
        print("Error: --session or --latest required")
        print("Usage:")
        print("  observe-impl --session <SESSION_DIR>")
        print("  observe-impl --latest")
        return 1

    # Validate session directory
    if not session_dir or not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return 1

    if not session_dir.is_dir():
        print(f"Error: Not a directory: {session_dir}")
        return 1

    # Check Claude CLI
    if not check_claude_installed():
        print("Error: Claude Code CLI not found")
        print("Install with: npm install -g @anthropic-ai/claude-code")
        return 1

    # Run observation
    success = run_observe(
        session_dir=session_dir,
        create_issue=not args.no_issue,
        model=args.model,
        timeout_minutes=args.timeout,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
