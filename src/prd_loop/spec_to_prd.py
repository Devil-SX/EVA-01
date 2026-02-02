#!/usr/bin/env python3
"""
spec-to-prd: Convert spec markdown files to PRD JSON format.

Usage:
    spec-to-prd <SPEC_FILE> [OPTIONS]

Options:
    SPEC_FILE           Path to spec markdown file
    --output FILE       Output PRD JSON file path
    --project NAME      Project name (default: inferred from filename)
    --model MODEL       Claude model: opus/sonnet/haiku (default: sonnet)
    --timeout MIN       Claude timeout in minutes (default: 15)
    -h, --help          Show this help message

Note: .prd directory will be automatically initialized if not exists.
      Claude will analyze the existing project structure to generate context-aware PRD.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when run directly
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import PrdDir, Config
from logger import PrdLogger
from claude_cli import ClaudeCLI
from prd_schema import PRD, UserStory


# Prompt template for spec-to-PRD conversion
# Claude will use its tools to explore the project before generating PRD
CONVERSION_PROMPT = '''You are a PRD generator for an existing codebase.

## Task
Convert the following spec into a PRD (Product Requirements Document) JSON format.

## IMPORTANT: Analyze Project First
Before generating the PRD, you MUST:
1. Use Glob/Read tools to explore the current project structure
2. Read key configuration files (package.json, pyproject.toml, tsconfig.json, Cargo.toml, etc.)
3. Understand the existing code patterns, conventions, and architecture
4. Identify files that will need to be modified or extended

## Input Spec:
{spec_content}

## Output Requirements
After analyzing the project, generate a valid JSON object with this exact structure:
```json
{{
  "project": "[Project name from spec or '{project_name}']",
  "branchName": "ralph/[feature-name-kebab-case]",
  "description": "[Brief description from spec]",
  "userStories": [
    {{
      "id": "US-001",
      "title": "[Short story title]",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Typecheck passes"],
      "priority": 1,
      "passes": false,
      "notes": "[Reference specific existing files to modify]"
    }}
  ]
}}
```

## Rules for PRD Generation:
1. **Analyze existing code patterns** - Follow the project's existing conventions, file organization, and coding style
2. **Consider dependencies** - Order stories by dependency (schema/types first, then core logic, then UI/API)
3. **Reference existing files** - In the notes field, mention specific files that will be modified or extended
4. **Incremental development** - Stories should build on existing codebase, not rewrite from scratch
5. **Small atomic stories** - Each story should be completable in one Claude session
6. **Quality criteria** - Always include appropriate quality checks (typecheck, lint, test) in acceptance criteria
7. **All stories start with passes: false**
8. **Priority numbers should be sequential (1, 2, 3, ...)**

## Context-Aware Guidelines:
- If Node.js project: Consider npm scripts, existing test framework, TypeScript config
- If Python project: Consider existing test framework, type hints, package structure
- If existing tests exist: Stories should include updating/adding tests
- Reference the actual file paths you discovered during exploration

## Final Output
After your analysis, output ONLY the JSON object (no markdown code blocks, no explanation).
The JSON must be valid and parseable.
'''


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert spec markdown files to PRD JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "spec_file",
        nargs="?",
        help="Path to spec markdown file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output PRD JSON file path"
    )
    parser.add_argument(
        "--project", "-p",
        help="Project name (default: inferred from filename)"
    )
    parser.add_argument(
        "--model", "-m",
        choices=["opus", "sonnet", "haiku"],
        default="sonnet",
        help="Claude model to use (default: sonnet)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout in minutes (default: 15)"
    )

    return parser.parse_args()


def infer_project_name(spec_path: Path) -> str:
    """Infer project name from spec file path."""
    name = spec_path.stem
    # Remove common prefixes
    for prefix in ["spec-", "spec_", "prd-", "prd_"]:
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    # Convert to title case
    return name.replace("-", " ").replace("_", " ").title()


def extract_json_from_output(output: str) -> dict:
    """Extract JSON object from Claude's output."""
    # Try to find JSON in the output
    # Look for content between { and }
    brace_count = 0
    json_start = -1
    json_end = -1

    for i, char in enumerate(output):
        if char == '{':
            if brace_count == 0:
                json_start = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and json_start != -1:
                json_end = i + 1
                break

    if json_start != -1 and json_end != -1:
        json_str = output[json_start:json_end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Try line by line
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    raise ValueError("Could not extract valid JSON from Claude's output")


def convert_spec_to_prd(
    spec_path: Path,
    project_name: str,
    prd_dir: PrdDir,
    logger: PrdLogger,
    config: Config,
    model: str = "sonnet"
) -> PRD:
    """
    Convert a spec file to PRD using Claude.
    Claude will explore the project structure itself using its tools.

    Args:
        spec_path: Path to spec markdown file
        project_name: Name of the project
        prd_dir: PrdDir instance
        logger: Logger instance
        config: Config instance
        model: Claude model to use

    Returns:
        PRD object
    """
    logger.info(f"Reading spec file: {spec_path}")

    # Read spec content
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Build prompt - Claude will explore the project itself
    prompt = CONVERSION_PROMPT.format(
        spec_content=spec_content,
        project_name=project_name
    )

    # Create log file for Claude's stream output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stream_log_path = prd_dir.logs_dir / f"spec_to_prd_{timestamp}_stream.log"
    stream_log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Calling Claude ({model}) to analyze project and generate PRD...")
    logger.info("Claude will explore project structure using its tools...")
    logger.info(f"Stream output saved to: {stream_log_path}")
    logger.log_separator()

    # Execute Claude with tools enabled for project exploration
    cli = ClaudeCLI(
        output_timeout_minutes=config.timeout_minutes,
        allowed_tools=["Read", "Glob", "Grep", "Bash(ls *)", "Bash(cat *)"],
        model=model
    )

    # Open log file for stream output
    with open(stream_log_path, "w", encoding="utf-8") as stream_log:
        stream_log.write(f"# spec-to-prd Stream Output\n")
        stream_log.write(f"# Started: {datetime.now().isoformat()}\n")
        stream_log.write(f"# Spec: {spec_path}\n")
        stream_log.write(f"# Model: {model}\n")
        stream_log.write("=" * 60 + "\n\n")

        result = cli.execute(prompt, log_file=stream_log)

        stream_log.write("\n" + "=" * 60 + "\n")
        stream_log.write(f"# Ended: {datetime.now().isoformat()}\n")
        stream_log.write(f"# Duration: {result.duration_seconds:.1f}s\n")
        stream_log.write(f"# Success: {result.success}\n")

    logger.log_separator()

    if not result.success:
        if result.timeout:
            raise RuntimeError(f"Claude timed out: {result.timeout_reason}")
        raise RuntimeError(f"Claude execution failed: {result.output}")

    logger.info(f"Claude execution completed in {result.duration_seconds:.1f}s")

    # Extract JSON from output
    try:
        prd_data = extract_json_from_output(result.output)
    except ValueError as e:
        logger.error(f"Failed to parse Claude output: {e}")
        logger.error(f"See full output in: {stream_log_path}")
        raise

    # Validate required fields
    required_fields = ["project", "userStories"]
    missing_fields = [f for f in required_fields if f not in prd_data]
    if missing_fields:
        logger.error(f"Missing required fields in PRD: {missing_fields}")
        logger.error(f"Parsed JSON keys: {list(prd_data.keys())}")
        logger.error(f"See full output in: {stream_log_path}")
        raise ValueError(f"Missing required fields: {missing_fields}")

    # Add source spec info
    prd_data["source_spec"] = str(spec_path)
    prd_data["created_at"] = datetime.now().isoformat()
    prd_data["updated_at"] = datetime.now().isoformat()

    # Create PRD object
    try:
        prd = PRD.from_dict(prd_data)
    except Exception as e:
        logger.error(f"Failed to create PRD object: {e}")
        logger.error(f"PRD data: {json.dumps(prd_data, indent=2, default=str)[:1000]}")
        raise

    logger.success(f"PRD created with {len(prd.userStories)} user stories")

    return prd


def main():
    """Main entry point."""
    args = parse_args()

    # Check for spec file
    if not args.spec_file:
        print("Error: SPEC_FILE is required")
        print("Usage: spec-to-prd <SPEC_FILE> [OPTIONS]")
        return 1

    spec_path = Path(args.spec_file)
    if not spec_path.exists():
        print(f"Error: Spec file not found: {spec_path}")
        return 1

    # Determine project root (from env var or current directory)
    # PRD_LOOP_WORKDIR is set by the wrapper script to preserve original cwd
    project_root = Path(os.environ.get("PRD_LOOP_WORKDIR", ".")).resolve()

    # Initialize .prd directory (auto-detect and create if needed)
    prd_dir = PrdDir(project_root)
    if not prd_dir.exists():
        prd_dir.init()
        print(f"Initialized .prd directory at {prd_dir.prd_dir}")

    # Get config
    config = prd_dir.get_config()

    # Override timeout from CLI
    if args.timeout:
        config.timeout_minutes = args.timeout

    # Setup logging
    log_path = prd_dir.get_log_path("spec_to_prd")
    logger = PrdLogger(log_file=log_path)
    logger.start_total_timer()

    logger.info(f"spec-to-prd starting")
    logger.info(f"Spec file: {spec_path}")
    logger.info(f"Project root: {project_root}")

    # Determine project name
    project_name = args.project or infer_project_name(spec_path)
    logger.info(f"Project name: {project_name}")

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_name = spec_path.stem.lower().replace(" ", "-") + ".json"
        output_path = prd_dir.prds_dir / output_name

    try:
        # Convert spec to PRD
        prd = convert_spec_to_prd(
            spec_path=spec_path,
            project_name=project_name,
            prd_dir=prd_dir,
            logger=logger,
            config=config,
            model=args.model
        )

        # Save PRD
        prd.save(output_path)
        logger.success(f"PRD saved to: {output_path}")

        # Copy spec to specs directory
        spec_dest = prd_dir.specs_dir / spec_path.name
        if not spec_dest.exists():
            import shutil
            shutil.copy(spec_path, spec_dest)
            logger.info(f"Spec copied to: {spec_dest}")

        # Print summary
        runtime = logger.format_duration(logger.get_total_runtime())
        logger.log_separator()
        logger.stats(f"Conversion complete in {runtime}")
        logger.info(f"Project: {prd.project}")
        logger.info(f"Branch: {prd.branchName}")
        logger.info(f"Stories: {len(prd.userStories)}")
        logger.info("")
        logger.info("User Stories:")
        for story in prd.userStories:
            logger.info(f"  {story.id}: {story.title}")
            if story.notes:
                logger.info(f"         Notes: {story.notes}")
        logger.info("")
        logger.info("Next steps:")
        logger.info(f"  impl-prd --prd {output_path}")

        return 0

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
