"""
Autonomous Market Sentiment & Competitor Intel Agent — MCP Tool Server.

Tools provided:
  1. fetch_hackernews    — search Hacker News Algolia API
  2. fetch_reddit        — search Reddit via public JSON API
  3. save_sentiment      — append sentiment analysis to intel_data.json
  4. read_sentiment_log  — read back all saved sentiment entries
  5. compare_topics      — side-by-side comparison of saved topics
  6. generate_report     — write a markdown report to the sandbox
  7. list_sandbox_files  — list files in the sandbox directory
  8. generate_ui         — push a Prefab dashboard spec to generated_app.py

Run:
  python intel_mcp_server.py          # stdio transport (used by agent)
  mcp dev intel_mcp_server.py         # dev inspector

Install:
  pip install "mcp[cli]" requests python-dotenv
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("IntelServer")

# ---------------------------------------------------------------------------
# Sandbox — every file tool is confined to this directory.
# ---------------------------------------------------------------------------
SANDBOX = Path(__file__).parent / "sandbox"
SANDBOX.mkdir(exist_ok=True)


def _safe_path(relative: str) -> Path:
    """Resolve `relative` inside SANDBOX and refuse anything that escapes."""
    p = (SANDBOX / relative).resolve()
    if SANDBOX.resolve() not in p.parents and p != SANDBOX.resolve():
        raise ValueError(f"Path '{relative}' escapes the sandbox")
    return p


# ===========================================================================
# 1. HACKER NEWS FETCH TOOL
# ===========================================================================
@mcp.tool()
def fetch_hackernews(topic: str) -> str:
    """Fetch the top 10 recent discussions from Hacker News about a topic.
    Returns titles and point counts.
    """
    url = f"http://hn.algolia.com/api/v1/search?query={topic}&hitsPerPage=10&tags=story"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])

        if not hits:
            return f"No recent Hacker News discussions found for: {topic}"

        results = []
        for i, hit in enumerate(hits, 1):
            title = hit.get("title") or hit.get("story_title") or "No title"
            points = hit.get("points") or 0
            num_comments = hit.get("num_comments") or 0
            author = hit.get("author") or "unknown"
            url_item = hit.get("url") or ""
            results.append(
                f"{i}. {title} | {points} pts | {num_comments} comments | by {author} | {url_item}"
            )

        return "\n".join(results)
    except Exception as e:
        return f"Error fetching Hacker News data for {topic}: {e}"


# ===========================================================================
# 2. REDDIT FETCH TOOL
# ===========================================================================
@mcp.tool()
def fetch_reddit(topic: str) -> str:
    """Search Reddit for recent posts about a topic using the public JSON API.
    Returns top 8 posts with title, score, subreddit, and comment count.
    """
    url = f"https://www.reddit.com/search.json?q={topic}&sort=relevance&t=month&limit=8"
    headers = {"User-Agent": "IntelMCPBot/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        posts = data.get("data", {}).get("children", [])

        if not posts:
            return f"No recent Reddit posts found for: {topic}"

        results = []
        for i, post in enumerate(posts, 1):
            d = post.get("data", {})
            title = d.get("title", "No title")
            score = d.get("score", 0)
            subreddit = d.get("subreddit_name_prefixed", "r/unknown")
            num_comments = d.get("num_comments", 0)
            results.append(
                f"{i}. [{subreddit}] {title} | {score} upvotes | {num_comments} comments"
            )

        return "\n".join(results)
    except Exception as e:
        return f"Error fetching Reddit data for {topic}: {e}"


# ===========================================================================
# 3. FILE CRUD — SAVE SENTIMENT
# ===========================================================================
@mcp.tool()
def save_sentiment(topic: str, raw_data: str, sentiment_score: str) -> str:
    """Save sentiment analysis results and raw findings to a local JSON-lines file.
    Parameters:
      topic           — the topic that was analyzed (e.g. 'DeepSeek')
      raw_data        — the raw text findings from the internet fetch
      sentiment_score — overall sentiment: positive, neutral, or negative
    Appends one JSON object per call to intel_data.json in the sandbox.
    """
    db_path = _safe_path("intel_data.json")

    entry = {
        "topic": topic,
        "sentiment_score": sentiment_score,
        "raw_data": raw_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with open(db_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return f"Saved sentiment for '{topic}' (score={sentiment_score}) → {db_path.name}"
    except Exception as e:
        return f"Error saving sentiment data: {e}"


# ===========================================================================
# 4. READ SENTIMENT LOG
# ===========================================================================
@mcp.tool()
def read_sentiment_log() -> str:
    """Read all previously saved sentiment entries from intel_data.json.
    Returns each entry as a formatted line.
    """
    db_path = _safe_path("intel_data.json")
    if not db_path.exists():
        return "No sentiment data found yet — intel_data.json does not exist."

    lines = db_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return "intel_data.json is empty."

    results = []
    for i, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
            topic = entry.get("topic", "?")
            score = entry.get("sentiment_score", "?")
            ts = entry.get("timestamp", "")
            results.append(f"{i}. [{score.upper()}] {topic} (at {ts})")
        except json.JSONDecodeError:
            results.append(f"{i}. (malformed entry)")

    return "\n".join(results)


# ===========================================================================
# 5. COMPARE TOPICS
# ===========================================================================
@mcp.tool()
def compare_topics() -> str:
    """Compare all saved topics side-by-side from the sentiment log.
    Summarises each unique topic with its latest sentiment score
    and how many data entries exist for it.
    """
    db_path = _safe_path("intel_data.json")
    if not db_path.exists():
        return "No data to compare — run some analyses first."

    lines = db_path.read_text(encoding="utf-8").strip().splitlines()
    topic_map: dict[str, dict] = {}
    for line in lines:
        try:
            entry = json.loads(line)
            t = entry.get("topic", "unknown")
            if t not in topic_map:
                topic_map[t] = {"count": 0, "sentiments": []}
            topic_map[t]["count"] += 1
            topic_map[t]["sentiments"].append(entry.get("sentiment_score", "?"))
        except json.JSONDecodeError:
            pass

    if not topic_map:
        return "No valid entries found."

    results = []
    for topic, info in topic_map.items():
        latest = info["sentiments"][-1] if info["sentiments"] else "?"
        results.append(
            f"• {topic}: {info['count']} entries, latest sentiment = {latest}"
        )
    return "\n".join(results)


# ===========================================================================
# 6. GENERATE MARKDOWN REPORT
# ===========================================================================
@mcp.tool()
def generate_report(topic: str, summary: str) -> str:
    """Generate a professional Markdown report and save it to the sandbox.
    Parameters:
      topic   — the topic being reported on
      summary — a detailed text summary to include in the report body
    Writes to sandbox/<topic>_report.md.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", topic).strip("_").lower()
    filename = f"{slug}_report.md"
    report_path = _safe_path(filename)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# Market Sentiment Report: {topic}

**Generated:** {ts}

---

## Executive Summary

{summary}

---

*Report generated by the Autonomous Market Sentiment & Competitor Intel Agent.*
"""
    report_path.write_text(md, encoding="utf-8")
    return f"Report saved → {filename}"


# ===========================================================================
# 7. LIST SANDBOX FILES
# ===========================================================================
@mcp.tool()
def list_sandbox_files() -> str:
    """List all files currently stored in the sandbox directory."""
    files = sorted(SANDBOX.iterdir())
    if not files:
        return "Sandbox is empty."
    lines = []
    for f in files:
        size = f.stat().st_size if f.is_file() else 0
        kind = "DIR" if f.is_dir() else f"{size:,} bytes"
        lines.append(f"  {f.name}  ({kind})")
    return "\n".join(lines)


# ===========================================================================
# 8. PREFAB UI GENERATION TOOL
# ===========================================================================

def _slug(s: str, default: str = "k") -> str:
    out = re.sub(r"[^a-zA-Z0-9_]+", "_", str(s)).strip("_").lower()
    return out or default


def _widget_lines(w: dict, ctx: dict) -> list[str]:
    kind = w.get("kind") or w.get("type", "")
    data_val = w.get("data")
    if isinstance(data_val, dict):
        w = {**w, **data_val}
    elif isinstance(data_val, list) and kind not in ("pie", "bar", "line", "sparkline"):
        w["items"] = data_val
    elif isinstance(data_val, str) and kind == "text":
        w["body"] = data_val

    ctx["uid"] = ctx.get("uid", 0) + 1
    uid = ctx["uid"]

    if kind == "stat":
        label = w.get("label") or w.get("title") or ""
        value = str(w.get("value", ""))
        sub = w.get("sub", "")
        out = [
            'with Card():',
            '    with CardContent():',
            '        with Column(gap=1):',
            f'            Muted({label!r})',
            f'            H1({value!r})',
        ]
        if sub:
            out.append(f'            Muted({sub!r})')
        return out

    if kind == "pie":
        title = w.get("title", "")
        data = w.get("data", [])
        name_key = w.get("name_key", "name")
        value_key = w.get("value_key", "value")
        # Normalizations for common LLM hallucinations
        if isinstance(data, dict):
            data = [{name_key: k, value_key: v} for k, v in data.items()]
        elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) and name_key not in data[0]:
            data = [{name_key: k, value_key: v} for k, v in data[0].items()]

        clean = []
        for row in data:
            if isinstance(row, dict):
                # If they used keys like "label" instead of "name"
                nk = name_key if name_key in row else ("label" if "label" in row else None)
                vk = value_key if value_key in row else ("value" if "value" in row else None)
                if nk and vk:
                    try:
                        val = float(row[vk])
                        clean.append({name_key: str(row[nk]), value_key: val})
                    except (ValueError, TypeError):
                        pass
        out = ['with Card():', '    with CardContent():', '        with Column(gap=2):']
        if title:
            out.append(f'            H3({title!r})')
        out.append(
            f'            PieChart(data={clean!r}, data_key={value_key!r}, '
            f'name_key={name_key!r}, show_legend=True)'
        )
        return out

    if kind == "bar":
        title = w.get("title", "")
        data = w.get("data", [])
        x_key = w.get("x_key", "x")
        y_keys = w.get("y_keys", ["y"])
        if isinstance(y_keys, str):
            y_keys = [y_keys]
        series_lines = ", ".join(f'ChartSeries(data_key={yk!r}, label={yk!r})' for yk in y_keys)
        out = ['with Card():', '    with CardContent():', '        with Column(gap=2):']
        if title:
            out.append(f'            H3({title!r})')
        out += [
            f'            BarChart(data={data!r},',
            f'                     series=[{series_lines}],',
            f'                     x_axis={x_key!r}, show_legend={len(y_keys) > 1})',
        ]
        return out

    if kind == "ring":
        label = w.get("label", "")
        value = w.get("value", 0)
        try:
            value = max(0, min(100, int(value)))
        except Exception:
            value = 0
        suffix = w.get("suffix", "%")
        display = f"{value}{suffix}" if suffix else f"{value}"
        out = ['with Column(gap=2):']
        if label:
            out.append(f'    H3({label!r})')
        out.append(f'    Ring(value={value}, label={display!r})')
        return out

    if kind == "sparkline":
        values = w.get("values", [])
        title = w.get("title", "")
        out = ['with Card():', '    with CardContent():', '        with Column(gap=2):']
        if title:
            out.append(f'            H3({title!r})')
        out.append(f'            Sparkline(data={values!r})')
        return out

    if kind == "progress_list":
        items = w.get("items", [])
        title = w.get("title")
        out: list[str] = []
        if title:
            out += [f'H3({title!r})']
        out += ['with Column(gap=3):']
        for it in items:
            if not isinstance(it, dict):
                continue
            label = it.get("label", "")
            val = it.get("value", 0)
            try:
                val = max(0, min(100, int(val)))
            except Exception:
                val = 0
            out += [
                '    with Column(gap=1):',
                f'        Text({label!r})',
                f'        Progress(value={val})',
            ]
        return out

    if kind == "table":
        title = w.get("title", "")
        columns = w.get("columns", [])
        rows = w.get("rows", [])
        out = ['with Card():', '    with CardContent():', '        with Column(gap=2):']
        if title:
            out.append(f'            H3({title!r})')
        # Header row (bold)
        out.append('            with Row(gap=3):')
        if not columns:
            out.append('                pass')
        for col in columns:
            out.append(f'                H3({str(col)!r})')
        # Data rows
        for row in rows:
            out.append('            with Row(gap=3):')
            cells = row if isinstance(row, list) else [row.get(c, "") for c in columns]
            if not cells:
                out.append('                pass')
            for cell in cells:
                out.append(f'                Text({str(cell)!r})')
        return out

    if kind == "text":
        heading = w.get("heading") or w.get("title") or ""
        body = w.get("body") or w.get("content") or ""
        level = str(w.get("level", "h3")).lower()
        out = ['with Column(gap=1):']
        if heading:
            if level == "h1":
                out.append(f'    H1({heading!r})')
            elif level == "h2":
                out.append(f'    H2({heading!r})')
            else:
                out.append(f'    H3({heading!r})')
        if body:
            out.append(f'    Muted({body!r})')
        if not heading and not body:
            out.append('    Muted("(empty text widget)")')
        return out

    if kind == "badges":
        # Accept "items", "tags", or "labels" key for flexibility
        items = w.get("items") or w.get("tags") or w.get("labels") or []
        badge_title = w.get("title") or ""
        out = ['with Column(gap=2):']
        if badge_title:
            out.append(f'    Muted({badge_title!r})')
        out.append('    with Row(gap=2):')
        if not items:
            out.append('        Badge("N/A", variant="default")')
        for it in items:
            lbl = it.get("label", "") if isinstance(it, dict) else str(it)
            var = it.get("variant", "default") if isinstance(it, dict) else "default"
            out.append(f'        Badge({lbl!r}, variant={var!r})')
        return out

    return [f'Muted({f"Unknown widget kind: {kind!r}"!r})']


def _dashboard_template(title: str, tabs: list[dict]) -> str:
    if not tabs:
        tabs = [{"name": "Main", "widgets": [{"kind": "text", "heading": "Empty dashboard"}]}]

    ctx: dict = {"uid": 0}
    TAB_INDENT = " " * 24

    built_tabs: list[tuple[str, str, str]] = []
    for i, tab in enumerate(tabs):
        name = str(tab.get("name") or f"Tab {i+1}")
        value = _slug(tab.get("value") or name, f"tab_{i+1}")
        widgets = tab.get("widgets") or []
        body_lines: list[str] = []
        if not widgets:
            body_lines = [TAB_INDENT + 'Muted("(empty tab)")']
        else:
            for w in widgets:
                for line in _widget_lines(w, ctx):
                    body_lines.append((TAB_INDENT + line) if line else "")
        built_tabs.append((name, value, "\n".join(body_lines)))

    first_value = built_tabs[0][1]

    # Extract optional subtitle from template params
    subtitle = ""
    if isinstance(tabs, list) and len(tabs) > 0:
        # subtitle can be passed as a top-level param by the agent
        pass  # subtitle handled below via function arg

    parts = [
        "from prefab_ui.app import PrefabApp",
        "from prefab_ui.components import (",
        "    Badge, Button, Card, CardContent, CardHeader, CardTitle,",
        "    Checkbox, Column, H1, H2, H3, Muted, Progress, Ring, Row,",
        "    Tab, Tabs, Text,",
        ")",
        "from prefab_ui.components.charts import (",
        "    BarChart, ChartSeries, LineChart, PieChart, Sparkline,",
        ")",
        "from datetime import datetime",
        "",
        'with PrefabApp(css_class="max-w-5xl mx-auto p-6") as app:',
        "    with Card():",
        "        with CardHeader():",
        f"            CardTitle({title!r})",
        f"            Muted(f'Generated on {{datetime.now().strftime(\"%Y-%m-%d %H:%M\")}} by the Autonomous Intel Agent')",
        "        with CardContent():",
        f"            with Tabs(value={first_value!r}):",
    ]
    for name, value, body in built_tabs:
        parts.append(f'                with Tab({name!r}, value={value!r}):')
        parts.append("                    with Column(gap=5):")
        parts.append(body)
    
    parts.append("\n\nif __name__ == '__main__':")
    parts.append('    import sys')
    parts.append('    print("\\nThis is a Prefab UI dashboard definition.\\n")')
    parts.append('    print("To run it in your browser, use the prefab CLI:\\n")')
    parts.append('    print("    prefab serve sandbox/generated_app.py\\n")')
    parts.append('    sys.exit(1)')
    
    return "\n".join(parts) + "\n"


@mcp.tool()
def generate_ui(spec_json: str) -> str:
    """Push a generated UI spec to the Prefab dashboard file in the sandbox.
    Expects `spec_json` to be a valid JSON string mapping to:
    {
      "params": {
        "title": "Dashboard Title",
        "tabs": [
          { "name": "Tab Name", "widgets": [ ... ] }
        ]
      }
    }
    Supported widget kinds: stat, pie, bar, ring, sparkline, progress_list, table, text, badges.
    """
    try:
        spec = json.loads(spec_json)
        if isinstance(spec, str):
            spec = json.loads(spec)
        params = spec.get("params", {})
        title = params.get("title", "Generated Dashboard")
        tabs = params.get("tabs", [])

        source = _dashboard_template(title, tabs)

        # Syntax-check the generated code before writing
        compile(source, "<generated_app>", "exec")

        app_path = _safe_path("generated_app.py")
        app_path.write_text(source, encoding="utf-8")

        return f"Successfully generated UI dashboard and saved to {app_path.name}"
    except json.JSONDecodeError:
        return "Error: spec_json is not a valid JSON string."
    except SyntaxError as e:
        return f"Error: generated code has a syntax error: {e}"
    except Exception as e:
        return f"Error generating UI: {e}"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"STARTING IntelServer — sandbox at {SANDBOX}", file=sys.stderr)
    mcp.run(transport="stdio")
