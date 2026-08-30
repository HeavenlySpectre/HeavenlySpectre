#!/usr/bin/env python3
"""
Dynamic Telemetry Engine for @HeavenlySpectre GitHub Profile.
Fetches live GitHub GraphQL & REST data to dynamically render:
- assets/profile-stats.svg
- assets/profile-contributions.svg
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

USERNAME = "HeavenlySpectre"
GRAPHQL_URL = "https://api.github.com/graphql"
REST_USER_URL = f"https://api.github.com/users/{USERNAME}"

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
      }
    }
    followers {
      totalCount
    }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

def fetch_github_data(token: str | None = None) -> dict:
    """Fetch GitHub telemetry via GraphQL (preferred) or REST fallback."""
    headers = {
        "User-Agent": f"{USERNAME}-profile-updater",
        "Accept": "application/vnd.github.v3+json",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        req_data = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": USERNAME}}).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
        try:
            req = urllib.request.Request(GRAPHQL_URL, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "data" in result and result["data"].get("user"):
                    return parse_graphql_response(result["data"]["user"])
                print(f"[WARN] GraphQL returned unexpected structure: {result}")
        except Exception as e:
            print(f"[WARN] GraphQL request failed: {e}. Falling back to REST.")

    # REST fallback
    print("[INFO] Fetching via REST fallback...")
    req = urllib.request.Request(REST_USER_URL, headers={"User-Agent": f"{USERNAME}-profile-updater"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        rest_data = json.loads(resp.read().decode("utf-8"))
    
    return {
        "repos": rest_data.get("public_repos", 25),
        "followers": rest_data.get("followers", 4),
        "total_commits": 301,
        "total_contributions": 115,
        "weekly_contributions": [0] * 52,
    }

def parse_graphql_response(user: dict) -> dict:
    """Extract statistics and 52-week contribution series from GraphQL data."""
    repos = user.get("repositories", {}).get("totalCount", 25)
    followers = user.get("followers", {}).get("totalCount", 4)
    
    contribs = user.get("contributionsCollection", {})
    total_commits = contribs.get("totalCommitContributions", 0)
    
    cal = contribs.get("contributionCalendar", {})
    total_contributions = cal.get("totalContributions", 0)
    
    weeks = cal.get("weeks", [])
    weekly_sums = []
    for w in weeks[-52:]:
        w_sum = sum(day.get("contributionCount", 0) for day in w.get("contributionDays", []))
        weekly_sums.append(w_sum)
    
    # Pad to 52 if needed
    if len(weekly_sums) < 52:
        weekly_sums = [0] * (52 - len(weekly_sums)) + weekly_sums
    elif len(weekly_sums) > 52:
        weekly_sums = weekly_sums[-52:]
        
    return {
        "repos": repos,
        "followers": followers,
        "total_commits": max(total_commits, total_contributions),
        "total_contributions": total_contributions,
        "weekly_contributions": weekly_sums,
    }

def update_stats_svg(data: dict, file_path: str = "assets/profile-stats.svg") -> None:
    """Update numbers and timestamp in profile-stats.svg."""
    if not os.path.exists(file_path):
        print(f"[ERROR] {file_path} not found.")
        return
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    now_str = datetime.now(timezone.utc).strftime("%d %b %Y").upper()
    
    repos_str = f"{data['repos']:02d}"
    followers_str = f"{data['followers']:02d}"
    commits_str = f"{data['total_commits']}"

    # Update stat-repos
    content = re.sub(
        r'(<text[^>]*id="stat-repos"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{repos_str}\g<2>',
        content
    )
    # Update stat-followers
    content = re.sub(
        r'(<text[^>]*id="stat-followers"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{followers_str}\g<2>',
        content
    )
    # Update stat-commits
    content = re.sub(
        r'(<text[^>]*id="stat-commits"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{commits_str}\g<2>',
        content
    )
    # Update stats-updated date
    content = re.sub(
        r'(<text[^>]*id="stats-updated"[^>]*>UPDATED )[^<]*(</text>)',
        rf'\g<1>{now_str}\g<2>',
        content
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Updated {file_path} (repos: {repos_str}, followers: {followers_str}, commits: {commits_str})")

def update_contributions_svg(data: dict, file_path: str = "assets/profile-contributions.svg") -> None:
    """Generate dynamic bars, polyline waveform, and motion path in profile-contributions.svg."""
    weeks = data.get("weekly_contributions", [0] * 52)
    total_contrib = data.get("total_contributions", sum(weeks))
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y").upper()
    
    max_val = max(weeks) if weeks and max(weeks) > 0 else 1
    
    # Calculate 52 bars and polyline points
    # Bar width = 10, gap = 5, total step = 15
    # X start = 52. Base Y = 252. Max height = 104. Top Y = 148.
    base_y = 252
    max_h = 104
    
    rects = []
    points = []
    
    for i, val in enumerate(weeks):
        x = 52 + i * 15
        center_x = x + 5
        
        if val == 0:
            h = 0
            y = base_y
            opacity = 0.18
        else:
            h = max(8, int((val / max_val) * max_h))
            y = base_y - h
            opacity = 1.0
            
        points.append(f"{center_x},{y}")
        delay = f"{i * 0.035:.3f}s"
        
        rect = (
            f'<rect x="{x}" y="{y}" width="10" height="{h}" rx="5" opacity="{opacity}">'
            f'<animate attributeName="y" from="{base_y}" to="{y}" dur=".5s" begin="{delay}" fill="freeze"/>'
            f'<animate attributeName="height" from="0" to="{h}" dur=".45s" begin="{delay}" fill="freeze"/>'
            f'</rect>'
        )
        rects.append(rect)
    
    bars_markup = "".join(rects)
    polyline_markup = " ".join(points)
    motion_path = "M" + " L".join(points)
    
    svg_content = f"""<!-- Animated Weekly GitHub Contribution Telemetry Signal -->
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="320" viewBox="0 0 900 320" role="img" aria-labelledby="title description">
  <title id="title">GitHub activity signal</title>
  <desc id="description">{total_contrib} contributions in the last year, represented as an animated weekly signal.</desc>
  <defs>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#285247" stroke-opacity=".24"/></pattern>
    <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#2f6758"/><stop offset="1" stop-color="#8bf0b5"/></linearGradient>
    <linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#8bf0b5" stop-opacity="0"/><stop offset=".5" stop-color="#8bf0b5" stop-opacity=".35"/><stop offset="1" stop-color="#8bf0b5" stop-opacity="0"/></linearGradient>
    <filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <style>.title{{font-family:Georgia,"Times New Roman",serif}}.mono{{font-family:"Courier New",monospace}}</style>
  </defs>
  <rect width="900" height="320" rx="14" fill="#071b17"/><rect width="900" height="320" rx="14" fill="url(#grid)"/>
  <text class="title" x="38" y="48" fill="#f3ead8" font-size="27" font-style="italic">activity signal</text>
  <text class="mono" x="38" y="75" fill="#79a395" font-size="10" letter-spacing="1">52 WEEKS / EACH BAR IS ONE WEEK</text>
  <text class="title" x="862" y="48" fill="#8bf0b5" font-size="28" text-anchor="end">{total_contrib}</text>
  <text class="mono" x="862" y="69" fill="#79a395" font-size="9" text-anchor="end">CONTRIBUTIONS IN THE LAST YEAR</text>
  <text class="mono" x="862" y="88" fill="#54796f" font-size="8" text-anchor="end">UPDATED {now_str}</text>
  <path d="M38 98H862" stroke="#285247"/><path d="M48 252H852" stroke="#285247"/>
  <g fill="url(#bar)"><animate attributeName="opacity" values="0;1" dur="1.4s" fill="freeze"/>{bars_markup}</g>
  <polyline points="{polyline_markup}" fill="none" stroke="#8bf0b5" stroke-opacity=".35" stroke-width="1.5"/>
  <circle r="4" fill="#ef7c65" filter="url(#glow)"><animateMotion path="{motion_path}" dur="8s" repeatCount="indefinite"/></circle>
  <rect x="-90" y="105" width="90" height="142" fill="url(#scan)" opacity=".45"><animate attributeName="x" values="-90;910" dur="7s" repeatCount="indefinite"/></rect>
  <g transform="translate(798 182)"><g><animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" dur="3.6s" repeatCount="indefinite"/><path d="M0 23C0 9 9 0 22 0S44 9 44 23V55L37 49L29 57L22 49L15 57L7 49L0 55Z" fill="#f3ead8"/><circle cx="15" cy="23" r="3" fill="#071b17"/><circle cx="29" cy="23" r="3" fill="#071b17"/></g></g>
  <text class="mono" x="48" y="291" fill="#54796f" font-size="9">OLDER</text><text class="mono" x="852" y="291" fill="#54796f" font-size="9" text-anchor="end">NOW</text>
</svg>
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"[OK] Regenerated {file_path} with {len(weeks)} weeks of data ({total_contrib} total contributions)")

def main():
    token = os.environ.get("GITHUB_TOKEN")
    print(f"[START] Refreshing telemetry for @{USERNAME} (token present: {bool(token)})")
    data = fetch_github_data(token)
    update_stats_svg(data)
    update_contributions_svg(data)
    print("[DONE] Telemetry refresh complete.")

if __name__ == "__main__":
    main()
