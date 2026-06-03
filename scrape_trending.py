#!/usr/bin/env python3
"""
Scrape GitHub Trending (monthly) using Scrapling and generate index.html.
"""
import os
import re
import json
import sys
from datetime import datetime
from pathlib import Path

from scrapling.fetchers import Fetcher
from jinja2 import Template

HERE = Path(__file__).parent
TEMPLATE_FILE = HERE / "template.html"
OUTPUT_FILE = HERE / "index.html"
CACHE_FILE = HERE / "_cached_trending.html"
TRENDING_URL = "https://github.com/trending?since=monthly"

# GitHub language colors (subset)
LANG_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178C6",
    "JavaScript": "#f1e05a",
    "Rust": "#dea584",
    "Go": "#00ADD8",
    "Java": "#b07219",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Shell": "#89e051",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
    "Scala": "#c22d40",
    "Lua": "#000080",
    "R": "#198CE7",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Zig": "#ec915c",
    "Solidity": "#AA6746",
    "Jupyter Notebook": "#DA5B0B",
    "TeX": "#3D6117",
    "Dockerfile": "#384d54",
    "PowerShell": "#012456",
    "Clojure": "#db5855",
    "Elixir": "#6e4a7e",
    "Haskell": "#5e5086",
    "Erlang": "#B83998",
    "Perl": "#0298c3",
    "HCL": "#844FBA",
    "Makefile": "#427819",
}

# CSS template — kept as raw string to avoid Jinja2 double-rendering
CSS_STYLE = """  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    color: #e6edf3;
    min-height: 100vh;
  }
  .container { max-width: 1280px; margin: 0 auto; padding: 40px 24px; }

  /* Header */
  header { text-align: center; margin-bottom: 48px; }
  header h1 {
    font-size: 2.8rem; font-weight: 800;
    background: linear-gradient(135deg, #58a6ff, #bc8cff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 8px;
  }
  header .subtitle {
    font-size: 1.1rem; color: #8b949e;
    display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  header .subtitle img { width: 20px; height: 20px; vertical-align: middle; }
  .update-badge {
    display: inline-block; margin-top: 12px;
    background: rgba(88, 166, 255, 0.15); color: #58a6ff;
    padding: 6px 16px; border-radius: 20px; font-size: 0.85rem;
    border: 1px solid rgba(88, 166, 255, 0.3);
  }

  /* Grid */
  .repo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 20px;
  }

  /* Card */
  .repo-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 24px;
    transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    position: relative;
    overflow: hidden;
  }
  .repo-card:hover {
    transform: translateY(-4px);
    border-color: #58a6ff;
    box-shadow: 0 12px 32px rgba(88, 166, 255, 0.1);
  }

  /* Rank badge */
  .rank-badge {
    position: absolute; top: 12px; right: 12px;
    width: 32px; height: 32px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.85rem;
  }
  .rank-1 { background: linear-gradient(135deg, #ffd700, #ffaa00); color: #0d1117; }
  .rank-2 { background: linear-gradient(135deg, #e0e0e0, #c0c0c0); color: #0d1117; }
  .rank-3 { background: linear-gradient(135deg, #cd7f32, #a0522d); color: #fff; }
  .rank-other { background: rgba(139, 148, 158, 0.2); color: #8b949e; }

  /* Card header */
  .card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .avatar {
    width: 44px; height: 44px; border-radius: 50%;
    background: #21262d; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem; font-weight: 700; color: #58a6ff;
  }
  .repo-name { flex: 1; min-width: 0; }
  .repo-name .owner {
    font-size: 0.8rem; color: #8b949e; display: block;
  }
  .repo-name .name {
    font-size: 1.1rem; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .repo-name .name a { color: #58a6ff; text-decoration: none; }
  .repo-name .name a:hover { text-decoration: underline; }

  /* Description */
  .description {
    font-size: 0.9rem; color: #8b949e; line-height: 1.5;
    margin-bottom: 16px;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Stats row */
  .stats {
    display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 14px;
    font-size: 0.85rem;
  }
  .stat { display: flex; align-items: center; gap: 4px; color: #8b949e; }
  .stat svg { width: 16px; height: 16px; fill: currentColor; }
  .stat .num { font-weight: 600; color: #e6edf3; }
  .hot-badge {
    background: rgba(255, 102, 0, 0.15); color: #ff6600;
    padding: 2px 10px; border-radius: 10px; font-weight: 600;
    font-size: 0.8rem; border: 1px solid rgba(255, 102, 0, 0.3);
    margin-left: auto;
  }

  /* Language + tags */
  .meta {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  }
  .lang-dot {
    width: 12px; height: 12px; border-radius: 50%; display: inline-block;
  }
  .lang { font-size: 0.85rem; color: #8b949e; }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag {
    font-size: 0.75rem; background: rgba(88, 166, 255, 0.1);
    color: #58a6ff; padding: 2px 8px; border-radius: 8px;
    max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  /* License */
  .license { font-size: 0.78rem; color: #484f58; margin-top: 10px; }

  /* Footer */
  footer {
    text-align: center; margin-top: 48px; padding: 20px 0;
    border-top: 1px solid #21262d; color: #484f58; font-size: 0.85rem;
  }
  footer a { color: #58a6ff; text-decoration: none; }

  /* Responsive */
  @media (max-width: 640px) {
    .container { padding: 20px 12px; }
    header h1 { font-size: 1.8rem; }
    .repo-grid { grid-template-columns: 1fr; }
  }
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🔥 GitHub 本月热门项目 Top {{ total }}</title>
<style>
{{ css_style }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🔥 GitHub 本月热门项目</h1>
    <p class="subtitle">
      <svg viewBox="0 0 16 16" width="20" height="20" fill="#8b949e"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      数据来自 GitHub Trending · {{ update_label }}
    </p>
    <span class="update-badge">📅 {{ month_label }} · 按本月新增 Star 排序</span>
  </header>

  <div class="repo-grid">
{% for repo in repos %}
    <!-- #{{ loop.index }} -->
    <div class="repo-card">
      <div class="rank-badge rank-{% if loop.index == 1 %}1{% elif loop.index == 2 %}2{% elif loop.index == 3 %}3{% else %}other{% endif %}">{{ loop.index }}</div>
      <div class="card-header">
        <div class="avatar" style="background:{{ repo.avatar_bg }};color:{{ repo.avatar_fg }};">{{ repo.avatar_char }}</div>
        <div class="repo-name">
          <span class="owner">{{ repo.owner }}</span>
          <div class="name"><a href="{{ repo.url }}" target="_blank">{{ repo.name }}</a></div>
        </div>
      </div>
      <div class="description">{{ repo.description }}</div>
      <div class="stats">
        <span class="stat">⭐ <span class="num">{{ repo.stars_total }}</span></span>
        <span class="stat">⑂ <span class="num">{{ repo.forks }}</span></span>
        <span class="hot-badge">🔥 +{{ repo.stars_month }} 本月</span>
      </div>
      <div class="meta">
        <span class="lang">{% if repo.language %}<span class="lang-dot" style="background:{{ repo.lang_color }};"></span> {{ repo.language }}{% else %}<span class="lang-dot" style="background:#8b949e;"></span> 无语言{% endif %}</span>
        {% if repo.tags %}
        <div class="tags">
          {% for tag in repo.tags[:5] %}
          <span class="tag">{{ tag }}</span>
          {% endfor %}
        </div>
        {% endif %}
      </div>
      {% if repo.license %}
      <div class="license">{{ repo.license }}</div>
      {% endif %}
    </div>
{% endfor %}
  </div>

  <footer>
    <p>数据来源 <a href="https://github.com/trending?since=monthly" target="_blank">GitHub Trending (Monthly)</a> · 由 <a href="https://github.com/D4Vinci/Scrapling" target="_blank">Scrapling</a> 自动抓取生成 · 更新时间 {{ update_date }}</p>
    <p style="margin-top:4px;">用 <a href="https://github.com/" target="_blank">GitHub</a> ⭐ 支持你喜欢的项目！</p>
  </footer>
</div>
</body>
</html>"""


def elem_text(el) -> str:
    """Extract visible text from a Selector element using ::text pseudo."""
    nodes = el.css("::text")
    if not nodes:
        return ""
    # Take the last non-whitespace text node
    for n in reversed(nodes):
        t = n.text.strip() if hasattr(n, "text") else str(n).strip()
        if t:
            return t
    return nodes[-1].text.strip() if hasattr(nodes[-1], "text") else str(nodes[-1]).strip()


def parse_stars(text: str) -> int:
    """Parse star count like '37,690' or '35,822 stars this month'."""
    text = text.strip()
    text = text.replace("stars this month", "").replace("stars today", "").replace("stars this week", "").strip()
    return int(text.replace(",", ""))


def parse_number(text: str) -> int:
    """Parse a number string like '2,332' or '37,690'."""
    return int(text.strip().replace(",", ""))


def color_variant(hex_color: str, brightness_offset: int = 40) -> str:
    """Lighten or darken a hex color."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, min(255, r + brightness_offset))
    g = max(0, min(255, g + brightness_offset))
    b = max(0, min(255, b + brightness_offset))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_avatar_params(owner: str) -> dict:
    """Generate deterministic avatar colors from owner name."""
    hash_val = sum(ord(c) for c in owner)
    bg_colors = [
        "#e3f2fd", "#fce4ec", "#fff3e0", "#e8f5e9",
        "#f3e5f5", "#e0f7fa", "#fff8e1", "#fbe9e7"
    ]
    fg_colors = [
        "#1565c0", "#c62828", "#e65100", "#2e7d32",
        "#7b1fa2", "#00838f", "#f9a825", "#bf360c"
    ]
    idx = hash_val % len(bg_colors)
    return {
        "avatar_bg": bg_colors[idx],
        "avatar_fg": fg_colors[idx],
        "avatar_char": owner[0].upper() if owner else "?"
    }


def fetch_page() -> bytes:
    """Fetch the trending page, or fall back to cached copy."""
    import time
    try:
        print(f"Fetching {TRENDING_URL} ...")
        page = Fetcher.get(TRENDING_URL, verify=False, timeout=15)
        body = page.body if isinstance(page.body, bytes) else page.body.encode('utf-8')
        print(f"Fetched {len(body)} bytes")
        # Save cache
        CACHE_FILE.write_bytes(body)
        return body
    except Exception as e:
        print(f"Fetch failed: {e}", file=sys.stderr)
        if CACHE_FILE.exists():
            print("Falling back to cached HTML ...")
            return CACHE_FILE.read_bytes()
        raise


def parse_trending(html: bytes) -> list[dict]:
    """Parse GitHub Trending HTML and extract repo data."""
    from scrapling import Selector
    page = Selector(html.decode('utf-8'))

    articles = page.css("article")
    print(f"Found {len(articles)} articles")

    repos = []
    for i, article in enumerate(articles):
        try:
            # --- Owner / Repo name from h2 > a ---
            h2_link = article.css("h2 a")
            if not h2_link:
                continue
            href = h2_link[0].attrib.get("href", "")
            # href is like "/owner/repo"
            parts = href.strip("/").split("/")
            if len(parts) < 2:
                continue
            owner, repo_name = parts[0], parts[1]

            # --- Description from p ---
            desc_elem = article.css("p.col-9")
            description = elem_text(desc_elem[0]) if desc_elem else ""

            # --- Find the stats div ---
            stats_div = article.css("div.f6")
            if not stats_div:
                continue
            stats = stats_div[0]

            # Total stars
            star_links = stats.css('a[href*="/stargazers"]')
            stars_total = 0
            if star_links:
                star_text = elem_text(star_links[0])
                if star_text:
                    stars_total = parse_number(star_text)

            # Forks
            fork_links = stats.css('a[href*="/forks"]')
            forks = 0
            if fork_links:
                fork_text = elem_text(fork_links[0])
                if fork_text:
                    forks = parse_number(fork_text)

            # Stars this month (the float-right span)
            month_star_span = stats.css("span.float-sm-right")
            stars_month = 0
            if month_star_span:
                month_text = elem_text(month_star_span[0])
                if month_text:
                    stars_month = parse_stars(month_text)

            # Language
            lang_span = stats.css('span[itemprop="programmingLanguage"]')
            language = elem_text(lang_span[0]) if lang_span else None

            # Language color
            lang_color = LANG_COLORS.get(language, "#8b949e")

            # Avatar params
            avatar = get_avatar_params(owner)

            # GitHub URL
            url = f"https://github.com/{owner}/{repo_name}"

            # Get license and topics via GitHub API
            license_text, tags = get_repo_details(owner, repo_name)

            repos.append({
                "owner": owner,
                "name": repo_name,
                "url": url,
                "description": description,
                "stars_total": f"{stars_total:,}",
                "forks": f"{forks:,}",
                "stars_month": f"{stars_month:,}",
                "language": language,
                "lang_color": lang_color,
                "license": license_text,
                "tags": tags,
                **avatar,
            })

            print(f"  [{i+1}] {owner}/{repo_name} ⭐{stars_total:,} (+{stars_month:,}) {language or 'N/A'}")
        except Exception as e:
            print(f"  [!] Error parsing article {i+1}: {e}", file=sys.stderr)
            continue

    return repos


def get_repo_details(owner: str, repo_name: str) -> tuple[str | None, list[str]]:
    """Fetch repo license and topics from GitHub API."""
    import urllib.request
    import urllib.error

    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    try:
        req = urllib.request.Request(api_url)
        req.add_header("Accept", "application/vnd.github.mercy-preview+json")  # topics support
        req.add_header("User-Agent", "Scrapling-Trending/1.0")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # License
        license_text = None
        if data.get("license") and data["license"].get("spdx_id"):
            spdx = data["license"]["spdx_id"]
            if spdx != "NOASSERTION":
                license_text = f"{spdx} License" if "License" not in spdx else spdx

        # Topics
        tags = data.get("topics", [])[:10]

        return license_text, tags
    except Exception as e:
        print(f"  [!] API error for {owner}/{repo_name}: {e}", file=sys.stderr)
        return None, []


def format_date() -> tuple[str, str]:
    """Return (month_label, update_date, update_label)."""
    now = datetime.utcnow()
    chinese_months = [
        "", "1月", "2月", "3月", "4月", "5月", "6月",
        "7月", "8月", "9月", "10月", "11月", "12月"
    ]
    month_str = f"{now.year}年{chinese_months[now.month]}"
    update_date = now.strftime("%Y年%m月%d日")
    update_label = "每日更新"
    return month_str, update_date, update_label


def main():
    html = fetch_page()
    repos = parse_trending(html)
    if not repos:
        print("ERROR: No repos scraped!", file=sys.stderr)
        sys.exit(1)

    repos = repos[:12]  # Top 12 only
    month_label, update_date, update_label = format_date()

    template = Template(HTML_TEMPLATE)
    html = template.render(
        css_style=CSS_STYLE,
        repos=repos,
        total=len(repos),
        month_label=month_label,
        update_date=update_date,
        update_label=update_label,
    )

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"\n✅ Generated {OUTPUT_FILE} with {len(repos)} repos")


if __name__ == "__main__":
    main()
