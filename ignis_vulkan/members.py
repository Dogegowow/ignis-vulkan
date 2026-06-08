from __future__ import annotations

import json
from pathlib import Path

from .models import VulkanMember
from .transform import normalize_name


class MemberRegistryError(ValueError):
    pass


class MemberRegistry:
    def __init__(self, members: list[VulkanMember]):
        self.members = members
        self.by_name: dict[str, VulkanMember] = {}
        self.duplicates: dict[str, list[VulkanMember]] = {}
        for member in members:
            for key in self._keys_for(member):
                if key in self.by_name:
                    existing = self.by_name.pop(key)
                    self.duplicates[key] = [existing, member]
                elif key in self.duplicates:
                    self.duplicates[key].append(member)
                else:
                    self.by_name[key] = member

    @classmethod
    def from_file(cls, path: str | Path) -> "MemberRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        rows = data.get("value", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise MemberRegistryError("Member file must contain a list or a {'value': [...]} response.")

        members: list[VulkanMember] = []
        for row in rows:
            try:
                org_id = int(row["org"]["orgId"]) if isinstance(row.get("org"), dict) else int(row["orgId"])
                members.append(
                    VulkanMember(
                        clan_id=int(row["clanId"]),
                        org_id=org_id,
                        ime=str(row["ime"]).strip(),
                        priimek=str(row["priimek"]).strip(),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise MemberRegistryError("Member file has an unexpected shape.") from exc
        return cls(members)

    def match(self, name: str) -> VulkanMember | None:
        key = normalize_name(name)
        return self.by_name.get(key)

    def missing_or_ambiguous(self, name: str) -> bool:
        key = normalize_name(name)
        return key not in self.by_name

    def _keys_for(self, member: VulkanMember) -> tuple[str, ...]:
        surname_first = normalize_name(f"{member.priimek} {member.ime}")
        name_first = normalize_name(f"{member.ime} {member.priimek}")
        return (surname_first, name_first)
