"""Claude Code CLI wrapper with streaming output and timeout detection."""

import json
import subprocess
import sys
import time
import select
import os
from dataclasses import dataclass
from typing import Optional, List, Callable, TextIO


@dataclass
class ExecutionResult:
    """Result of a Claude CLI execution."""
    success: bool
    output: str
    session_id: str = ""
    duration_seconds: float = 0.0
    exit_code: int = 0
    timeout: bool = False
    timeout_reason: str = ""  # "output_timeout" or "process_timeout"


class ClaudeCLI:
    """
    Wrapper for Claude Code CLI with streaming output and timeout detection.

    Uses stream-json output format to enable real-time output monitoring
    and timeout detection when no output is received for too long.
    """

    # Model name mapping
    MODEL_MAP = {
        "opus": "claude-opus-4-5-20251101",
        "sonnet": "claude-sonnet-4-20250514",
        "haiku": "claude-haiku-3-5-20241022",
    }

    def __init__(
        self,
        output_timeout_minutes: int = 15,
        allowed_tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        dangerously_skip_permissions: bool = False
    ):
        """
        Initialize Claude CLI wrapper.

        Args:
            output_timeout_minutes: Kill process if no output for this many minutes
            allowed_tools: List of allowed tools for Claude
            model: Model to use (opus/sonnet/haiku, default: sonnet)
            dangerously_skip_permissions: Skip all permission prompts for autonomous mode
        """
        self.output_timeout = output_timeout_minutes * 60  # Convert to seconds
        self.allowed_tools = allowed_tools or []
        self.model = model
        self.dangerously_skip_permissions = dangerously_skip_permissions
        self.last_output_time = 0.0

    def execute(
        self,
        prompt: str,
        on_output: Optional[Callable[[str], None]] = None,
        working_dir: Optional[str] = None,
        log_file: Optional[TextIO] = None
    ) -> ExecutionResult:
        """
        Execute Claude Code CLI with streaming output.

        Args:
            prompt: The prompt to send to Claude
            on_output: Optional callback for real-time output (receives text chunks)
            working_dir: Working directory for the command
            log_file: Optional file handle to write raw stream output

        Returns:
            ExecutionResult with success status, output, timing, etc.
        """
        start_time = time.time()

        # Build command
        cmd = self._build_command(prompt)

        try:
            # Start process with unbuffered output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
                bufsize=0,  # Unbuffered
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )

            # Monitor stream with timeout detection
            output, timed_out, timeout_reason = self._monitor_stream(
                process, on_output, log_file
            )

            # Get exit code
            if timed_out:
                exit_code = -1
            else:
                exit_code = process.wait()

            duration = time.time() - start_time

            # Extract session ID from output if available
            session_id = self._extract_session_id(output)

            return ExecutionResult(
                success=exit_code == 0 and not timed_out,
                output=output,
                session_id=session_id,
                duration_seconds=duration,
                exit_code=exit_code,
                timeout=timed_out,
                timeout_reason=timeout_reason
            )

        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                output="Error: 'claude' command not found. Please install Claude Code CLI.",
                exit_code=-1
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=f"Error executing Claude CLI: {str(e)}",
                exit_code=-1
            )

    def _build_command(self, prompt: str) -> List[str]:
        """Build the claude command with arguments."""
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
        ]

        # Add dangerous skip permissions for autonomous mode
        if self.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Add model selection
        if self.model:
            model_id = self.MODEL_MAP.get(self.model.lower(), self.model)
            cmd.extend(["--model", model_id])

        # Add allowed tools
        if self.allowed_tools:
            cmd.append("--allowedTools")
            cmd.extend(self.allowed_tools)

        # Add prompt
        cmd.extend(["-p", prompt])

        return cmd

    def _monitor_stream(
        self,
        process: subprocess.Popen,
        on_output: Optional[Callable[[str], None]],
        log_file: Optional[TextIO] = None
    ) -> tuple:
        """
        Monitor streaming output with timeout detection.

        Returns:
            (text_content, timed_out, timeout_reason)
            text_content is the extracted text from Claude's response (not raw JSON)
        """
        text_chunks = []  # Extracted text content
        self.last_output_time = time.time()

        # Use select for non-blocking read (Unix-specific)
        # For Windows compatibility, would need threading
        fd = process.stdout.fileno()

        while True:
            # Check for output timeout
            idle_time = time.time() - self.last_output_time
            if idle_time > self.output_timeout:
                process.kill()
                process.wait()
                return "".join(text_chunks), True, "output_timeout"

            # Non-blocking read with 1 second timeout
            if sys.platform != "win32":
                ready, _, _ = select.select([fd], [], [], 1.0)
                if not ready:
                    # Check if process ended
                    if process.poll() is not None:
                        break
                    continue

            # Read available data
            try:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue

                line = line.decode("utf-8", errors="replace")
                self.last_output_time = time.time()

                # Write raw output to log file if provided
                if log_file:
                    log_file.write(line)
                    log_file.flush()

                # Parse stream and extract text content
                text = self._handle_stream_line(line, on_output)
                if text:
                    text_chunks.append(text)

            except Exception:
                if process.poll() is not None:
                    break

        return "".join(text_chunks), False, ""

    def _handle_stream_line(
        self,
        line: str,
        on_output: Optional[Callable[[str], None]]
    ) -> Optional[str]:
        """
        Handle a single line of stream-json output.

        Extracts text content and calls the output callback.

        Returns:
            Extracted text content, or None if no text in this line
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
            extracted_text = None

            # Handle different event types
            if data.get("type") == "stream_event":
                event = data.get("event", {})
                event_type = event.get("type", "")

                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            print(text, end="", flush=True)
                            if on_output:
                                on_output(text)
                            extracted_text = text

                elif event_type == "content_block_start":
                    content_block = event.get("content_block", {})
                    if content_block.get("type") == "tool_use":
                        tool_name = content_block.get("name", "")
                        marker = f"\n[Tool: {tool_name}]\n"
                        print(marker, end="", flush=True)
                        if on_output:
                            on_output(marker)
                        extracted_text = marker

                elif event_type == "content_block_stop":
                    print("\n", end="", flush=True)
                    if on_output:
                        on_output("\n")
                    extracted_text = "\n"

            elif data.get("type") == "result":
                # Final result message - extract any useful info
                pass

            return extracted_text

        except json.JSONDecodeError:
            # Not JSON, might be raw output
            print(line, flush=True)
            if on_output:
                on_output(line + "\n")
            return line + "\n"

    def _extract_session_id(self, output: str) -> str:
        """Extract session ID from output if present."""
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Check various possible locations
                if "sessionId" in data:
                    return data["sessionId"]
                if "session_id" in data:
                    return data["session_id"]
                if data.get("type") == "result":
                    return data.get("sessionId", "")
            except json.JSONDecodeError:
                continue
        return ""


def execute_claude(
    prompt: str,
    timeout_minutes: int = 15,
    allowed_tools: Optional[List[str]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    working_dir: Optional[str] = None
) -> ExecutionResult:
    """
    Convenience function to execute Claude CLI.

    Args:
        prompt: The prompt to send to Claude
        timeout_minutes: Kill if no output for this many minutes
        allowed_tools: List of allowed tools
        on_output: Optional callback for real-time output
        working_dir: Working directory

    Returns:
        ExecutionResult
    """
    cli = ClaudeCLI(
        output_timeout_minutes=timeout_minutes,
        allowed_tools=allowed_tools
    )
    return cli.execute(prompt, on_output=on_output, working_dir=working_dir)


def check_claude_installed() -> bool:
    """
    Check if Claude Code CLI is installed and accessible.

    Returns:
        True if claude command is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
