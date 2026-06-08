from __future__ import annotations

import queue
import threading
import tkinter as tk
from calendar import month_name
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .api import WORK_TYPE_IDS, ReviewDecision, VulkanApiError, VulkanApiImporter
from .history import AppState, StateStore
from .members import MemberRegistry, MemberRegistryError
from .models import Activity, MemberMatch
from .transform import WorkbookError, activities_for_month, read_activities


class TransferApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ignis to Vulkan Transfer - API mode")
        self.geometry("980x720")
        self.minsize(900, 620)

        self.store = StateStore()
        self.state = self.store.load()
        self.activities: list[Activity] = []
        self.review_queue: queue.Queue[tuple[str, Activity, MemberMatch, threading.Event, dict[str, ReviewDecision]]] = queue.Queue()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.file_path_var = tk.StringVar(value="")
        self.url_var = tk.StringVar(value=self.state.config.vulkan_url)
        project_dir = Path(__file__).resolve().parents[1]
        private_members_path = project_dir / "vulkan_members.json"
        sample_members_path = project_dir / "sample_vulkan_members.json"
        default_members_path = private_members_path if private_members_path.exists() else sample_members_path
        self.members_path_var = tk.StringVar(
            value=self.state.config.members_path or (str(default_members_path) if default_members_path.exists() else "")
        )

        default_month = datetime.now().month - 1
        default_year = datetime.now().year
        if default_month == 0:
            default_month = 12
            default_year -= 1
        self.month_var = tk.IntVar(value=default_month)
        self.year_var = tk.IntVar(value=default_year)
        self.skip_completed_var = tk.BooleanVar(value=True)

        self._build_ui()
        self.after(200, self._poll_queues)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        file_frame = ttk.LabelFrame(root, text="Input")
        file_frame.pack(fill=tk.X)
        ttk.Label(file_frame, text="Ignis Excel file").grid(row=0, column=0, sticky=tk.W, padx=8, pady=8)
        ttk.Entry(file_frame, textvariable=self.file_path_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=8)
        ttk.Button(file_frame, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=8, pady=8)
        ttk.Label(file_frame, text="Vulkan members JSON").grid(row=1, column=0, sticky=tk.W, padx=8, pady=8)
        ttk.Entry(file_frame, textvariable=self.members_path_var).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=8)
        ttk.Button(file_frame, text="Browse", command=self._browse_members).grid(row=1, column=2, padx=8, pady=8)
        file_frame.columnconfigure(1, weight=1)

        settings = ttk.LabelFrame(root, text="Monthly transfer")
        settings.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(settings, text="Month").grid(row=0, column=0, sticky=tk.W, padx=8, pady=8)
        month_box = ttk.Combobox(
            settings,
            textvariable=self.month_var,
            values=list(range(1, 13)),
            width=8,
            state="readonly",
        )
        month_box.grid(row=0, column=1, sticky=tk.W, padx=8, pady=8)
        ttk.Label(settings, text="Year").grid(row=0, column=2, sticky=tk.W, padx=8, pady=8)
        ttk.Spinbox(settings, from_=2020, to=2100, textvariable=self.year_var, width=8).grid(
            row=0,
            column=3,
            sticky=tk.W,
            padx=8,
            pady=8,
        )
        ttk.Checkbutton(settings, text="Skip locally completed rows", variable=self.skip_completed_var).grid(
            row=0,
            column=4,
            sticky=tk.W,
            padx=8,
            pady=8,
        )

        ttk.Label(settings, text="Vulkan URL").grid(row=1, column=0, sticky=tk.W, padx=8, pady=8)
        ttk.Entry(settings, textvariable=self.url_var).grid(row=1, column=1, columnspan=4, sticky=tk.EW, padx=8, pady=8)
        settings.columnconfigure(4, weight=1)

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, pady=10)
        ttk.Button(actions, text="Preview month", command=self._preview).pack(side=tk.LEFT)
        ttk.Button(actions, text="Start transfer", command=self._start_transfer).pack(side=tk.LEFT, padx=(8, 0))

        columns = ("date", "title", "type", "duration", "hours", "members", "status")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=12)
        for column, text, width in (
            ("date", "Date", 110),
            ("title", "Title", 240),
            ("type", "Vulkan type", 170),
            ("duration", "Duration", 90),
            ("hours", "Hours", 70),
            ("members", "Members", 80),
            ("status", "Status", 170),
        ):
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, anchor=tk.W)
        self.tree.tag_configure("invalid", background="#ffd6d6")
        self.tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose Ignis export",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if path:
            self.file_path_var.set(path)

    def _browse_members(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose Vulkan members JSON",
            filetypes=[("JSON/text files", "*.json *.txt *.*"), ("All files", "*.*")],
        )
        if path:
            self.members_path_var.set(path)

    def _preview(self) -> bool:
        try:
            path = Path(self.file_path_var.get())
            if not path.exists():
                messagebox.showerror("Missing file", "Choose an Ignis Excel export first.")
                return False
            raw = read_activities(path)
            activities = activities_for_month(raw, self.year_var.get(), self.month_var.get())
            if self.skip_completed_var.get():
                activities = [activity for activity in activities if activity.history_key not in self.state.completed]
            self.activities = activities
            self._render_activities()
            self._log(f"Loaded {len(activities)} activities for {month_name[self.month_var.get()]} {self.year_var.get()}.")
            return True
        except (WorkbookError, OSError, ValueError) as exc:
            messagebox.showerror("Could not load Excel", str(exc))
            return False

    def _render_activities(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for activity in self.activities:
            status = "; ".join(activity.warnings) if activity.warnings else "Ready"
            tags = ("invalid",) if activity.vulkan_category not in WORK_TYPE_IDS else ()
            self.tree.insert(
                "",
                tk.END,
                iid=str(activity.row_number),
                values=(
                    activity.start.strftime("%d.%m.%Y"),
                    activity.title,
                    activity.vulkan_category,
                    self._duration_text(activity),
                    activity.hours_text,
                    len(activity.participants),
                    status,
                ),
                tags=tags,
            )

    def _start_transfer(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Transfer running", "A transfer is already running.")
            return
        if not self._preview():
            return
        if not self.activities:
            messagebox.showinfo("No activities", "There are no activities to transfer for this month.")
            return

        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Missing Vulkan URL", "Enter the Vulkan URL before starting.")
            return
        members_path = Path(self.members_path_var.get())
        if not members_path.exists():
            messagebox.showerror("Missing members", "Choose the Vulkan members JSON file before starting.")
            return
        if members_path.name == "sample_vulkan_members.json":
            messagebox.showerror(
                "Sample members selected",
                "The sample member file contains fake names and IDs. Choose your private vulkan_members.json file before starting.",
            )
            return
        self.state.config.vulkan_url = url
        self.state.config.members_path = str(members_path)
        self.store.save(self.state)

        self.worker = threading.Thread(target=self._run_worker, daemon=True)
        self.worker.start()

    def _run_worker(self) -> None:
        try:
            members = MemberRegistry.from_file(self.state.config.members_path)
            importer = VulkanApiImporter(
                vulkan_url=self.state.config.vulkan_url,
                profile_dir=self.store.browser_profile_dir,
                members=members,
                review_callback=self._request_review,
                log_callback=lambda message: self.log_queue.put(message),
                completed_callback=self._mark_completed,
            )
            importer.run_activities(self.activities)
        except (VulkanApiError, MemberRegistryError) as exc:
            self.log_queue.put(str(exc))
        except Exception as exc:
            self.log_queue.put(f"Transfer stopped: {exc}")

    def _request_review(self, stage: str, activity: Activity, match: MemberMatch) -> ReviewDecision:
        event = threading.Event()
        result: dict[str, ReviewDecision] = {"continue": False}
        self.review_queue.put((stage, activity, match, event, result))
        event.wait()
        return result["continue"]

    def _mark_completed(self, activity: Activity, match: MemberMatch) -> None:
        if match.missing:
            self.store.log_missing_members(self.state, activity, list(match.missing))
        self.store.mark_completed(self.state, activity)

    def _poll_queues(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(message)

        while True:
            try:
                stage, activity, match, event, result = self.review_queue.get_nowait()
            except queue.Empty:
                break
            result["continue"] = self._show_review(stage, activity, match)
            event.set()

        self.after(200, self._poll_queues)

    def _show_review(self, stage: str, activity: Activity, match: MemberMatch) -> ReviewDecision:
        dialog = tk.Toplevel(self)
        dialog.title("Review before saving")
        dialog.geometry("860x760")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        heading = "Review before creating" if stage == "api_review" else "Review before saving"
        ttk.Label(frame, text=heading, font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text=(
                f"{activity.start:%d.%m.%Y}  |  {activity.vulkan_category}  |  "
                f"{activity.title}  |  Duration: {self._duration_text(activity)}"
            ),
        ).pack(
            anchor=tk.W,
            pady=(4, 10),
        )

        edit_frame = ttk.LabelFrame(frame, text="Vulkan")
        edit_frame.pack(fill=tk.X, pady=(0, 10))

        title_var = tk.StringVar(value=activity.title)
        category_var = tk.StringVar(value=activity.vulkan_category if activity.vulkan_category in WORK_TYPE_IDS else "")
        ttk.Label(edit_frame, text="Title").grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        ttk.Entry(edit_frame, textvariable=title_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=6)
        ttk.Label(edit_frame, text="Category").grid(row=1, column=0, sticky=tk.W, padx=8, pady=6)
        ttk.Combobox(
            edit_frame,
            textvariable=category_var,
            values=list(WORK_TYPE_IDS.keys()),
            state="readonly",
        ).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)
        edit_frame.columnconfigure(1, weight=1)

        warning_var = tk.StringVar(value="")
        if activity.vulkan_category not in WORK_TYPE_IDS:
            warning_var.set("Unknown category: choose a valid Vulkan category before continuing.")
        warning_label = ttk.Label(edit_frame, textvariable=warning_var, foreground="#b00020")
        warning_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=8, pady=(0, 6))

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        desc_frame = ttk.LabelFrame(body, text="Ignis description")
        desc_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
        description = scrolledtext.ScrolledText(desc_frame, height=12, wrap=tk.WORD)
        description.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        description.insert(tk.END, activity.description or "(empty)")
        description.configure(state=tk.DISABLED)

        member_frame = ttk.LabelFrame(body, text=self._member_box_title(activity, match))
        member_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))
        member_canvas = tk.Canvas(member_frame, highlightthickness=0)
        member_scrollbar = ttk.Scrollbar(member_frame, orient=tk.VERTICAL, command=member_canvas.yview)
        member_list = ttk.Frame(member_canvas)
        member_list.bind(
            "<Configure>",
            lambda event: member_canvas.configure(scrollregion=member_canvas.bbox("all")),
        )
        member_canvas.create_window((0, 0), window=member_list, anchor=tk.NW)
        member_canvas.configure(yscrollcommand=member_scrollbar.set)
        member_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        member_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)

        matched_set = set(match.matched)
        missing_set = set(match.missing)
        member_vars: dict[str, tk.BooleanVar] = {}
        for row_index, member_name in enumerate(activity.participants):
            is_missing = member_name in missing_set
            var = tk.BooleanVar(value=member_name in matched_set)
            member_vars[member_name] = var
            checkbox = tk.Checkbutton(
                member_list,
                text=member_name,
                variable=var,
                anchor=tk.W,
                fg="#0057b8" if is_missing else "#111111",
                selectcolor="#d7e8ff" if is_missing else "#ffffff",
                activeforeground="#0057b8" if is_missing else "#111111",
                disabledforeground="#0057b8" if is_missing else "#777777",
                state=tk.DISABLED if is_missing else tk.NORMAL,
            )
            checkbox.grid(row=row_index, column=0, sticky=tk.W, padx=4, pady=2)

        lower = ttk.Frame(frame)
        lower.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)

        detected_frame = ttk.LabelFrame(lower, text="Detected members text")
        detected_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
        detected_text = scrolledtext.ScrolledText(detected_frame, height=7, wrap=tk.WORD)
        detected_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        detected_text.insert(tk.END, self._participant_text(activity))
        detected_text.configure(state=tk.DISABLED)

        warnings_frame = ttk.LabelFrame(lower, text="Warnings")
        warnings_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))
        warnings_text = scrolledtext.ScrolledText(warnings_frame, height=7, wrap=tk.WORD)
        warnings_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        warnings_text.insert(tk.END, self._warning_text(activity, match))
        warnings_text.configure(state=tk.DISABLED)

        result: dict[str, ReviewDecision] = {"continue": False}

        def choose_skip() -> None:
            result["continue"] = False
            dialog.destroy()

        def choose_continue() -> None:
            title = title_var.get().strip()
            category = category_var.get().strip()
            if not title:
                warning_var.set("Title cannot be empty.")
                return
            if category not in WORK_TYPE_IDS:
                warning_var.set("Choose a valid Vulkan category before continuing.")
                return
            selected_members = tuple(
                member_name
                for member_name, var in member_vars.items()
                if var.get() and member_name in matched_set
            )
            missing_members = tuple(
                member_name
                for member_name in activity.participants
                if member_name in missing_set
            )
            result["continue"] = replace(
                activity,
                title=title,
                vulkan_note=title,
                vulkan_category=category,
                participants=selected_members + missing_members,
                warnings=tuple(
                    warning
                    for warning in activity.warnings
                    if not warning.startswith("Unknown Ignis category")
                ),
            )
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(buttons, text="Continue", command=choose_continue).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Skip this activity", command=choose_skip).pack(side=tk.RIGHT, padx=(0, 8))

        dialog.wait_window()
        return result["continue"]

    def _member_box_title(self, activity: Activity, match: MemberMatch) -> str:
        return (
            f"Members: {len(activity.participants)} detected, "
            f"{len(match.matched)} matched, {len(match.missing)} not in Vulkan"
        )

    def _participant_text(self, activity: Activity) -> str:
        return "\n".join(f"- {name}" for name in activity.participants) or "(none found)"

    def _warning_text(self, activity: Activity, match: MemberMatch) -> str:
        lines: list[str] = []
        lines.extend(f"- {warning}" for warning in activity.warnings)
        lines.extend(f"- Not in Vulkan: {name}" for name in match.missing)
        return "\n".join(lines) or "(none)"

    def _duration_text(self, activity: Activity) -> str:
        minutes = int((activity.end - activity.start).total_seconds() // 60)
        if minutes <= 0:
            return "0 min"
        hours, remainder = divmod(minutes, 60)
        if hours and remainder:
            return f"{hours}h {remainder}min"
        if hours:
            return f"{hours}h"
        return f"{remainder}min"

    def _review_text(self, stage: str, activity: Activity, match: MemberMatch) -> str:
        participants = "\n".join(f"- {name}" for name in activity.participants) or "(none found)"
        missing = "\n".join(f"- {name}" for name in match.missing) or "(none)"
        matched = "\n".join(f"- {name}" for name in match.matched) or "(not checked yet)"
        warnings = "\n".join(f"- {warning}" for warning in activity.warnings) or "(none)"
        return (
            f"Vulkan date: {activity.start:%Y-%m-%d}T00:00:00\n"
            f"Vulkan type: {activity.vulkan_category}\n"
            f"Vulkan title: {activity.title}\n"
            f"Vulkan note: {activity.vulkan_note}\n"
            f"Member hours: {activity.hours_text}\n\n"
            f"Ignis description:\n{activity.description or '(empty)'}\n\n"
            f"Detected Ignis members:\n{participants}\n\n"
            f"Matched Vulkan members:\n{matched}\n\n"
            f"Missing/skipped members:\n{missing}\n\n"
            f"Warnings:\n{warnings}\n"
        )

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main() -> None:
    app = TransferApp()
    app.mainloop()
