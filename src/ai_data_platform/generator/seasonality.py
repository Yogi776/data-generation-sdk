"""Universal seasonality engine — pure math, no domain rules.

Every seasonal effect (Black Friday, monsoon, payday, flu season, recession)
reduces to the same generic primitives, composed multiplicatively:

    weight(t) = base * trend(t) * yearly(t) * monthly(t) * weekly(t)
                     * holiday(t) * Π windows_i(t)

This module holds ONLY math: numpy + datetime, never polars, so it is
unit-testable in isolation and portable to a future non-Python executor. The
polars wrapping lives in `samplers.py` / `engine.py`.

The factor config (`cfg`) is a plain JSON-serializable dict so it travels in the
Plan-IR verbatim. Two private range-reference keys are injected by the spec
layer: ``_start`` / ``_end`` (ISO dates) anchor the trend and bound holiday
resolution, so `multiplier_for` is self-contained given only (dates, cfg).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from ai_data_platform.core.exceptions import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

try:  # optional dependency: `pip install ai-data-platform[seasonality]`
    import holidays as _holidays_lib
except ImportError:  # pragma: no cover - exercised only when extra is absent
    _holidays_lib = None  # type: ignore[assignment]

_YEAR_DAYS = 365.25
_DOW_NAMES = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
_NORTH_SEASONS = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn",
}


# -- helpers -------------------------------------------------------------------
def _to_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _pydates(dates: Sequence[Any]) -> list[date]:
    return [_to_date(d) for d in dates]


def _range_dates(start: date, end: date) -> list[date]:
    n = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(max(n, 1))]


# -- sub-factors (each: derived date components -> multiplier array) -----------
def _trend(cfg: dict | None, days: list[date], ref: date) -> np.ndarray:
    n = len(days)
    if not cfg:
        return np.ones(n)
    kind = str(cfg.get("kind", "linear")).lower()
    g = float(cfg.get("annual_growth", cfg.get("rate", 0.0)))
    years = np.array([(d - ref).days / _YEAR_DAYS for d in days], dtype=float)
    if kind == "exponential":
        out = np.power(1.0 + g, years)
    elif kind == "logarithmic":
        out = 1.0 + g * np.log1p(np.clip(years, 0, None))
    else:  # linear
        out = 1.0 + g * years
    return np.clip(out, 0.01, None)


def _yearly(cfg: dict | None, days: list[date]) -> np.ndarray:
    n = len(days)
    if not cfg:
        return np.ones(n)
    out = np.ones(n)
    amp = float(cfg.get("amplitude", 0.0))
    if amp:
        phase = float(cfg.get("phase_days", 0.0))
        doy = np.array([d.timetuple().tm_yday for d in days], dtype=float)
        out = out * (1.0 + amp * np.sin(2.0 * math.pi * (doy + phase) / _YEAR_DAYS))
    for peak in cfg.get("peaks", []) or []:
        month = int(peak["month"])
        pday = int(peak.get("day", 15))
        strength = float(peak.get("strength", 1.5))
        width = max(float(peak.get("width_days", 3)), 0.5)
        # distance (days) to the nearest yearly occurrence of (month, day)
        dist = np.array([_nearest_recurring_dist(d, month, pday) for d in days], dtype=float)
        out = out * (1.0 + (strength - 1.0) * np.exp(-0.5 * (dist / width) ** 2))
    return np.clip(out, 0.0, None)


def _nearest_recurring_dist(d: date, month: int, day: int) -> float:
    best = 10_000.0
    for yr in (d.year - 1, d.year, d.year + 1):
        try:
            target = date(yr, month, day)
        except ValueError:  # e.g. Feb 29 on a non-leap year -> clamp to 28th
            target = date(yr, month, min(day, 28))
        best = min(best, abs((d - target).days))
    return best


def _monthly(cfg: dict | None, days: list[date]) -> np.ndarray:
    n = len(days)
    if not cfg:
        return np.ones(n)
    by_day = cfg.get("weights_by_day")
    if by_day:
        table = {int(k): float(v) for k, v in by_day.items()}
        return np.array([table.get(d.day, 1.0) for d in days], dtype=float)
    shape = str(cfg.get("shape", "uniform")).lower()
    strength = float(cfg.get("strength", 0.5))
    out = np.ones(n)
    for i, d in enumerate(days):
        dim = _days_in_month(d.year, d.month)
        frac = (d.day - 1) / max(dim - 1, 1)  # 0 at month start .. 1 at month end
        if shape == "month_end":
            out[i] = 1.0 + strength * frac
        elif shape == "month_start":
            out[i] = 1.0 + strength * (1.0 - frac)
    return out


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _weekly(cfg: dict | None, days: list[date]) -> np.ndarray:
    n = len(days)
    if not cfg:
        return np.ones(n)
    weights = np.ones(7)
    for name, mult in cfg.items():
        key = str(name).strip().lower()
        if key in _DOW_NAMES:
            weights[_DOW_NAMES[key]] = float(mult)
    dow = np.array([d.weekday() for d in days])
    return weights[dow]


def _holiday_factor(cfg: dict | None, days: list[date], start: date, end: date) -> np.ndarray:
    n = len(days)
    if not cfg:
        return np.ones(n)
    strength = float(cfg.get("strength", 1.5))
    window = int(cfg.get("window_days", 0))
    hdates = resolve_holiday_dates(cfg, start, end)
    if not hdates:
        return np.ones(n)
    out = np.ones(n)
    hsorted = sorted(hdates)
    for i, d in enumerate(days):
        dist = min(abs((d - h).days) for h in hsorted)
        if dist <= window:
            out[i] = max(out[i], strength)
    return out


def _windows_factor(events: list[dict] | None, days: list[date]) -> np.ndarray:
    n = len(days)
    if not events:
        return np.ones(n)
    out = np.ones(n)
    for ev in events:
        mult = float(ev.get("multiplier", 1.0))
        if ev.get("start") and ev.get("end"):
            lo, hi = _to_date(ev["start"]), _to_date(ev["end"])
        elif ev.get("date"):
            center = _to_date(ev["date"])
            w = int(ev.get("window_days", 0))
            lo, hi = center - timedelta(days=w), center + timedelta(days=w)
        else:
            continue
        for i, d in enumerate(days):
            if lo <= d <= hi:
                out[i] = out[i] * mult
    return out


def resolve_holiday_dates(cfg: dict, start: date, end: date) -> set[date]:
    """Holiday dates in [start, end] from an explicit list or a country calendar.

    An explicit ``dates:`` list always works. A ``country:`` code needs the
    optional `holidays` package; absent it, raise a typed ConfigError with a hint.
    """
    if cfg.get("dates"):
        return {_to_date(x) for x in cfg["dates"] if start <= _to_date(x) <= end}
    country = cfg.get("country")
    if not country:
        return set()
    if _holidays_lib is None:
        raise ConfigError(
            f"Seasonality holidays for country {country!r} need the `holidays` package.",
            hint="Install it with: pip install 'ai-data-platform[seasonality]' "
            "(or list explicit `dates:` in the spec instead).",
        )
    years = list(range(start.year, end.year + 1))
    subdiv = cfg.get("subdiv") or cfg.get("state")
    cal = _holidays_lib.country_holidays(str(country), years=years, subdiv=subdiv)
    return {d for d in cal if start <= d <= end}


def _compose(days: list[date], cfg: dict, ref: date, bound_start: date, bound_end: date) -> np.ndarray:
    """Raw (unnormalized) multiplicative weight per date. base defaults to 1.0."""
    base = float(cfg.get("base", 1.0))
    w = np.full(len(days), base, dtype=float)
    w *= _trend(cfg.get("trend"), days, ref)
    w *= _yearly(cfg.get("yearly"), days)
    w *= _monthly(cfg.get("monthly"), days)
    w *= _weekly(cfg.get("weekly"), days)
    w *= _holiday_factor(cfg.get("holidays"), days, bound_start, bound_end)
    w *= _windows_factor(cfg.get("events"), days)
    return np.clip(w, 0.0, None)


def _bounds(cfg: dict, start: date | None, end: date | None) -> tuple[date, date]:
    s = start if start is not None else _to_date(cfg.get("_start", "2024-01-01"))
    e = end if end is not None else _to_date(cfg.get("_end", "2026-01-01"))
    return s, e


# -- public API ----------------------------------------------------------------
def build_day_weights(start: date, end: date, cfg: dict) -> np.ndarray:
    """Normalized (sum=1) expected weight per day over [start, end] inclusive.

    Pure — the expected volume density used both for sampling and validation.
    Noise is deliberately excluded so the curve is a stable reference.
    """
    days = _range_dates(start, end)
    w = _compose(days, cfg, ref=start, bound_start=start, bound_end=end)
    total = float(w.sum())
    if total <= 0:  # degenerate config -> uniform
        return np.full(len(days), 1.0 / max(len(days), 1))
    return w / total


def build_hour_weights(cfg: dict) -> np.ndarray:
    """Normalized 24-length hour-of-day weights; uniform when no `daily` cfg."""
    daily = cfg.get("daily") or {}
    hours = daily.get("hour_weights")
    if not hours or len(hours) != 24:
        return np.full(24, 1.0 / 24.0)
    arr = np.clip(np.asarray(hours, dtype=float), 0.0, None)
    total = float(arr.sum())
    return arr / total if total > 0 else np.full(24, 1.0 / 24.0)


def multiplier_for(dates: Sequence[Any], cfg: dict) -> np.ndarray:
    """Pure per-date multiplicative factor (no noise, no normalization).

    Used to scale metric values by seasonality. Trend/holidays are anchored to
    the range injected as cfg['_start']/cfg['_end'].
    """
    days = _pydates(dates)
    if not days:
        return np.zeros(0)
    bs, be = _bounds(cfg, None, None)
    return _compose(days, cfg, ref=bs, bound_start=bs, bound_end=be)


def sample_seasonal_dates(
    rng: np.random.Generator,
    n: int,
    start: date,
    end: date,
    cfg: dict,
    with_time: bool,
) -> list[date | datetime]:
    """Draw n event timestamps weighted by the seasonal day curve.

    Volume seasonality: row count is unchanged, only *when* events land. Peaks
    emerge on aggregation. Deterministic given `rng`. Optional multiplicative
    `noise` perturbs the per-day weights (real effect on volume) without
    polluting the pure validation curve.
    """
    if n <= 0:
        return []
    weights = build_day_weights(start, end, cfg)
    noise = cfg.get("noise")
    if noise:
        sigma = float(noise.get("sigma", 0.0))
        if sigma > 0:
            kind = str(noise.get("kind", "lognormal")).lower()
            if kind == "normal":
                jitter = np.clip(1.0 + rng.normal(0.0, sigma, size=len(weights)), 0.0, None)
            else:  # lognormal (multiplicative, mean ~1)
                jitter = rng.lognormal(-(sigma**2) / 2.0, sigma, size=len(weights))
            weights = weights * jitter
            total = float(weights.sum())
            weights = weights / total if total > 0 else build_day_weights(start, end, cfg)
    day_idx = rng.choice(len(weights), size=n, p=weights)
    base_days = [start + timedelta(days=int(i)) for i in day_idx]
    if not with_time:
        return base_days
    hour_w = build_hour_weights(cfg)
    hours = rng.choice(24, size=n, p=hour_w)
    minutes = rng.integers(0, 60, size=n)
    seconds = rng.integers(0, 60, size=n)
    return [
        datetime(d.year, d.month, d.day, int(h), int(m), int(s))
        for d, h, m, s in zip(base_days, hours, minutes, seconds)
    ]


def calendar_features(
    dates: Sequence[Any],
    parts: list[str],
    *,
    fiscal_year_start_month: int = 1,
    hemisphere: str = "north",
    country: str | None = None,
    holidays: list[Any] | None = None,
) -> dict[str, list]:
    """Pure reference implementation for calendar attribute columns.

    day_of_week (Mon=1..Sun=7), is_weekend, week, month, quarter, year,
    fiscal_month/quarter/year, season, is_holiday, is_business_day.
    """
    days = _pydates(dates)
    out: dict[str, list] = {}
    fstart = max(1, min(12, int(fiscal_year_start_month)))

    hset: set[date] = set()
    if "is_holiday" in parts or "is_business_day" in parts:
        if holidays:
            hset = {_to_date(x) for x in holidays}
        elif country and _holidays_lib is not None and days:
            years = list(range(min(d.year for d in days), max(d.year for d in days) + 1))
            hset = set(_holidays_lib.country_holidays(str(country), years=years))

    for part in parts:
        if part == "day_of_week":
            out[part] = [d.isoweekday() for d in days]
        elif part == "is_weekend":
            out[part] = [d.weekday() >= 5 for d in days]
        elif part == "week":
            out[part] = [d.isocalendar().week for d in days]
        elif part == "month":
            out[part] = [d.month for d in days]
        elif part == "quarter":
            out[part] = [(d.month - 1) // 3 + 1 for d in days]
        elif part == "year":
            out[part] = [d.year for d in days]
        elif part == "fiscal_month":
            out[part] = [(d.month - fstart) % 12 + 1 for d in days]
        elif part == "fiscal_quarter":
            out[part] = [((d.month - fstart) % 12) // 3 + 1 for d in days]
        elif part == "fiscal_year":
            out[part] = [d.year if d.month >= fstart else d.year - 1 for d in days]
        elif part == "season":
            shift = 6 if str(hemisphere).lower() == "south" else 0
            out[part] = [_NORTH_SEASONS[(d.month - 1 + shift) % 12 + 1] for d in days]
        elif part == "is_holiday":
            out[part] = [d in hset for d in days]
        elif part == "is_business_day":
            out[part] = [d.weekday() < 5 and d not in hset for d in days]
        else:
            raise ConfigError(
                f"Unknown calendar part {part!r}.",
                hint="Valid: day_of_week, is_weekend, week, month, quarter, year, "
                "fiscal_month, fiscal_quarter, fiscal_year, season, is_holiday, "
                "is_business_day.",
            )
    return out


# calendar part -> catalog column dtype (used by the spec expander)
CALENDAR_PART_DTYPE: dict[str, str] = {
    "day_of_week": "int", "is_weekend": "bool", "week": "int", "month": "int",
    "quarter": "int", "year": "int", "fiscal_month": "int", "fiscal_quarter": "int",
    "fiscal_year": "int", "season": "string", "is_holiday": "bool",
    "is_business_day": "bool",
}
