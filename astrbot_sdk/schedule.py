"""Schedule-specific SDK types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScheduleContext:
    schedule_id: str
    plugin_id: str
    handler_id: str
    trigger_kind: str
    cron: str | None = None
    interval_seconds: int | None = None
    scheduled_at: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ScheduleContext:
        schedule = payload.get("schedule")
        if not isinstance(schedule, dict):
            raise ValueError("schedule payload is required")
        return cls(
            schedule_id=str(schedule.get("schedule_id", "")),
            plugin_id=str(schedule.get("plugin_id", "")),
            handler_id=str(schedule.get("handler_id", "")),
            trigger_kind=str(schedule.get("trigger_kind", "")),
            cron=(
                str(schedule["cron"]) if isinstance(schedule.get("cron"), str) else None
            ),
            interval_seconds=(
                int(schedule["interval_seconds"])
                if isinstance(schedule.get("interval_seconds"), int)
                else None
            ),
            scheduled_at=(
                str(schedule["scheduled_at"])
                if isinstance(schedule.get("scheduled_at"), str)
                else None
            ),
        )


__all__ = ["ScheduleContext"]
