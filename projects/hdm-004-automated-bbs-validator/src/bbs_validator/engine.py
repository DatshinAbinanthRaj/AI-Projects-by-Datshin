"""Validate one file or a whole folder and return one result per schedule."""
from __future__ import annotations

import os

from .loaders import ScheduleError, find_schedules, load_schedule
from .profile import Profile
from .report import ScheduleResult
from .rules import check_schedule, computed_weights, verdict


def validate_file(path: str, profile: Profile) -> ScheduleResult:
    try:
        schedule = load_schedule(path)
    except ScheduleError as exc:
        return ScheduleResult(os.path.basename(path), "UNREADABLE", problem=str(exc))
    findings = check_schedule(schedule, profile)
    findings.sort(key=lambda f: (f.line == 0, f.line))      # row findings first, in file order
    weights, _ = computed_weights(schedule, profile)
    return ScheduleResult(schedule.name, verdict(findings), len(schedule.rows), findings,
                          weights, list(schedule.notes))


def validate_path(path: str, profile: Profile) -> list:
    """Unreadable files do not stop the batch; they are reported as UNREADABLE."""
    return [validate_file(p, profile) for p in find_schedules(path)]


def exit_code(results: list, strict: bool = False) -> int:
    """0 = nothing blocks release, 1 = at least one schedule fails or cannot be read."""
    blocking = {"FAIL", "UNREADABLE"} | ({"REVIEW"} if strict else set())
    return 1 if any(r.verdict in blocking for r in results) else 0
