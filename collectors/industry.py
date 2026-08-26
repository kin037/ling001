# -*- coding: utf-8 -*-
"""
行业情报发现采集器
========================

数据源（双路冗余）：

1. Bing News RSS（实测可用，中文新闻正常）
   https://www.bing.com/news/search?q=...&format=rss

2. Google News RSS（备选）
   https://news.google.com/rss/search?q=...

RSS 搜索结果只能作为线索，不能直接作为真实开工率 ——
这与本项目"缺失数据不能让 AI 自行补全"的规则一致。
"""

import os

from datetime import datetime, timezone

from urllib.parse import quote

from xml.etree import ElementTree

from collectors.http import safe_get_text

BING_RSS = (
    "https://www.bing.com/news/search?"
    "q={query}"
    "&format=rss"
    "&setlang=zh-hans"
)

GOOGLE_RSS = (
    "https://news.google.com/rss/search?"
    "q={query}"
    "&hl=zh-CN"
    "&gl=CN"
    "&ceid=CN:zh-Hans"
)

QUERIES = {
    "battery_operating_rate": os.getenv(
        "INDUSTRY_QUERY_1",
        "锂电池 碳酸锂 价格 开工率",
    ),
    "lithium_supply": os.getenv(
        "INDUSTRY_QUERY_2",
        "锂盐 碳酸锂 减产 供应",
    ),
    "lithium_price": os.getenv(
        "INDUSTRY_QUERY_3",
        "碳酸锂 价格 期货 现货",
    ),
}


def _parse_rss(xml_text, source_url):
    """解析 RSS XML，返回条目列表。"""
    root = ElementTree.fromstring(xml_text)
    items = []
    for item in root.findall(".//item")[:10]:
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "description": ((item.findtext("description") or "")[:1000]),
        })
    return items


def news_rss(query, source="bing"):
    """从指定 RSS 源搜索行业新闻。"""
    if source == "bing":
        url = BING_RSS.format(query=quote(query))
    else:
        url = GOOGLE_RSS.format(query=quote(query))

    xml_text, error = safe_get_text(url, timeout=20, retries=2)

    if not xml_text:
        return {
            "status": "error",
            "source": "Bing News" if source == "bing" else "Google News",
            "source_url": url,
            "error": error,
        }

    try:
        items = _parse_rss(xml_text, url)
        return {
            "status": "discovery_only",
            "source": "Bing News" if source == "bing" else "Google News",
            "source_url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
            "warning": "RSS搜索结果只能作为线索，不能直接作为真实开工率。",
        }
    except Exception as e:
        return {
            "status": "error",
            "source": "Bing News" if source == "bing" else "Google News",
            "source_url": url,
            "error": str(e),
        }


def collect_industry_discovery():
    """行业情报：Bing 为主源，Google 为辅（双路冗余）。"""
    result = {}

    for key, query in QUERIES.items():
        bing = news_rss(query, source="bing")
        google = news_rss(query, source="google")

        # Bing 失败时回退 Google
        if bing.get("status") == "error" and google.get("status") != "error":
            result[key] = google
        else:
            result[key] = bing
            if google.get("status") != "error":
                result[key]["fallback_items"] = google.get("items", [])[:5]

    return result
