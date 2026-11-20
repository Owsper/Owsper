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


def build_svg(contributions: dict[str, int], repos: list[dict], generated: date) -> str:
    total = sum(contributions.values())
    active_days = sum(1 for count in contributions.values() if count > 0)
    public_repos = [repo for repo in repos if not repo.get("fork")]
    series, first, last = weekly_series(contributions)

    left, right = 56, 1144
    base_y, top_y = 300, 238
    span = right - left
    peak = max((count for _, count in series), default=0) or 1

    points: list[str] = []
    bars: list[str] = []
    dots: list[str] = []
    step = span / max(len(series) - 1, 1)
    for index, (_, count) in enumerate(series):
        x = left + index * step
        height = round((base_y - top_y) * math.sqrt(count / peak)) if count else 0
        if height <= 0:
            color = "#242320"
            height = 1
        elif count >= peak * 0.66:
            color = "#c9c5bc"
        elif count >= peak * 0.33:
            color = "#6f6b64"
        else:
            color = "#3a3733"
        bars.append(
            f'<line x1="{x:.1f}" y1="{base_y}" x2="{x:.1f}" y2="{base_y - height}" '
            f'stroke="{color}" stroke-width="2.5"/>'
        )
        points.append(f"{x:.1f},{base_y - height}")
        if count >= peak * 0.8:
            dots.append(f'<circle cx="{x:.1f}" cy="{base_y - height}" r="2" fill="#f2efe8"/>')

    months: list[str] = []
    seen: set[int] = set()
    for index in (0, len(series) // 4, len(series) // 2, (3 * len(series)) // 4):
        week_start = series[min(index, len(series) - 1)][0]
        key = week_start.year * 12 + week_start.month
        if key in seen:
            continue
        seen.add(key)
        x = left + index * step
        label = week_start.strftime("%b").upper()
        if index == 0:
            label = f"{week_start.strftime('%b').upper()} {week_start.year}"
        months.append(
            f'<text x="{x:.1f}" y="330" font-size="21" letter-spacing="1.4" fill="#8a857c">{label}</text>'
        )
    months.append(f'<text x="{right}" y="330" text-anchor="end" font-size="21" letter-spacing="1.4" fill="#8a857c">TODAY</text>')

    grid = "".join(
        f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#1d1c1a" stroke-width="1"/>'
        for y in (top_y, 258, 279)
    )

    updated = generated.isoformat()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360" role="img" aria-labelledby="activityTitle activityDesc">
  <title id="activityTitle">OWSPER — public GitHub signal</title>
  <desc id="activityDesc">{total:,} public contributions on {active_days} active days across {len(public_repos)} public repositories, from {first.isoformat()} to {last.isoformat()}, drawn as a weekly signal trace.</desc>
  <rect width="1200" height="360" fill="#070707"/>
  <rect x="0.5" y="0.5" width="1199" height="359" fill="none" stroke="#232323"/>

  <g font-family="{MONO}">
    <text x="56" y="48" font-size="13" letter-spacing="2.4" fill="#c9c5bc">SIGNAL / LAST 12 MONTHS</text>
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
    <text x="700" y="198">PUBLIC REPOSITORIES</text>
  </g>

  {grid}
  <polyline points="{' '.join(points)}" fill="none" stroke="#f2efe8" stroke-width="1.2" opacity="0.32"/>
  {''.join(bars)}
  {''.join(dots)}
  <line x1="{left}" y1="{base_y}" x2="{right}" y2="{base_y}" stroke="#35322d" stroke-width="1"/>
  {''.join(months)}

  <g font-family="{MONO}" font-size="10" letter-spacing="1.6" fill="#8a857c">
    <text x="56" y="352">GENERATED FROM PUBLIC GITHUB DATA. NO THIRD-PARTY STATISTICS SERVICES.</text>
    <text x="1144" y="352" text-anchor="end">OWSPER</text>
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
