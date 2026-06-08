from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .models import Activity


PROJECT_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_DIR / "local_state"
LEGACY_APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "IgnisVulkanTransfer"


@dataclass
class AppConfig:
    vulkan_url: str = ""
    members_path: str = ""


@dataclass
class ImportRecord:
    key: str
    row_number: int
    title: str
    imported_at: str


@dataclass
class AppState:
    config: AppConfig = field(default_factory=AppConfig)
    completed: dict[str, ImportRecord] = field(default_factory=dict)
    missing_members: list[dict[str, str]] = field(default_factory=list)


class StateStore:
    def __init__(self, app_dir: Path = STATE_DIR):
        self.app_dir = app_dir
        self.state_path = app_dir / "state.json"
        self.legacy_state_path = LEGACY_APP_DIR / "state.json"

    @property
    def browser_profile_dir(self) -> Path:
        legacy_profile = LEGACY_APP_DIR / "browser-profile"
        try:
            if legacy_profile.exists():
                return legacy_profile
        except OSError:
            pass
        return self.app_dir / "browser-profile"

    def load(self) -> AppState:
        self._migrate_legacy_state()
        if not self.state_path.exists():
            return AppState()
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        completed = {
            key: ImportRecord(**record)
            for key, record in data.get("completed", {}).items()
        }
        return AppState(
            config=AppConfig(**data.get("config", {})),
            completed=completed,
            missing_members=list(data.get("missing_members", [])),
        )

    def _migrate_legacy_state(self) -> None:
        try:
            if self.state_path.exists() or not self.legacy_state_path.exists():
                return
            self.app_dir.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(self.legacy_state_path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            return

    def save(self, state: AppState) -> None:
        self.app_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "config": asdict(state.config),
            "completed": {
                key: asdict(record)
                for key, record in state.completed.items()
            },
            "missing_members": state.missing_members,
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_completed(self, state: AppState, activity: Activity) -> None:
        state.completed[activity.history_key] = ImportRecord(
            key=activity.history_key,
            row_number=activity.row_number,
            title=activity.title,
            imported_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.save(state)

    def log_missing_members(self, state: AppState, activity: Activity, names: list[str]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        for name in names:
            state.missing_members.append(
                {
                    "name": name,
                    "activity": activity.title,
                    "date": activity.start.strftime("%Y-%m-%d"),
                    "logged_at": now,
                }
            )
        self.save(state)
