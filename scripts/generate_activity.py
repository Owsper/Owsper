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
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = "Owsper"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO_ROOT, "assets", "activity.svg")

# Monochrome activity levels, dark -> light.
LEVELS = [(0, 0, "#141414"), (1, 2, "#2b2b2b"), (3, 5, "#4a4a4a"), (6, 10, "#7a7a7a"), (11, 10**9, "#cfcfcf")]
SERIES = ["#d8d8d8", "#a9a9a9", "#858585", "#6a6a6a", "#545454", "#404040", "#2e2e2e"]


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


def level_for(count: int) -> str:
    for low, high, color in LEVELS:
        if low <= count <= high:
            return color
    return LEVELS[-1][2]


def esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def language_mix(repos: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        language = repo.get("language") or "Docs only"
        if language == "Jupyter Notebook":
            language = "Jupyter"
        counts[language] = counts.get(language, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def build_svg(contributions: dict[str, int], repos: list[dict], generated: date) -> str:
    total = sum(contributions.values())
    active_days = sum(1 for count in contributions.values() if count > 0)
    public_repos = [repo for repo in repos if not repo.get("fork")]
    languages = language_mix(public_repos)

    days = sorted(date.fromisoformat(day) for day in contributions)
    first, last = days[0], days[-1]
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)  # Sunday
    weeks = ((last - grid_start).days // 7) + 1
    pitch = 16 if weeks <= 53 else max(12, 844 // weeks)
    cell = pitch - 4
    left, top = 56, 92
    grid_width = weeks * pitch - (pitch - cell)
    month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

    cells: list[str] = []
    labels: list[str] = []
    seen_month = None
    for week in range(weeks):
        week_start = grid_start + timedelta(days=week * 7)
        if week_start.month != seen_month and week_start.day <= 7:
            seen_month = week_start.month
            x = left + week * pitch
            if x + 26 < left + grid_width:
                labels.append(
                    f'<text x="{x}" y="{top + 7 * pitch + 12}" font-size="8.5" letter-spacing="1.6" '
                    f'fill="#5c5c5c">{month_names[week_start.month - 1]}</text>'
                )
        for weekday in range(7):
            day = week_start + timedelta(days=weekday)
            if day < first or day > last:
                continue
            count = contributions.get(day.isoformat(), 0)
            x = left + week * pitch
            y = top + weekday * pitch
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1.5" '
                f'fill="{level_for(count)}"><title>{day.isoformat()} — {count} '
                f'contribution{"s" if count != 1 else ""}</title></rect>'
            )

    # Stacked language bar, width proportional to repository count.
    bar_x, bar_y, bar_w, bar_h = 56, 292, 1088, 6
    segments: list[str] = []
    legend: list[str] = []
    cursor = bar_x
    total_repos = sum(count for _, count in languages) or 1
    column = bar_w / max(len(languages), 1)
    for index, (name, count) in enumerate(languages):
        width = round(bar_w * count / total_repos)
        if index == len(languages) - 1:
            width = bar_x + bar_w - cursor
        color = SERIES[index % len(SERIES)]
        segments.append(
            f'<rect x="{cursor}" y="{bar_y}" width="{max(width - 2, 1)}" height="{bar_h}" fill="{color}"/>'
        )
        lx = bar_x + index * column
        legend.append(
            f'<rect x="{lx}" y="318" width="7" height="7" fill="{color}"/>'
            f'<text x="{lx + 13}" y="325" font-size="9" letter-spacing="1.2" fill="#8a8a8a">'
            f"{esc(name)} {count}</text>"
        )
        cursor += width

    updated = generated.isoformat()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="410" viewBox="0 0 1200 410" role="img" aria-labelledby="activityTitle activityDesc">
  <title id="activityTitle">OWSPER — public GitHub activity</title>
  <desc id="activityDesc">{total:,} public contributions in the last year across {len(public_repos)} public repositories. Contribution calendar and primary-language distribution generated from the GitHub API.</desc>
  <rect width="1200" height="410" fill="#080808"/>
  <rect x="0.5" y="0.5" width="1199" height="409" fill="none" stroke="#1f1f1f"/>

  <g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, 'Courier New', monospace">
    <text x="56" y="52" font-size="10.5" letter-spacing="4" fill="#b4b4b4">SIGNAL / LAST 12 MONTHS</text>
    <text x="1144" y="52" font-size="9" letter-spacing="2.4" fill="#5a5a5a" text-anchor="end">UPDATED {updated} · GITHUB API</text>

    {''.join(cells)}
    {''.join(labels)}

    <text x="956" y="124" font-size="46" font-weight="200" letter-spacing="1" fill="#f4f4f4">{total:,}</text>
    <text x="956" y="144" font-size="8.5" letter-spacing="2.4" fill="#626262">PUBLIC CONTRIBUTIONS</text>
    <text x="956" y="182" font-size="46" font-weight="200" letter-spacing="1" fill="#cfcfcf">{active_days}</text>
    <text x="956" y="202" font-size="8.5" letter-spacing="2.4" fill="#626262">ACTIVE DAYS</text>
    <text x="956" y="240" font-size="10" letter-spacing="2" fill="#8a8a8a">{len(public_repos)} PUBLIC REPOSITORIES</text>

    <line x1="56" y1="252" x2="1144" y2="252" stroke="#242424" stroke-width="1"/>
    <text x="56" y="277" font-size="9" letter-spacing="2.4" fill="#626262">PRIMARY LANGUAGE BY REPOSITORY</text>
    {''.join(segments)}
    {''.join(legend)}
    <text x="56" y="382" font-size="8" letter-spacing="1.8" fill="#6a6a6a">GENERATED FROM PUBLIC GITHUB DATA. NO THIRD-PARTY STATISTICS SERVICES.</text>
    <text x="1144" y="382" font-size="8" letter-spacing="1.8" fill="#6a6a6a" text-anchor="end">OWSPER</text>
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
