"""Collect RSS news items for the morning briefing.

Uses configured RSS feeds only. No fake news is generated. The output is a
compact JSON that Research AI/n8n can summarize and send to Telegram.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import argparse
import html
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "news_sources.json"


def clean_text(text: str | None) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_dt(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return clean_text(text) or None


def fetch_rss(source: dict[str, Any], *, limit: int) -> tuple[list[dict[str, Any]], str | None]:
    url = str(source.get("url") or "")
    if not url:
        return [], "missing_source_url"
    req = Request(url, headers={"User-Agent": "HermesTradingBot/1.0 (+https://github.com/robeldojune-star/juneCLaw)"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read()
    except HTTPError as exc:
        return [], f"http_{exc.code}_{source.get('id')}"
    except URLError as exc:
        return [], f"url_error_{source.get('id')}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}_{source.get('id')}: {exc}"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [], f"rss_parse_error_{source.get('id')}: {exc}"

    items: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:limit]:
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        desc = clean_text(item.findtext("description"))
        pub = parse_dt(item.findtext("pubDate"))
        if not title:
            continue
        items.append(
            {
                "source_id": source.get("id"),
                "source_name": source.get("name"),
                "category": source.get("category"),
                "title": title,
                "link": link,
                "published_at": pub,
                "summary_preview": desc[:240],
            }
        )
    return items, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--per-source-limit", type=int, default=5)
    parser.add_argument("--total-limit", type=int, default=25)
    args = parser.parse_args()

    config_path = Path(args.config)
    blocks: list[str] = []
    if not config_path.exists():
        blocks.append("news_sources_config_missing")
        config = {"sources": []}
    else:
        config = json.loads(config_path.read_text(encoding="utf-8"))

    all_items: list[dict[str, Any]] = []
    source_errors: list[str] = []
    for source in config.get("sources", []):
        if source.get("type") != "rss":
            continue
        items, error = fetch_rss(source, limit=args.per_source_limit)
        all_items.extend(items)
        if error:
            source_errors.append(error)

    # Deduplicate by title/link while preserving order.
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in all_items:
        key = (str(item.get("title")), str(item.get("link")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    deduped = deduped[: args.total_limit]

    if not deduped:
        blocks.append("no_news_items_collected")

    out = {
        "ok": not blocks,
        "workflow": "daily_trading_workflow_v1",
        "stage": "news_collector_rss",
        "status": "completed" if not blocks else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "configured_source_count": len(config.get("sources", [])),
            "collected_item_count": len(deduped),
            "source_error_count": len(source_errors),
        },
        "items": deduped,
        "source_errors": source_errors,
        "blocking_conditions": list(dict.fromkeys(blocks)),
        "alerts": ["some_news_sources_failed"] if source_errors and deduped else [],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
