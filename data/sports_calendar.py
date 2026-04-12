from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


@dataclass(frozen=True)
class SportsCalendarWindowDefinition:
    slug: str
    title: str
    sport: str
    window_type: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    content_bucket: str
    template_key: str
    default_platforms: tuple[str, ...]
    summary: str
    stage_angle: str


MACRO_SPORTS_CALENDAR: list[SportsCalendarWindowDefinition] = [
    SportsCalendarWindowDefinition(
        slug="baseball-transfer-portal-open",
        title="Baseball Transfer Portal Window",
        sport="baseball",
        window_type="transfer_portal",
        start_month=5,
        start_day=1,
        end_month=7,
        end_day=31,
        content_bucket="portal_window",
        template_key="portal_open",
        default_platforms=("x", "linkedin"),
        summary="Open the portal window with pressure-performance context.",
        stage_angle="Transfer portal content should be urgent, proof-led, and specific to the decision risk.",
    ),
    SportsCalendarWindowDefinition(
        slug="football-transfer-portal-open",
        title="Football Transfer Portal Window",
        sport="football",
        window_type="transfer_portal",
        start_month=4,
        start_day=1,
        end_month=5,
        end_day=31,
        content_bucket="portal_window",
        template_key="portal_open",
        default_platforms=("x", "linkedin"),
        summary="Use the football portal window to frame decision pressure and roster consequences.",
        stage_angle="Tie the message to roster decisions, pressure, and the cost of guessing.",
    ),
    SportsCalendarWindowDefinition(
        slug="womens-summer-signing-window",
        title="Signing Day Window",
        sport="multi-sport",
        window_type="signing_day",
        start_month=4,
        start_day=1,
        end_month=4,
        end_day=30,
        content_bucket="commitment",
        template_key="signing_day",
        default_platforms=("linkedin", "instagram"),
        summary="Celebrate signings and commitment moments with proof-first framing.",
        stage_angle="Make the athlete feel seen, not marketed to.",
    ),
    SportsCalendarWindowDefinition(
        slug="college-world-series-window",
        title="College World Series Window",
        sport="baseball",
        window_type="championship_window",
        start_month=6,
        start_day=1,
        end_month=6,
        end_day=30,
        content_bucket="championship_window",
        template_key="championship_push",
        default_platforms=("x", "linkedin", "instagram"),
        summary="Spotlight performance under pressure when the sport is most visible.",
        stage_angle="Frame the moment as a pressure-performance story, not a generic cheer post.",
    ),
    SportsCalendarWindowDefinition(
        slug="womens-college-world-series-window",
        title="WCWS Window",
        sport="softball",
        window_type="championship_window",
        start_month=5,
        start_day=1,
        end_month=6,
        end_day=30,
        content_bucket="championship_window",
        template_key="championship_push",
        default_platforms=("x", "linkedin", "instagram"),
        summary="Spotlight the women's college world series window with proof-led commentary.",
        stage_angle="Anchor the message in visible stakes and not generic sports hype.",
    ),
    SportsCalendarWindowDefinition(
        slug="alliance-testing-window",
        title="Alliance Testing Window",
        sport="multi-sport",
        window_type="partner_testing",
        start_month=7,
        start_day=1,
        end_month=8,
        end_day=31,
        content_bucket="partner_volume",
        template_key="assessment_milestone",
        default_platforms=("x", "linkedin", "instagram"),
        summary="Use the testing window for volume milestones, registration pushes, and proof content.",
        stage_angle="Translate raw assessment volume into credibility and action.",
    ),
    SportsCalendarWindowDefinition(
        slug="fss-regional-circuit",
        title="FSS Regional Circuit",
        sport="multi-sport",
        window_type="partner_series",
        start_month=1,
        start_day=1,
        end_month=12,
        end_day=31,
        content_bucket="partner_series",
        template_key="partner_series",
        default_platforms=("x", "linkedin"),
        summary="Keep rolling partner-series content ready for the regional circuit.",
        stage_angle="Maintain a steady proof cadence rather than one-off announcements.",
    ),
]


def _date_for(year: int, month: int, day: int) -> date:
    return date(year, month, day)


def build_macro_calendar(year: int | None = None) -> list[dict[str, object]]:
    year = year or date.today().year
    return [
        {
            "slug": window.slug,
            "title": window.title,
            "sport": window.sport,
            "window_type": window.window_type,
            "start_date": _date_for(year, window.start_month, window.start_day).isoformat(),
            "end_date": _date_for(year, window.end_month, window.end_day).isoformat(),
            "content_bucket": window.content_bucket,
            "template_key": window.template_key,
            "default_platforms": list(window.default_platforms),
            "summary": window.summary,
            "stage_angle": window.stage_angle,
        }
        for window in MACRO_SPORTS_CALENDAR
    ]


def iter_calendar_windows() -> Iterable[SportsCalendarWindowDefinition]:
    yield from MACRO_SPORTS_CALENDAR


def get_calendar_window(slug: str) -> SportsCalendarWindowDefinition | None:
    return next((window for window in MACRO_SPORTS_CALENDAR if window.slug == slug), None)


def rolling_calendar_days(days: int = 28, *, anchor: date | None = None) -> list[dict[str, object]]:
    anchor = anchor or date.today()
    windows = build_macro_calendar(anchor.year) + build_macro_calendar(anchor.year + 1)
    results: list[dict[str, object]] = []
    for offset in range(days):
        day = anchor + timedelta(days=offset)
        matching = [
            window
            for window in windows
            if window["start_date"] <= day.isoformat() <= window["end_date"]
        ]
        results.append(
            {
                "date": day.isoformat(),
                "weekday": day.strftime("%a"),
                "label": day.strftime("%b %d"),
                "is_today": offset == 0,
                "windows": matching,
            }
        )
    return results
