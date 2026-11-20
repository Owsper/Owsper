#!/usr/bin/env python3
"""Generate assets/activity.svg from public GitHub data.

Sources, in order of preference:
  1. GitHub GraphQL API (uses GITHUB_TOKEN when present).
  2. The public contribution calendar HTML fragment (no token required).
  3. Existing assets/activity.svg (left untouched on total failure).

Only the Python standard library is used, so the workflow needs no install step.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = "Owsper"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO_ROOT, "assets", "activity.svg")

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Courier New', monospace"
SERIF = "Georgia, 'Times New Roman', serif"


def log(message: str) -> None:
    print(message, file=sys.stderr)


def request(url: str, token: str | None = None, payload: dict | None = None) -> str:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-assets",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_contributions_graphql(token: str) -> dict[str, int]:
    today = date.today()
    start = today - timedelta(days=364)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    variables = {
        "login": USER,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    }
    body = json.loads(request("https://api.github.com/graphql", token, {"query": query, "variables": variables}))
    if body.get("errors"):
        raise RuntimeError(f"GraphQL returned errors: {body['errors']}")
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {
        day["date"]: int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }


def fetch_contributions_public() -> dict[str, int]:
    html = request(f"https://github.com/users/{USER}/contributions", None)
    cells = {}
    for match in re.finditer(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-[^"]+)"', html
    ):
        cells[match.group(2)] = match.group(1)
    counts: dict[str, int] = {}
    for tooltip in re.finditer(
        r'<tool-tip[^>]*for="([^"]+)"[^>]*>([0-9,]+) contributions? on ([^<]+)</tool-tip>', html
    ):
        day = cells.get(tooltip.group(1))
        if day:
            counts[day] = int(tooltip.group(2).replace(",", ""))
    # Days without a tooltip are zero-contribution days.
    for day in cells.values():
        counts.setdefault(day, 0)
    if not counts:
        raise RuntimeError("Could not parse the public contribution calendar.")
    return counts


def fetch_repositories(token: str | None) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        chunk = json.loads(
            request(
                f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&type=owner&sort=pushed",
                token,
            )
        )
        if not isinstance(chunk, list):
            raise RuntimeError(f"Unexpected repository response: {chunk}")
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return repos


def load_data(token: str | None) -> tuple[dict[str, int], list[dict]]:
    contributions: dict[str, int] | None = None
    if token:
        try:
            contributions = fetch_contributions_graphql(token)
            log("Contributions: GraphQL API")
        except Exception as exc:  # noqa: BLE001 - fall back deliberately
            log(f"GraphQL contributions unavailable ({exc}); trying public calendar.")
    if not contributions:
        try:
            contributions = fetch_contributions_public()
            log("Contributions: public calendar")
        except Exception as exc:  # noqa: BLE001
            log(f"Public contribution calendar unavailable: {exc}")
            contributions = None
    repos = fetch_repositories(token)
    if contributions is None:
        raise RuntimeError("No contribution data available.")
    return contributions, repos


def weekly_series(contributions: dict[str, int]) -> tuple[list[tuple[date, int]], date, date]:
    """Group daily counts into Sunday-starting weeks."""
    days = sorted(date.fromisoformat(day) for day in contributions)
    first, last = days[0], days[-1]
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)  # Sunday
    weeks = ((last - grid_start).days // 7) + 1
    totals: list[tuple[date, int]] = []
    for week in range(weeks):
        week_start = grid_start + timedelta(days=week * 7)
        total = sum(
            contributions.get((week_start + timedelta(days=offset)).isoformat(), 0)
            for offset in range(7)
        )
        totals.append((week_start, total))
    return totals, first, last


def monthly_series(contributions: dict[str, int]) -> list[tuple[date, int]]:
    """Group daily counts by month, starting at the first active month."""
    totals: dict[tuple[int, int], int] = {}
    for day_text, count in contributions.items():
        day = date.fromisoformat(day_text)
        key = (day.year, day.month)
        totals[key] = totals.get(key, 0) + count
    keys = sorted(totals)
    active = [key for key in keys if totals[key] > 0]
    if active:
        keys = [key for key in keys if key >= active[0]]
    return [(date(year, month, 1), totals[(year, month)]) for year, month in keys]


def curve_commands(points: list[tuple[float, float]], top_y: float, base_y: float) -> str:
    """Catmull-Rom curve through the points, clamped to the chart area."""
    if len(points) < 2:
        return ""
    commands: list[str] = []
    for index in range(len(points) - 1):
        p0 = points[max(index - 1, 0)]
        p1 = points[index]
        p2 = points[index + 1]
        p3 = points[min(index + 2, len(points) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        c1 = (c1[0], min(base_y, max(top_y, c1[1])))
        c2 = (c2[0], min(base_y, max(top_y, c2[1])))
        commands.append(
            f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        )
    return " ".join(commands)


def build_svg(contributions: dict[str, int], repos: list[dict], generated: date) -> str:
    total = sum(contributions.values())
    active_days = sum(1 for count in contributions.values() if count > 0)
    public_repos = [
        repo
        for repo in repos
        if not repo.get("fork") and repo.get("name", "").lower() != USER.lower()
    ]
    week_totals, first, last = weekly_series(contributions)
    monthly = monthly_series(contributions)

    left, right = 56, 1144
    base_y, top_y = 302, 238
    span = right - left
    peak = max((count for _, count in monthly), default=0) or 1
    step = span / max(len(monthly) - 1, 1)

    coords = [
        (left + index * step, base_y - (base_y - top_y) * count / peak)
        for index, (_, count) in enumerate(monthly)
    ]
    curve = curve_commands(coords, top_y, base_y)
    line_path = f"M {coords[0][0]:.1f} {coords[0][1]:.1f} {curve}"
    area_path = (
        f"M {coords[0][0]:.1f} {base_y} L {coords[0][0]:.1f} {coords[0][1]:.1f} "
        f"{curve} L {coords[-1][0]:.1f} {base_y} Z"
    )

    # Faint weekly detail behind the monthly silhouette.
    week_peak = max((count for _, count in week_totals), default=0) or 1
    chart_start = monthly[0][0]
    total_days = max((last - chart_start).days, 1)
    ticks: list[str] = []
    for week_start, count in week_totals:
        if count <= 0:
            continue
        fraction = (week_start - chart_start).days / total_days
        if not 0 <= fraction <= 1:
            continue
        x = left + fraction * span
        height = 8 + 24 * math.sqrt(count / week_peak)
        ticks.append(
            f'<line x1="{x:.1f}" y1="{base_y}" x2="{x:.1f}" y2="{base_y - height:.1f}" '
            f'stroke="#3a3733" stroke-width="1.2" opacity="0.65"/>'
        )

    dots = [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="#f2efe8" stroke="#070707" stroke-width="1"/>'
        for x, y in coords
    ]

    peak_index = max(range(len(monthly)), key=lambda index: monthly[index][1])
    peak_x, peak_y = coords[peak_index]
    peak_label = (
        f'<circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="7" fill="none" stroke="#9a958b" opacity="0.55"/>'
    )

    month_labels = "".join(
        f'<text x="{left + index * step:.1f}" y="332" text-anchor="{"start" if index == 0 else "end" if index == len(monthly) - 1 else "middle"}" '
        f'font-size="20" letter-spacing="1.4" fill="#9a958b">{month.strftime("%b").upper()}</text>'
        for index, (month, _) in enumerate(monthly)
    )

    same_year = monthly[0][0].year == monthly[-1][0].year
    if same_year:
        heading = f"SIGNAL / {monthly[0][0].year}"
        range_label = (
            f"{monthly[0][0].strftime('%b').upper()} — {monthly[-1][0].strftime('%b').upper()} "
            f"{monthly[-1][0].year} · PEAK {peak:,}"
        )
    else:
        heading = f"SIGNAL / LAST {len(monthly)} MONTHS"
        range_label = (
            f"{monthly[0][0].strftime('%b').upper()} {monthly[0][0].year} — "
            f"{monthly[-1][0].strftime('%b').upper()} {monthly[-1][0].year} · PEAK {peak:,}"
        )

    grid = "".join(
        f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#1d1c1a" stroke-width="1"/>'
        for y in (top_y, 260, 281)
    )
    guides = "".join(
        f'<line x1="{x:.1f}" y1="{top_y}" x2="{x:.1f}" y2="{base_y}" stroke="#1b1a18" stroke-width="1"/>'
        for x, _ in coords
    )

    updated = generated.isoformat()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360" role="img" aria-labelledby="activityTitle activityDesc">
  <title id="activityTitle">OWSPER — public GitHub signal</title>
  <desc id="activityDesc">{total:,} public contributions on {active_days} active days across {len(public_repos)} project repositories, from {first.isoformat()} to {last.isoformat()}, drawn as a monthly signal trace.</desc>
  <defs>
    <linearGradient id="signalFill" x1="0" y1="238" x2="0" y2="300" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#f2efe8" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#f2efe8" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="360" fill="#070707"/>
  <rect x="0.5" y="0.5" width="1199" height="359" fill="none" stroke="#232323"/>

  <g font-family="{MONO}">
    <text x="56" y="48" font-size="13" letter-spacing="2.4" fill="#c9c5bc">{heading}</text>
    <text x="1144" y="48" text-anchor="end" font-size="11" letter-spacing="1.6" fill="#9a958b">UPDATED {updated} · GITHUB API</text>
    <line x1="330" y1="116" x2="330" y2="192" stroke="#242320" stroke-width="1"/>
    <line x1="642" y1="116" x2="642" y2="192" stroke="#242320" stroke-width="1"/>
  </g>

  <g font-family="{SERIF}" fill="#f2efe8">
    <text x="56" y="170" font-size="80" letter-spacing="-1">{total:,}</text>
    <text x="388" y="170" font-size="80" letter-spacing="-1" fill="#d4d0c6">{active_days}</text>
    <text x="700" y="170" font-size="80" letter-spacing="-1" fill="#d4d0c6">{len(public_repos)}</text>
  </g>

  <g font-family="{MONO}" font-size="12" letter-spacing="2.2" fill="#9a958b">
    <text x="56" y="198">PUBLIC CONTRIBUTIONS</text>
    <text x="388" y="198">ACTIVE DAYS</text>
    <text x="700" y="198">PROJECT REPOSITORIES</text>
  </g>

  <text x="56" y="220" font-family="{MONO}" font-size="10" letter-spacing="2" fill="#8a857c">MONTHLY TOTALS</text>
  <text x="1144" y="220" text-anchor="end" font-family="{MONO}" font-size="10" letter-spacing="2" fill="#8a857c">{range_label}</text>

  {grid}
  {guides}
  {''.join(ticks)}
  <path d="{area_path}" fill="url(#signalFill)"/>
  <path d="{line_path}" fill="none" stroke="#f2efe8" stroke-width="2"/>
  {''.join(dots)}
  {peak_label}
  <line x1="{left}" y1="{base_y}" x2="{right}" y2="{base_y}" stroke="#35322d" stroke-width="1"/>
  {month_labels}

  <g font-family="{MONO}" font-size="10" letter-spacing="1.6" fill="#8a857c">
    <text x="1144" y="354" text-anchor="end">OWSPER</text>
  </g>
</svg>
'''


def main() -> int:
    global USER
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--user", default=USER)
    args = parser.parse_args()
    USER = args.user
    token = os.environ.get("GITHUB_TOKEN") or None
    try:
        contributions, repos = load_data(token)
    except Exception as exc:  # noqa: BLE001 - graceful fallback
        log(f"::warning::Activity data unavailable, keeping existing asset. {exc}")
        return 0

    svg = build_svg(contributions, repos, datetime.now(timezone.utc).date())
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(svg)
    log(f"Wrote {args.out} ({len(svg.encode('utf-8')) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
