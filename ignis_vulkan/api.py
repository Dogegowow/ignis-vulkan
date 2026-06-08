from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .members import MemberRegistry
from .models import Activity, MemberMatch


ReviewDecision = bool | Activity
ReviewCallback = Callable[[str, Activity, MemberMatch], ReviewDecision]
LogCallback = Callable[[str], None]
CompletedCallback = Callable[[Activity, MemberMatch], None]

WORK_TYPE_IDS = {
    "Dežurstva": 2,
    "Požarna straža": 3,
    "Vaje": 4,
    "Tekmovanja ne razpisana v Vulkanu": 5,
    "Usposabljanje/izobraževanje": 6,
    "Pregled/servisiranje opreme": 7,
    "Urejanje okolice": 8,
    "Delo v domu": 9,
    "Pregledi hidrantnega omrežja": 10,
    "Prevozi vode": 11,
    "Drugo": 12,
    "Seja/sestanek": 13,
    "Organizacija tekmovanja ne razpisanega v Vulkanu": 14,
    "Sojenje na tekmovanju ne razpisanem v Vulkanu": 15,
    "Mladinska tekmovanja": 16,
    "Gasilske prireditve": 17,
    "Gasilska žalovanja": 18,
    "Posvet / seminar": 19,
    "Posvet / seminar - GD": 85,
    "Intervencije - ostala oprema": 87,
}


class VulkanApiError(RuntimeError):
    pass


class VulkanApiImporter:
    def __init__(
        self,
        vulkan_url: str,
        profile_dir: Path,
        members: MemberRegistry,
        review_callback: ReviewCallback,
        log_callback: LogCallback,
        completed_callback: CompletedCallback | None = None,
    ):
        self.vulkan_url = vulkan_url
        self.profile_dir = profile_dir
        self.members = members
        self.review_callback = review_callback
        self.log = log_callback
        self.completed_callback = completed_callback
        self.origin = self._origin(vulkan_url)

    def run_activities(self, activities: list[Activity]) -> None:
        os.environ.setdefault(
            "PLAYWRIGHT_BROWSERS_PATH",
            str(Path(__file__).resolve().parents[1] / ".ms-playwright"),
        )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise VulkanApiError("Playwright is not installed. Run the setup from README.md first.") from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                viewport={"width": 1100, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(self.vulkan_url)
            self._wait_for_login(page)

            for index, activity in enumerate(activities, start=1):
                self.log(f"Processing {index}/{len(activities)}: {activity.title}")
                match = self._match_members(activity)
                decision = self.review_callback("api_review", activity, match)
                if not decision:
                    self.log(f"Skipped: {activity.title}")
                    continue
                if isinstance(decision, Activity):
                    activity = decision
                    match = self._match_members(activity)

                delo_id = self._create_activity(context, activity)
                self.log(f"Created activity {delo_id}: {activity.title}")
                for name in match.matched:
                    member = self.members.match(name)
                    if member is None:
                        continue
                    self._add_member(context, delo_id, activity, member.clan_id, member.org_id)
                    self.log(f"Added member: {member.display_name}")

                if self.completed_callback:
                    self.completed_callback(activity, match)
                self.log(f"Finished: {activity.title}")

            context.close()

    def _match_members(self, activity: Activity) -> MemberMatch:
        matched: list[str] = []
        missing: list[str] = []
        for name in activity.participants:
            if self.members.match(name):
                matched.append(name)
            else:
                missing.append(name)
        return MemberMatch(matched=tuple(matched), missing=tuple(missing))

    def _create_activity(self, context, activity: Activity) -> int:
        work_type_id = WORK_TYPE_IDS.get(activity.vulkan_category)
        if work_type_id is None:
            raise VulkanApiError(f"Unknown Vulkan work type: {activity.vulkan_category}")

        payload = {
            "datum": f"{activity.start:%Y-%m-%d}T00:00:00",
            "deloVrstaId": work_type_id,
            "naziv": activity.title,
            "opomba": activity.vulkan_note,
        }
        response = context.request.post(
            f"{self.origin}/vulkan/proxy/Org/Delo",
            data=payload,
            headers=self._headers("/vulkan/org/delo/new"),
        )
        return self._response_value(response, "create activity")

    def _add_member(self, context, delo_id: int, activity: Activity, clan_id: int, org_id: int) -> int:
        payload = {
            "clanId": clan_id,
            "orgId": org_id,
            "ur": activity.hours_value,
            "opomba": activity.vulkan_note,
        }
        response = context.request.post(
            f"{self.origin}/vulkan/proxy/Org/Delo/{delo_id}/Clan",
            data=payload,
            headers=self._headers(f"/vulkan/org/delo/{delo_id}"),
        )
        return self._response_value(response, "add member")

    def _response_value(self, response, action: str) -> int:
        if not response.ok:
            raise VulkanApiError(f"Vulkan failed to {action}: HTTP {response.status} {response.text()}")
        data = response.json()
        if data.get("statusCode") != 200:
            raise VulkanApiError(f"Vulkan failed to {action}: {data}")
        return int(data["value"])

    def _wait_for_login(self, page) -> None:
        try:
            page.get_by_text("VULKAN").first.wait_for(timeout=120000)
        except Exception:
            self.log("Log into Vulkan in the browser window, then the importer will continue.")
            page.get_by_text("VULKAN").first.wait_for(timeout=300000)

    def _headers(self, referer_path: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/*+json",
            "x-requested-with": "XMLHttpRequest",
            "Origin": self.origin,
            "Referer": f"{self.origin}{referer_path}",
        }

    def _origin(self, url: str) -> str:
        parsed = urlsplit(url.strip())
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
