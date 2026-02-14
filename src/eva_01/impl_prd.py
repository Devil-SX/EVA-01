#!/usr/bin/env python3
"""
impl-prd: Autonomous loop to implement PRD user stories.

Usage:
    impl-prd [OPTIONS]

Options:
    --prd FILE          Specify PRD file (default: latest in .prd/prds/)
    --max-iterations N  Maximum loop iterations (default: 50)
    --timeout MINUTES   Claude timeout in minutes (default: 15)
    --model MODEL       Claude model: opus/sonnet/haiku (default: opus)
    --resume            Resume from last state
    --status            Show current status and exit
    --reset             Reset state and start fresh
    --help              Show this help message
"""

import argparse
import signal
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports when run directly
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import PrdProject, find_project_root, Config
from prd_schema import PRD, LoopState
from claude_cli import ClaudeCLI, check_claude_installed
from session_logger import SessionLogger
from circuit_breaker import SimpleCircuitBreaker
from rate_limiter import RateLimiter
from prompt.implementation import IMPLEMENTATION_PROMPT


def parse_args():
    parser = argparse.ArgumentParser(
        description="Autonomous loop to implement PRD user stories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prd",
        type=str,
        help="Path to PRD file (default: latest in .prd/prds/)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maximum loop iterations (default: 50)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Claude timeout in minutes (default: 15)",
    )
    parser.add_argument(
        "--model", "-m",
        choices=["opus", "sonnet", "haiku"],
        default="opus",
        help="Claude model to use (default: opus)",
    )
    parser.add_argument(
        "--no-progress-threshold",
        type=int,
        default=3,
        help="Stop after N loops with no progress (default: 3)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last state",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status and exit",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset state and start fresh",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--no-observe",
        action="store_true",
        help="Don't run observe-impl after completion",
    )
    return parser.parse_args()


class ImplementationLoop:
    """Main implementation loop for PRD."""

    def __init__(
        self,
        project: PrdProject,
        prd: PRD,
        prd_path: Path,
        config: Config,
        logger: SessionLogger,
        args: argparse.Namespace,
        max_iterations: int = 50,
        timeout_minutes: int = 15,
        no_progress_threshold: int = 3,
        model: str = "opus",
    ):
        self.project = project
        self.prd = prd
        self.prd_path = prd_path
        self.config = config
        self.logger = logger
        self.args = args
        self.max_iterations = max_iterations
        self.model = model

        # Initialize components
        self.cli = ClaudeCLI(
            output_timeout_minutes=timeout_minutes,
            allowed_tools=config.allowed_tools,
            model=model,
            dangerously_skip_permissions=True,  # Autonomous mode
        )
        self.circuit_breaker = SimpleCircuitBreaker(no_progress_threshold)
        rate_limit_state_file = project.prd_dir / "rate_limit.json"
        self.rate_limiter = RateLimiter(config.max_calls_per_hour, rate_limit_state_file)

        # State
        self.state = project.load_state()
        self.running = True
        self.exit_reason = ""

        # Signal handling
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self.logger.warn("Interrupt received, stopping after current iteration...")
        self.running = False
        self.exit_reason = "user_interrupt"

    def run(self) -> bool:
        """
        Run the implementation loop.

        Returns:
            True if all stories completed, False otherwise
        """
        # Save session start info
        self.logger.save_config(self.config)
        self.logger.save_prd_snapshot(self.prd)
        self.logger.save_run_args(self.args)

        self.logger.separator()
        self.logger.info(f"impl-prd: Implementing {self.prd.project}")
        self.logger.info(f"Model: {self.model}")
        self.logger.separator()

        # Show initial status
        done, total = self.prd.get_progress()
        self.logger.info(f"PRD: {self.prd.description}")
        self.logger.info(f"Progress: {done}/{total} stories complete")

        if self.prd.is_complete():
            self.logger.success("All stories already complete!")
            self._finalize()
            return True

        # Update state
        self.state.status = "running"
        self.state.current_prd = str(self.prd_path)
        self.project.save_state(self.state)

        # Main loop
        iteration = self.state.loop_count
        while self.running and iteration < self.max_iterations:
            iteration += 1
            self.state.loop_count = iteration

            # Check rate limit
            if not self.rate_limiter.can_call():
                wait_time = self.rate_limiter.get_wait_time()
                self.logger.warn(f"Rate limit reached, waiting {wait_time}s...")
                self._wait_with_countdown(wait_time)
                continue

            # Check circuit breaker
            if self.circuit_breaker.should_stop():
                status = self.circuit_breaker.get_status()
                self.logger.error(f"Circuit breaker triggered: {status.reason}")
                self.exit_reason = "circuit_breaker"
                break

            # Get next story
            story = self.prd.get_next_story()
            if not story:
                self.logger.success("All stories complete!")
                self.exit_reason = "complete"
                break

            self.state.current_story_id = story.id

            # Start loop with session logger (creates loop-specific log file)
            loop_log_path = self.logger.start_loop(
                loop_num=iteration,
                story_id=story.id,
                story_title=story.title
            )

            # Build prompt
            prompt = self._build_prompt(story)

            # Execute Claude
            self.logger.info("Executing Claude...")
            self.logger.start_timer("claude")

            # Get the loop log file for stream output
            loop_log_file = self.logger.get_loop_log_file()
            result = self.cli.execute(prompt, log_file=loop_log_file)

            api_duration = self.logger.stop_timer("claude")
            self.rate_limiter.record_call()
            self.state.total_api_calls += 1

            # Handle timeout
            if result.timeout:
                self.logger.error(f"Timeout: {result.timeout_reason}")
                self.circuit_breaker.record_failure("timeout")
                self.logger.end_loop(
                    success=False,
                    timeout=True,
                    error=result.timeout_reason,
                    api_duration=api_duration
                )
                continue

            # Handle failure
            if not result.success:
                self.logger.error(f"Claude execution failed (exit code {result.exit_code})")
                self.circuit_breaker.record_failure(f"exit_code_{result.exit_code}")
                self.logger.end_loop(
                    success=False,
                    error=f"exit_code_{result.exit_code}",
                    api_duration=api_duration
                )
                continue

            # Reload PRD to check if Claude updated the story status
            old_passes = story.passes
            self.prd = PRD.load(self.prd_path)

            # Find the story and check if it passed
            updated_story = next((s for s in self.prd.userStories if s.id == story.id), None)
            story_passed = updated_story and updated_story.passes and not old_passes

            if story_passed:
                self.logger.success(f"Story {story.id} completed!")
                self.circuit_breaker.record_success()
            else:
                # Story not marked as passed - record as no progress
                self.circuit_breaker.record_failure("no_progress")

            # End loop
            self.logger.end_loop(
                success=True,
                story_passed=story_passed,
                api_duration=api_duration
            )

            # Log stats
            done, total = self.prd.get_progress()
            self.logger.log_stats(
                api_calls=self.state.total_api_calls,
                max_calls=self.config.max_calls_per_hour,
                stories_done=done,
                total_stories=total,
            )

            # Save state
            self.project.save_state(self.state)

            # Check if all done
            if self.prd.is_complete():
                self.logger.success("All stories complete!")
                self.exit_reason = "complete"
                break

            # Brief pause between iterations
            time.sleep(2)

        # Final status
        self._finalize()

        return self.prd.is_complete()

    def _build_prompt(self, story) -> str:
        """Build the prompt for implementing a story."""
        # Format acceptance criteria
        criteria_list = "\n".join(f"- [ ] {c}" for c in story.acceptanceCriteria)

        return IMPLEMENTATION_PROMPT.format(
            project_name=self.prd.project,
            project_description=self.prd.description,
            story_id=story.id,
            story_title=story.title,
            story_description=story.description,
            acceptance_criteria=criteria_list,
            prd_path=self.prd_path,
        )

    def _wait_with_countdown(self, seconds: int) -> None:
        """Wait with countdown display."""
        while seconds > 0 and self.running:
            mins, secs = divmod(seconds, 60)
            print(f"\rWaiting: {mins:02d}:{secs:02d}", end="", flush=True)
            time.sleep(1)
            seconds -= 1
        print()

    def _finalize(self) -> None:
        """Finalize the loop and save state."""
        # Update state
        if self.exit_reason == "complete":
            self.state.status = "completed"
        elif self.exit_reason == "user_interrupt":
            self.state.status = "paused"
        elif self.exit_reason == "circuit_breaker":
            self.state.status = "failed"
        else:
            self.state.status = "stopped"
            if not self.exit_reason:
                self.exit_reason = "max_iterations"

        self.project.save_state(self.state)

        # Get final stats
        done, total = self.prd.get_progress()

        # Log completion status before finalizing (finalize closes log file)
        if self.prd.is_complete():
            self.logger.success("All stories implemented!")
        else:
            remaining = [s for s in self.prd.userStories if not s.passes]
            self.logger.warn(f"Remaining stories: {len(remaining)}")
            for s in remaining[:5]:
                self.logger.warn(f"  - {s.id}: {s.title}")

        # Finalize session logger (writes summary.json and closes log file)
        self.logger.finalize(
            exit_reason=self.exit_reason,
            total_api_calls=self.state.total_api_calls,
            stories_completed=done,
            total_stories=total,
            prd_file=str(self.prd_path)
        )


def show_status(project: PrdProject) -> int:
    """Show current status and exit."""
    from logger import PrdLogger
    logger = PrdLogger()

    state = project.load_state()

    logger.separator()
    logger.info("impl-prd Status")
    logger.separator()

    logger.info(f"Status: {state.status}")
    logger.info(f"Current PRD: {state.current_prd or 'None'}")
    logger.info(f"Current Story: {state.current_story_id or 'None'}")
    logger.info(f"Loop Count: {state.loop_count}")
    logger.info(f"Total API Calls: {state.total_api_calls}")
    logger.info(f"Last Run: {state.last_run or 'Never'}")

    # Load PRD if available
    prd_path = project.get_latest_prd()
    if prd_path:
        try:
            prd = PRD.load(prd_path)
            done, total = prd.get_progress()
            logger.info(f"PRD Progress: {done}/{total} stories")
        except Exception:
            pass

    return 0


def main():
    args = parse_args()
    session_dir = None  # Track session directory for observe-impl

    # Find project
    project_root = find_project_root()
    if not project_root:
        print("Error: .prd directory not found")
        print("Run 'spec-to-prd <spec.md>' first")
        return 1

    project = PrdProject(project_root)

    # Handle --status (uses simple logger)
    if args.status:
        return show_status(project)

    # Handle --reset
    if args.reset:
        from logger import PrdLogger
        logger = PrdLogger()
        logger.info("Resetting state...")
        LoopState().save(project.state_file)
        logger.success("State reset complete")
        return 0

    # Check Claude CLI
    if not check_claude_installed():
        print("Error: Claude Code CLI not found")
        print("Install with: npm install -g @anthropic-ai/claude-code")
        return 1

    # Load config
    config = project.load_config()

    # Override config with CLI args
    if args.max_iterations:
        config.max_iterations = args.max_iterations
    if args.timeout:
        config.timeout_minutes = args.timeout
    if args.no_progress_threshold:
        config.no_progress_threshold = args.no_progress_threshold

    # Find PRD file
    if args.prd:
        prd_path = Path(args.prd)
        if not prd_path.exists():
            prd_path = project.prds_dir / args.prd
        if not prd_path.exists():
            print(f"Error: PRD file not found: {args.prd}")
            return 1
    else:
        prd_path = project.get_latest_prd()
        if not prd_path:
            print("Error: No PRD files found in .prd/prds/")
            print("Run 'spec-to-prd' first to generate PRD files")
            return 1

    # Load PRD
    try:
        prd = PRD.load(prd_path)
    except Exception as e:
        print(f"Error: Failed to load PRD: {e}")
        return 1

    # Check for resume — auto-resume if previous run was interrupted
    state = project.load_state()
    if not args.resume and state.loop_count > 0 and state.status in ("running", "paused"):
        print(f"Auto-resuming previous run (loop #{state.loop_count}, status: {state.status})")
        print("Use --reset to start fresh instead")
        args.resume = True

    # Initialize session logger
    logger = SessionLogger(logs_dir=project.logs_dir)
    session_dir = logger.session_dir  # Save for observe-impl
    logger.info(f"Loaded PRD: {prd_path.name}")

    try:
        # Create and run loop
        loop = ImplementationLoop(
            project=project,
            prd=prd,
            prd_path=prd_path,
            config=config,
            logger=logger,
            args=args,
            max_iterations=config.max_iterations,
            timeout_minutes=config.timeout_minutes,
            no_progress_threshold=config.no_progress_threshold,
            model=args.model,
        )

        success = loop.run()
        return 0 if success else 1

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Run observe-impl after completion (unless disabled)
        if not args.no_observe and session_dir and session_dir.exists():
            try:
                from observe_impl import run_observe
                run_observe(session_dir, create_issue=True, model="haiku")
            except Exception as e:
                print(f"Warning: observe-impl failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
