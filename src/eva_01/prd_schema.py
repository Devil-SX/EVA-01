"""PRD JSON data structures and validation."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
from pathlib import Path


@dataclass
class UserStory:
    """Represents a single user story in a PRD."""
    id: str
    title: str
    description: str
    acceptanceCriteria: List[str]
    priority: int
    passes: bool = False
    notes: str = ""
    testPlan: str = ""
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserStory":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            acceptanceCriteria=data["acceptanceCriteria"],
            priority=data["priority"],
            passes=data.get("passes", False),
            notes=data.get("notes", ""),
            testPlan=data.get("testPlan", ""),
            completed_at=data.get("completed_at")
        )


@dataclass
class PRD:
    """Represents a Product Requirements Document."""
    project: str
    branchName: str
    description: str
    userStories: List[UserStory]
    source_spec: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "branchName": self.branchName,
            "description": self.description,
            "source_spec": self.source_spec,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "userStories": [s.to_dict() for s in self.userStories]
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: Path) -> None:
        """Save PRD to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: dict) -> "PRD":
        return cls(
            project=data["project"],
            branchName=data["branchName"],
            description=data["description"],
            source_spec=data.get("source_spec", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            userStories=[UserStory.from_dict(s) for s in data["userStories"]]
        )

    @classmethod
    def load(cls, path: Path) -> "PRD":
        """Load PRD from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_next_story(self) -> Optional[UserStory]:
        """Get the next story to implement (lowest priority with passes=False)."""
        pending = [s for s in self.userStories if not s.passes]
        if not pending:
            return None
        return min(pending, key=lambda s: s.priority)

    def mark_story_complete(self, story_id: str, notes: str = "") -> bool:
        """Mark a story as complete."""
        for story in self.userStories:
            if story.id == story_id:
                story.passes = True
                story.completed_at = datetime.now().isoformat()
                if notes:
                    story.notes = notes
                self.updated_at = datetime.now().isoformat()
                return True
        return False

    def is_complete(self) -> bool:
        """Check if all stories are complete."""
        return all(s.passes for s in self.userStories)

    def get_progress(self) -> tuple:
        """Get progress as (completed, total)."""
        completed = sum(1 for s in self.userStories if s.passes)
        total = len(self.userStories)
        return completed, total


@dataclass
class LoopState:
    """Represents the current state of the impl-prd loop."""
    current_prd: str = ""
    current_story_id: str = ""
    loop_count: int = 0
    total_api_calls: int = 0
    last_run: str = ""
    session_id: str = ""
    status: str = "idle"  # idle, running, paused, completed, failed
    consecutive_failures: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        """Save state to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: dict) -> "LoopState":
        return cls(
            current_prd=data.get("current_prd", ""),
            current_story_id=data.get("current_story_id", ""),
            loop_count=data.get("loop_count", 0),
            total_api_calls=data.get("total_api_calls", 0),
            last_run=data.get("last_run", ""),
            session_id=data.get("session_id", ""),
            status=data.get("status", "idle"),
            consecutive_failures=data.get("consecutive_failures", 0)
        )

    @classmethod
    def load(cls, path: Path) -> "LoopState":
        """Load state from JSON file."""
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
