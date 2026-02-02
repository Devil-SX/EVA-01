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
      The tool analyzes existing project structure to generate context-aware PRD.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set

# Add parent directory to path for imports when run directly
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import PrdDir, Config
from logger import PrdLogger
from claude_cli import ClaudeCLI
from prd_schema import PRD, UserStory


# Prompt template for spec-to-PRD conversion with project context
CONVERSION_PROMPT = '''You are a PRD converter for an existing codebase. Analyze the project structure and spec document to generate a context-aware PRD.

## Existing Project Structure:
{project_structure}

## Key Files Content:
{key_files_content}

## Input Spec:
{spec_content}

## Output Requirements:
Generate a valid JSON object with this exact structure:
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
      "notes": ""
    }}
  ]
}}

## Rules:
1. **Analyze existing code patterns** - Follow the project's existing conventions, file organization, and coding style
2. **Consider dependencies** - Order stories by dependency (schema/types first, then core logic, then UI/API)
3. **Reference existing files** - When a story modifies existing files, mention them in notes
4. **Incremental development** - Stories should build on existing codebase, not rewrite from scratch
5. **Small atomic stories** - Each story should be completable in one session
6. **Quality criteria** - Always include "Typecheck passes" in acceptance criteria
7. **UI stories** - Include "Verify in browser" as criterion for UI changes
8. **All stories start with passes: false**
9. **Priority numbers should be sequential (1, 2, 3, ...)**

## Context Awareness:
- If the project has package.json, consider npm/node conventions
- If the project has pyproject.toml or setup.py, consider Python conventions
- If the project has existing tests, stories should include test updates
- If the project uses TypeScript, ensure type safety in criteria
- Reference specific existing files that will be modified or extended

Output ONLY the JSON object, no other text.
'''


# Files to ignore when scanning project structure
IGNORE_PATTERNS = {
    # Directories
    '.git', '.prd', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', '.nuxt', 'target', '.idea', '.vscode',
    'coverage', '.pytest_cache', '.mypy_cache', 'egg-info',
    # Files
    '.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo', '*.egg', '*.whl',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'uv.lock',
    'poetry.lock', 'Pipfile.lock',
}

# Key files to read content from (config/setup files)
KEY_FILE_PATTERNS = {
    'package.json', 'pyproject.toml', 'setup.py', 'setup.cfg',
    'tsconfig.json', 'Cargo.toml', 'go.mod', 'Makefile',
    'README.md', 'readme.md', 'README.rst',
}

# Maximum depth for directory tree
MAX_TREE_DEPTH = 4

# Maximum file content length to include
MAX_FILE_CONTENT_LENGTH = 2000


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


def should_ignore(path: Path, base_path: Path) -> bool:
    """Check if a path should be ignored."""
    rel_path = path.relative_to(base_path)

    for part in rel_path.parts:
        # Check directory/file name patterns
        if part in IGNORE_PATTERNS:
            return True
        # Check glob patterns
        for pattern in IGNORE_PATTERNS:
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(part, pattern):
                    return True
    return False


def get_project_tree(base_path: Path, max_depth: int = MAX_TREE_DEPTH) -> str:
    """
    Generate a tree view of the project structure.

    Args:
        base_path: Root directory to scan
        max_depth: Maximum depth to traverse

    Returns:
        String representation of directory tree
    """
    lines = []

    def add_tree(path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return

        # Filter out ignored entries
        entries = [e for e in entries if not should_ignore(e, base_path)]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                add_tree(entry, prefix + extension, depth + 1)

    lines.append(f"{base_path.name}/")
    add_tree(base_path)

    return "\n".join(lines)


def get_key_files_content(base_path: Path) -> Dict[str, str]:
    """
    Read content from key configuration files.

    Args:
        base_path: Root directory to scan

    Returns:
        Dictionary mapping filename to content
    """
    contents = {}

    for pattern in KEY_FILE_PATTERNS:
        # Search for the file
        matches = list(base_path.glob(pattern))
        if not matches:
            # Try case-insensitive for README
            if pattern.lower().startswith('readme'):
                for f in base_path.iterdir():
                    if f.is_file() and f.name.lower().startswith('readme'):
                        matches = [f]
                        break

        for file_path in matches[:1]:  # Only first match
            if file_path.is_file() and not should_ignore(file_path, base_path):
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    # Truncate if too long
                    if len(content) > MAX_FILE_CONTENT_LENGTH:
                        content = content[:MAX_FILE_CONTENT_LENGTH] + "\n... (truncated)"
                    contents[file_path.name] = content
                except Exception:
                    pass

    return contents


def get_git_info(base_path: Path) -> Optional[Dict[str, str]]:
    """
    Get git repository information if available.

    Returns:
        Dictionary with git info, or None if not a git repo
    """
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=base_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        info = {}

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=base_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()

        # Get recent commits (just count)
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=base_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            info["commit_count"] = result.stdout.strip()

        return info
    except Exception:
        return None


def analyze_project_context(base_path: Path, logger: PrdLogger) -> Dict[str, str]:
    """
    Analyze the project and collect context information.

    Args:
        base_path: Project root directory
        logger: Logger instance

    Returns:
        Dictionary with project_structure and key_files_content
    """
    logger.info("Analyzing project structure...")

    # Get directory tree
    tree = get_project_tree(base_path)
    logger.info(f"Found project tree ({len(tree.splitlines())} entries)")

    # Get key files content
    key_files = get_key_files_content(base_path)
    logger.info(f"Read {len(key_files)} key files: {', '.join(key_files.keys())}")

    # Format key files content
    key_files_str = ""
    if key_files:
        for filename, content in key_files.items():
            key_files_str += f"\n### {filename}\n```\n{content}\n```\n"
    else:
        key_files_str = "(No key configuration files found)"

    # Get git info
    git_info = get_git_info(base_path)
    if git_info:
        logger.info(f"Git repo: branch={git_info.get('branch', 'N/A')}, commits={git_info.get('commit_count', 'N/A')}")
        tree = f"Git Branch: {git_info.get('branch', 'N/A')}\n\n{tree}"

    return {
        "project_structure": tree,
        "key_files_content": key_files_str
    }


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
    project_root: Path,
    prd_dir: PrdDir,
    logger: PrdLogger,
    config: Config,
    model: str = "sonnet"
) -> PRD:
    """
    Convert a spec file to PRD using Claude with project context.

    Args:
        spec_path: Path to spec markdown file
        project_name: Name of the project
        project_root: Root directory of the project
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

    # Analyze project context
    context = analyze_project_context(project_root, logger)

    # Build prompt
    prompt = CONVERSION_PROMPT.format(
        project_structure=context["project_structure"],
        key_files_content=context["key_files_content"],
        spec_content=spec_content,
        project_name=project_name
    )

    logger.info(f"Calling Claude ({model}) to convert spec to PRD...")
    logger.log_separator()

    # Execute Claude
    cli = ClaudeCLI(
        output_timeout_minutes=config.timeout_minutes,
        allowed_tools=[],  # No tools needed for conversion
        model=model
    )

    result = cli.execute(prompt)

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
        logger.error("Raw output:")
        logger.error(result.output[:1000])
        raise

    # Add source spec info
    prd_data["source_spec"] = str(spec_path)
    prd_data["created_at"] = datetime.now().isoformat()
    prd_data["updated_at"] = datetime.now().isoformat()

    # Create PRD object
    prd = PRD.from_dict(prd_data)

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

    # Determine project root (current directory)
    project_root = Path.cwd()

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
            project_root=project_root,
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
        logger.info("")
        logger.info("Next steps:")
        logger.info(f"  impl-prd --prd {output_path}")

        return 0

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
