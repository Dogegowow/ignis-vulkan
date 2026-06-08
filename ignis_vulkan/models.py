from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RawActivity:
    row_number: int
    start: datetime
    end: datetime
    category: str
    title: str
    description: str
    participants_text: str
    entered_by: str


@dataclass(frozen=True)
class Activity:
    row_number: int
    start: datetime
    end: datetime
    ignis_category: str
    vulkan_category: str
    title: str
    vulkan_note: str
    description: str
    participants: tuple[str, ...]
    entered_by: str
    hours_value: float
    hours_text: str
    date_text: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def history_key(self) -> str:
        return f"{self.start:%Y-%m-%d %H:%M}|{self.end:%Y-%m-%d %H:%M}|{self.title}|{self.ignis_category}"


@dataclass(frozen=True)
class MemberMatch:
    matched: tuple[str, ...]
    missing: tuple[str, ...]


@dataclass(frozen=True)
class VulkanMember:
    clan_id: int
    org_id: int
    ime: str
    priimek: str

    @property
    def display_name(self) -> str:
        return f"{self.priimek} {self.ime}".strip()
