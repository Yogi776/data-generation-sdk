"""Sampler registry: column name/type/profile -> value sampler.

No domain is hardcoded. Selection is driven by (a) profiled distributions when
available, (b) name-pattern heuristics, (c) type fallbacks — in that order.
Every sampler is deterministic given its RNG.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

Sampler = Callable[[np.random.Generator, int], pl.Series]

# -- wordlists (generic building blocks, not domain templates) -----------------
FIRST_NAMES = [
    "Aarav",
    "Aditi",
    "Alex",
    "Amara",
    "Ana",
    "Arjun",
    "Ava",
    "Carlos",
    "Chen",
    "Diego",
    "Elena",
    "Emma",
    "Fatima",
    "Grace",
    "Hiro",
    "Ines",
    "Ivan",
    "James",
    "Julia",
    "Kai",
    "Lena",
    "Liam",
    "Lucia",
    "Marcus",
    "Maria",
    "Mei",
    "Mohammed",
    "Nina",
    "Noah",
    "Olivia",
    "Omar",
    "Priya",
    "Rahul",
    "Rosa",
    "Sam",
    "Sara",
    "Sofia",
    "Tariq",
    "Wei",
    "Zoe",
]
LAST_NAMES = [
    "Ahmed",
    "Andersson",
    "Brown",
    "Chen",
    "Costa",
    "Das",
    "Fernandez",
    "Garcia",
    "Gupta",
    "Hansen",
    "Ivanov",
    "Johnson",
    "Khan",
    "Kim",
    "Kowalski",
    "Kumar",
    "Lee",
    "Lopez",
    "Martin",
    "Mueller",
    "Nguyen",
    "Okafor",
    "Patel",
    "Rossi",
    "Santos",
    "Sato",
    "Schmidt",
    "Silva",
    "Singh",
    "Smith",
    "Suzuki",
    "Tanaka",
    "Torres",
    "Wang",
    "Williams",
    "Yamamoto",
]
CITIES = [
    "Amsterdam",
    "Austin",
    "Bangalore",
    "Berlin",
    "Boston",
    "Chicago",
    "Dubai",
    "Dublin",
    "Jakarta",
    "Lagos",
    "Lima",
    "London",
    "Madrid",
    "Melbourne",
    "Mexico City",
    "Mumbai",
    "Nairobi",
    "New York",
    "Osaka",
    "Paris",
    "Pune",
    "San Francisco",
    "Sao Paulo",
    "Seattle",
    "Seoul",
    "Singapore",
    "Sydney",
    "Tokyo",
    "Toronto",
    "Warsaw",
]
COUNTRIES = [
    "Australia",
    "Brazil",
    "Canada",
    "China",
    "France",
    "Germany",
    "India",
    "Indonesia",
    "Italy",
    "Japan",
    "Kenya",
    "Mexico",
    "Netherlands",
    "Nigeria",
    "Poland",
    "Singapore",
    "South Korea",
    "Spain",
    "UAE",
    "UK",
    "USA",
]
STREETS = [
    "Main St",
    "Oak Ave",
    "Park Rd",
    "Maple Dr",
    "Cedar Ln",
    "Lake View",
    "Hill St",
    "River Rd",
    "Station Rd",
    "Market St",
]
WORDS = [
    "alpha",
    "apex",
    "atlas",
    "aurora",
    "beacon",
    "bolt",
    "cedar",
    "cipher",
    "cobalt",
    "compass",
    "delta",
    "ember",
    "flux",
    "harbor",
    "ion",
    "juniper",
    "karma",
    "lumen",
    "matrix",
    "nimbus",
    "onyx",
    "orbit",
    "pixel",
    "quartz",
    "raven",
    "sierra",
    "terra",
    "vertex",
    "willow",
    "zephyr",
]

_EMAIL_DOMAINS = ["example.com", "example.org", "example.net", "mail.example.com"]


@dataclass
class SamplerSpec:
    """Plan-IR column sampler: name + params, executable by any conformant engine."""

    sampler: str
    params: dict[str, Any] = field(default_factory=dict)


# -- individual samplers -------------------------------------------------------
def _seq_int(start: int = 1) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        return pl.Series(np.arange(start, start + n, dtype=np.int64))

    return f


def _uuid_like() -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        raw = rng.integers(0, 16, size=(n, 32))
        hexd = np.array(list("0123456789abcdef"))
        strs = ["".join(row) for row in hexd[raw]]
        return pl.Series([f"{s[:8]}-{s[8:12]}-4{s[13:16]}-a{s[17:20]}-{s[20:32]}" for s in strs])

    return f


def _choice(values: list[Any], weights: list[float] | None = None) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        p = None
        if weights:
            arr = np.asarray(weights, dtype=float)
            p = arr / arr.sum()
        idx = rng.choice(len(values), size=n, p=p)
        return pl.Series([values[i] for i in idx])

    return f


def _full_name() -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        fi = rng.choice(len(FIRST_NAMES), size=n)
        li = rng.choice(len(LAST_NAMES), size=n)
        return pl.Series([f"{FIRST_NAMES[a]} {LAST_NAMES[b]}" for a, b in zip(fi, li)])

    return f


def _email() -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        fi = rng.choice(len(FIRST_NAMES), size=n)
        li = rng.choice(len(LAST_NAMES), size=n)
        num = rng.integers(1, 999, size=n)
        dom = rng.choice(len(_EMAIL_DOMAINS), size=n)
        return pl.Series(
            [
                f"{FIRST_NAMES[a].lower()}.{LAST_NAMES[b].lower()}{c}@{_EMAIL_DOMAINS[d]}"
                for a, b, c, d in zip(fi, li, num, dom)
            ]
        )

    return f


def _phone() -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        a = rng.integers(200, 999, size=n)
        b = rng.integers(200, 999, size=n)
        c = rng.integers(1000, 9999, size=n)
        return pl.Series([f"+1-{x}-{y}-{z}" for x, y, z in zip(a, b, c)])

    return f


def _address() -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        num = rng.integers(1, 9999, size=n)
        st = rng.choice(len(STREETS), size=n)
        ci = rng.choice(len(CITIES), size=n)
        return pl.Series([f"{a} {STREETS[b]}, {CITIES[c]}" for a, b, c in zip(num, st, ci)])

    return f


def _lognormal(mean: float, sigma: float = 0.6, decimals: int = 2) -> Sampler:
    mu = np.log(max(mean, 0.01)) - sigma**2 / 2

    def f(rng: np.random.Generator, n: int) -> pl.Series:
        return pl.Series(np.round(rng.lognormal(mu, sigma, size=n), decimals))

    return f


def _normal(mean: float, std: float, lo: float | None, hi: float | None, as_int: bool) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        vals = rng.normal(mean, max(std, 1e-9), size=n)
        if lo is not None or hi is not None:
            vals = np.clip(vals, lo, hi)
        if as_int:
            return pl.Series(np.round(vals).astype(np.int64))
        return pl.Series(np.round(vals, 4))

    return f


def _uniform_int(lo: int, hi: int) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        return pl.Series(rng.integers(lo, hi + 1, size=n, dtype=np.int64))

    return f


def _poisson(lam: float, min_value: int = 0) -> Sampler:
    """Poisson matched to the profiled mean (shifted only by an explicit floor)."""
    lam_adj = max(lam - min_value, 0.1)

    def f(rng: np.random.Generator, n: int) -> pl.Series:
        return pl.Series((rng.poisson(lam_adj, size=n) + min_value).astype(np.int64))

    return f


def _bool(p_true: float = 0.5) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        return pl.Series(rng.random(size=n) < p_true)

    return f


def _dates(start: date, end: date, with_time: bool) -> Sampler:
    span = max((end - start).days, 1)

    def f(rng: np.random.Generator, n: int) -> pl.Series:
        offsets = rng.integers(0, span + 1, size=n)
        if with_time:
            secs = rng.integers(0, 86_400, size=n)
            vals = [
                datetime.combine(start + timedelta(days=int(d)), datetime.min.time())
                + timedelta(seconds=int(s))
                for d, s in zip(offsets, secs)
            ]
            return pl.Series(vals)
        return pl.Series([start + timedelta(days=int(d)) for d in offsets])

    return f


def _template(pattern: str) -> Sampler:
    """Format template: '#' -> digit, '?' -> uppercase letter, else literal.

    Examples: "ORD-2025-######", "TRK##########", "+91-9#########", "??-####".
    """
    digit_positions = [i for i, ch in enumerate(pattern) if ch == "#"]
    letter_positions = [i for i, ch in enumerate(pattern) if ch == "?"]
    letters = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    base = list(pattern)

    def f(rng: np.random.Generator, n: int) -> pl.Series:
        digits = rng.integers(0, 10, size=(n, max(len(digit_positions), 1)))
        lets = rng.integers(0, 26, size=(n, max(len(letter_positions), 1)))
        out = []
        for row in range(n):
            chars = base.copy()
            for j, pos in enumerate(digit_positions):
                chars[pos] = str(digits[row, j])
            for j, pos in enumerate(letter_positions):
                chars[pos] = letters[lets[row, j]]
            out.append("".join(chars))
        return pl.Series(out)

    return f


def _words(k: int = 2) -> Sampler:
    def f(rng: np.random.Generator, n: int) -> pl.Series:
        idx = rng.choice(len(WORDS), size=(n, k))
        return pl.Series([" ".join(WORDS[i] for i in row) for row in idx])

    return f


# -- Plan-IR executor: spec name -> factory ------------------------------------
def build_sampler(spec: SamplerSpec) -> Sampler:
    p = spec.params
    match spec.sampler:
        case "sequence":
            return _seq_int(int(p.get("start", 1)))
        case "uuid":
            return _uuid_like()
        case "choice":
            return _choice(p["values"], p.get("weights"))
        case "full_name":
            return _full_name()
        case "email":
            return _email()
        case "phone":
            return _phone()
        case "address":
            return _address()
        case "city":
            return _choice(CITIES)
        case "country":
            return _choice(COUNTRIES)
        case "lognormal":
            return _lognormal(float(p.get("mean", 100.0)), float(p.get("sigma", 0.6)))
        case "normal":
            return _normal(
                float(p.get("mean", 0.0)),
                float(p.get("std", 1.0)),
                p.get("min"),
                p.get("max"),
                bool(p.get("as_int", False)),
            )
        case "uniform_int":
            return _uniform_int(int(p.get("min", 1)), int(p.get("max", 1000)))
        case "poisson":
            return _poisson(float(p.get("lam", 3.0)), int(p.get("min", 0)))
        case "bool":
            return _bool(float(p.get("p_true", 0.5)))
        case "date" | "datetime":
            start = date.fromisoformat(p.get("start", "2024-01-01"))
            end = date.fromisoformat(p.get("end", "2026-01-01"))
            return _dates(start, end, spec.sampler == "datetime")
        case "template":
            return _template(str(p.get("pattern", "########")))
        case "words":
            return _words(int(p.get("k", 2)))
        case _:
            return _words(2)


def _lognormal_sigma(mean: float, std: float | None) -> float:
    """Moment-match lognormal sigma from profiled mean/std: σ² = ln(1 + (s/m)²)."""
    if not std or mean <= 0:
        return 0.6
    cv2 = (std / mean) ** 2
    return float(np.clip(np.sqrt(np.log1p(cv2)), 0.1, 2.5))


# -- inference: (column meta, profile) -> SamplerSpec ---------------------------
_NAME_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)e?[-_]?mail"), "email"),
    (re.compile(r"(?i)phone|mobile|cell"), "phone"),
    (
        re.compile(r"(?i)(^|_)((first|last|full|customer|patient|user|contact)_?)?name$"),
        "full_name",
    ),
    (re.compile(r"(?i)address|street"), "address"),
    (re.compile(r"(?i)(^|_)city$"), "city"),
    (re.compile(r"(?i)(^|_)country$"), "country"),
    (re.compile(r"(?i)price|amount|total|cost|salary|revenue|balance|fee"), "lognormal"),
    (re.compile(r"(?i)qty|quantity|units|count$"), "poisson"),
    (re.compile(r"(?i)^(is|has)_|_flag$|active$"), "bool"),
    (re.compile(r"(?i)uuid|guid"), "uuid"),
]


def infer_sampler(
    column: dict[str, Any],
    profile: dict[str, Any] | None,
    *,
    is_pk: bool,
) -> SamplerSpec:
    """Choose a sampler for a catalog column dict (+ optional profiled stats)."""
    name = column["name"]
    dtype = column["type"]

    if is_pk and dtype == "int":
        return SamplerSpec("sequence")
    if is_pk:
        return SamplerSpec("uuid")

    # 0) declared format template (spec `format:`) wins for strings
    if profile and profile.get("format") and dtype == "string":
        return SamplerSpec("template", {"pattern": str(profile["format"])})

    # 1) profiled categorical distribution wins
    if profile:
        distinct = profile.get("distinct", 0)
        top = profile.get("top_values") or []
        count = profile.get("count", 0)
        # strings/bools: up to 50 categories; ints: low-cardinality codes
        # (ratings, tiers) with the full domain captured in top_values
        is_categorical = (dtype in ("string", "bool") and 0 < distinct <= 50) or (
            dtype == "int" and 0 < distinct <= 20 and len(top) >= distinct
        )
        if top and count > 0 and is_categorical:
            values: list[Any] = [t["value"] for t in top]
            if dtype == "int":
                try:
                    values = [int(v) for v in values]
                except (TypeError, ValueError):
                    values = [t["value"] for t in top]
            return SamplerSpec(
                "choice",
                {"values": values, "weights": [t["count"] for t in top]},
            )

    # 2) name-pattern heuristics
    for pattern, sampler in _NAME_RULES:
        if pattern.search(name):
            if sampler == "lognormal":
                mean = float((profile or {}).get("mean") or 100.0)
                return SamplerSpec(
                    "lognormal",
                    {"mean": mean, "sigma": _lognormal_sigma(mean, (profile or {}).get("std"))},
                )
            if sampler == "poisson":
                mean = (profile or {}).get("mean") or 3.0
                floor = int((profile or {}).get("min") or 0)
                return SamplerSpec("poisson", {"lam": float(mean), "min": floor})
            return SamplerSpec(sampler)

    # 3) type + profile fallbacks
    if dtype in ("date", "datetime"):
        params: dict[str, Any] = {}
        if profile and profile.get("min") and profile.get("max"):
            params = {"start": str(profile["min"])[:10], "end": str(profile["max"])[:10]}
        return SamplerSpec(dtype, params)
    if dtype == "bool":
        return SamplerSpec("bool")
    if dtype == "int":
        if profile and profile.get("mean") is not None and profile.get("std"):
            return SamplerSpec(
                "normal",
                {
                    "mean": profile["mean"],
                    "std": profile["std"],
                    "min": profile.get("min"),
                    "max": profile.get("max"),
                    "as_int": True,
                },
            )
        lo = int((profile or {}).get("min") or 1)
        hi = int((profile or {}).get("max") or max(lo + 1, 1000))
        return SamplerSpec("uniform_int", {"min": lo, "max": hi})
    if dtype == "float":
        if profile and profile.get("mean") is not None:
            return SamplerSpec(
                "normal",
                {
                    "mean": profile["mean"],
                    "std": profile.get("std") or 1.0,
                    "min": profile.get("min"),
                    "max": profile.get("max"),
                    "as_int": False,
                },
            )
        return SamplerSpec("lognormal", {"mean": 100.0, "sigma": 0.6})
    return SamplerSpec("words", {"k": 2})
