#!/usr/bin/env python3
"""
spec-to-prd: Convert spec markdown files to PRD JSON format.

Usage:
    spec-to-prd <SPEC_FILE> [OPTIONS]

Options:
    SPEC_FILE           Path to spec markdown file
    --output FILE       Output PRD JSON file path
    --project NAME      Project name (default: inferred from filename)
    --model MODEL       Claude model: opus/sonnet/haiku (default: opus)
    --timeout MIN       Claude timeout in minutes (default: 15)
    -h, --help          Show this help message

Note: .prd directory will be automatically initialized if not exists.
      Claude will analyze the existing project structure to generate context-aware PRD.
"""

import argparse
import json
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
from prompt.conversion import CONVERSION_PROMPT


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
        default="opus",
        help="Claude model to use (default: opus)"
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
    model: str = "opus"
) -> tuple[PRD, Path]:
    """
    Convert a spec file to PRD using Claude.
    Claude will explore the project structure and write PRD to file.

    Args:
        spec_path: Path to spec markdown file
        project_name: Name of the project
        prd_dir: PrdDir instance
        logger: Logger instance
        config: Config instance
        model: Claude model to use

    Returns:
        Tuple of (PRD object, path to PRD file)
    """
    logger.info(f"Reading spec file: {spec_path}")

    # Read spec content
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Generate timestamped output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prd_filename = f"prd_{timestamp}.json"
    prd_output_path = prd_dir.prds_dir / prd_filename

    # Build prompt - Claude will explore the project and write PRD to file
    prompt = CONVERSION_PROMPT.format(
        spec_content=spec_content,
        project_name=project_name,
        prd_output_path=prd_output_path
    )

    # Create log file for Claude's stream output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stream_log_path = prd_dir.logs_dir / f"spec_to_prd_{timestamp}_stream.log"
    stream_log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Calling Claude ({model}) to analyze project and generate PRD...")
    logger.info("Claude will explore project structure using its tools...")
    logger.info(f"PRD will be saved to: {prd_output_path}")
    logger.info(f"Stream output saved to: {stream_log_path}")
    logger.log_separator()

    # Execute Claude with tools enabled for project exploration and file writing
    cli = ClaudeCLI(
        output_timeout_minutes=config.timeout_minutes,
        allowed_tools=["Read", "Write", "Glob", "Grep", "Bash(ls *)"],
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
        raise RuntimeError(f"Claude execution failed. See log: {stream_log_path}")

    logger.info(f"Claude execution completed in {result.duration_seconds:.1f}s")

    # Check if PRD file was created
    if not prd_output_path.exists():
        logger.error(f"Claude did not create PRD file at: {prd_output_path}")
        logger.error(f"See full output in: {stream_log_path}")
        raise RuntimeError(f"PRD file was not created: {prd_output_path}")

    prd_path = prd_output_path
    logger.info(f"PRD file created: {prd_path.name}")

    # Load and validate PRD
    try:
        prd = PRD.load(prd_path)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in PRD file: {e}")
        logger.error(f"PRD file: {prd_path}")
        raise
    except KeyError as e:
        logger.error(f"Missing required field in PRD: {e}")
        logger.error(f"PRD file: {prd_path}")
        raise

    # Add source spec info if not present
    prd_data = prd.to_dict()
    if not prd_data.get("source_spec"):
        prd_data["source_spec"] = str(spec_path)
        prd_data["created_at"] = datetime.now().isoformat()
        prd_data["updated_at"] = datetime.now().isoformat()
        prd = PRD.from_dict(prd_data)
        prd.save(prd_path)

    logger.success(f"PRD created with {len(prd.userStories)} user stories")

    return prd, prd_path


def main():
    """Main entry point."""
    args = parse_args()

    # Check for spec file
    if not args.spec_file:
        print("Error: SPEC_FILE is required")
        print("Usage: spec-to-prd <SPEC_FILE> [OPTIONS]")
        return 1

    # Project root is current working directory
    project_root = Path.cwd().resolve()

    # Resolve spec path relative to current directory
    spec_path = Path(args.spec_file).resolve()

    if not spec_path.exists():
        print(f"Error: Spec file not found: {spec_path}")
        return 1

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

    try:
        # Convert spec to PRD (Claude will create the file)
        prd, prd_path = convert_spec_to_prd(
            spec_path=spec_path,
            project_name=project_name,
            prd_dir=prd_dir,
            logger=logger,
            config=config,
            model=args.model
        )

        # If user specified output path, move the file
        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = project_root / output_path
            import shutil
            shutil.move(str(prd_path), str(output_path))
            prd_path = output_path
            logger.info(f"PRD moved to: {output_path}")

        logger.success(f"PRD saved to: {prd_path}")

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
        logger.info(f"  impl-prd --prd {prd_path}")

        return 0

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
