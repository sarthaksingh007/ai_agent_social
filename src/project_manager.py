"""
Agent 4 — Project Manager (PM).  PRD §3.

Slices the monthly calendar skeleton into weekly workflow modules. This is done
deterministically (by ISO week) rather than with an LLM: it's pure structural
reshaping, so code is more reliable and instant — no model variance, no tokens.
"""
from collections import defaultdict
from datetime import date

from src.schemas import PostStructure, StrategySchema, WeeklyPlan


def _week_index(iso_date: str, base_week: int | None, cache: dict) -> int:
    """Map a YYYY-MM-DD string to a 1-based week number within the plan."""
    try:
        d = date.fromisoformat(iso_date)
        return d.isocalendar().week
    except Exception:  # noqa: BLE001
        return 1


def slice_into_weeks(strategy: StrategySchema) -> list[WeeklyPlan]:
    """Group the calendar skeleton into weekly plans, themed by the week's
    dominant content pillar."""
    buckets: dict[int, list[PostStructure]] = defaultdict(list)
    cache: dict = {}
    for post in strategy.one_month_calendar_skeleton:
        buckets[_week_index(post.date, None, cache)].append(post)

    weeks: list[WeeklyPlan] = []
    for i, iso_week in enumerate(sorted(buckets), start=1):
        posts = buckets[iso_week]
        # Theme = the most common pillar that week.
        pillar_counts: dict[str, int] = defaultdict(int)
        for p in posts:
            pillar_counts[p.pillar] += 1
        theme = max(pillar_counts, key=pillar_counts.get) if pillar_counts else "General"
        weeks.append(WeeklyPlan(week_number=i, theme=theme, posts=posts))
    return weeks
