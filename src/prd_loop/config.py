"""Configuration management for PRD Loop."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class Config:
    """Configuration for PRD Loop."""
    max_calls_per_hour: int = 100
    max_iterations: int = 50
    timeout_minutes: int = 15
    output_format: str = "stream"  # json or stream
    allowed_tools: List[str] = None
    session_expiry_hours: int = 24
    max_consecutive_failures: int = 3
    no_progress_threshold: int = 3  # Alias for circuit breaker threshold

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = [
                "Write", "Read", "Edit", "Bash(git *)", "Bash(npm *)", "Bash(pytest)"
            ]

    def to_dict(self) -> dict:
        d = asdict(self)
        # Always true in impl-prd (autonomous mode), this field is ignored
        d["dangerously_skip_permissions"] = True
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        """Save config to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            max_calls_per_hour=data.get("max_calls_per_hour", 100),
            max_iterations=data.get("max_iterations", 50),
            timeout_minutes=data.get("timeout_minutes", 15),
            output_format=data.get("output_format", "stream"),
            allowed_tools=data.get("allowed_tools"),
            session_expiry_hours=data.get("session_expiry_hours", 24),
            max_consecutive_failures=data.get("max_consecutive_failures", 3),
            no_progress_threshold=data.get("no_progress_threshold", 3)
        )

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load config from JSON file, or return defaults if not exists."""
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class PrdDir:
    """Manages the .prd directory structure."""

    def __init__(self, base_path: Path = None):
        self.base = base_path or Path.cwd()
        self.prd_dir = self.base / ".prd"
        self.specs_dir = self.prd_dir / "specs"
        self.prds_dir = self.prd_dir / "prds"
        self.logs_dir = self.prd_dir / "logs"
        self.config_file = self.prd_dir / "config.json"
        self.state_file = self.prd_dir / "state.json"

    def exists(self) -> bool:
        """Check if .prd directory exists."""
        return self.prd_dir.exists()

    def init(self) -> None:
        """Initialize .prd directory structure."""
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.prds_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create default config if not exists
        if not self.config_file.exists():
            Config().save(self.config_file)

    def get_config(self) -> Config:
        """Get configuration."""
        return Config.load(self.config_file)

    def get_latest_prd(self) -> Optional[Path]:
        """Get the most recently modified PRD file."""
        prd_files = list(self.prds_dir.glob("*.json"))
        if not prd_files:
            return None
        return max(prd_files, key=lambda p: p.stat().st_mtime)

    def get_log_path(self, prefix: str) -> Path:
        """Generate a new log file path with timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return self.logs_dir / f"{prefix}_{timestamp}.log"


def find_project_root(start_path: Path = None) -> Optional[Path]:
    """
    Find the project root by searching for .prd directory.

    Args:
        start_path: Starting path to search from (default: current directory)

    Returns:
        Path to directory containing .prd, or None if not found
    """
    current = (start_path or Path.cwd()).resolve()

    # Search up the directory tree
    while current != current.parent:
        if (current / ".prd").is_dir():
            return current
        current = current.parent

    # Check root as well
    if (current / ".prd").is_dir():
        return current

    return None


class PrdProject(PrdDir):
    """
    Extended PrdDir with project-specific functionality for impl-prd.

    Adds state management and project-level operations.
    """

    def __init__(self, project_root: Path):
        super().__init__(project_root)
        self.project_root = project_root

    def load_state(self) -> "LoopState":
        """Load loop state from file."""
        from prd_schema import LoopState
        return LoopState.load(self.state_file)

    def save_state(self, state: "LoopState") -> None:
        """Save loop state to file."""
        state.save(self.state_file)

    def load_config(self) -> Config:
        """Load project configuration."""
        return self.get_config()
