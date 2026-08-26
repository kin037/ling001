# -*- coding: utf-8 -*-
"""
官方供应端公告采集器
========================

数据源：

1. ASX 澳大利亚证券交易所官方公告 API（Markit Digital）
   https://asx.api.markitdigital.com/asx-research/1.0/companies/{CODE}/announcements
   返回真实公告 JSON：headline / date / announcementType / isPriceSensitive

2. Albemarle / SQM 投资者关系页面（静态 HTML 抓取，动态页面可能失败，
   失败时明确标注 error，绝不编造数据）
"""

from datetime import datetime, timezone

import requests

from collectors.http import safe_get_text

# =========================================================
# ASX 官方公告 API
# =========================================================

ASX_API = (
    "https://asx.api.markitdigital.com/asx-research/1.0/"
    "companies/{code}/announcements"
    "?fields=code,announcement-date,date,file-type,headline,"
    "id,market-sensitive,page,price-sensitive,release-date,type,url"
)

# 重点关注 ASX 锂矿公司
ASX_LITHIUM_CODES = {
    "PLS": "Pilbara Minerals（皮尔巴拉矿业）",
    "MIN": "Mineral Resources（矿产资源）",
    "IGO": "IGO Limited（天齐澳洲合资方）",
    "LTR": "Lithium Plus Minerals",
    "CXO": "Core Lithium（核心锂业）",
}

ASX_HEADERS = {
    "Referer": "https://www.asx.com.au/",
    "Accept": "application/json",
}


def collect_asx_announcements(code="PLS", label=None, limit=8):
    """抓取单一 ASX 公司的近期公告。"""
    label = label or code
    url = ASX_API.format(code=code)

    try:
        response = requests.get(url, headers=ASX_HEADERS, timeout=25)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        return {
            "code": code,
            "label": label,
            "source_url": f"https://www.asx.com.au/companies/{code}",
            "status": "error",
            "error": str(e),
            "announcements": [],
        }

    data = payload.get("data") or {}
    items = data.get("items") or []

    announcements = []
    for item in items[:limit]:
        announcements.append({
            "headline": item.get("headline"),
            "date": item.get("date"),
            "type": item.get("announcementType"),
            "price_sensitive": item.get("isPriceSensitive"),
            "file_size": item.get("fileSize"),
        })

    return {
        "code": code,
        "label": label,
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed" if announcements else "missing",
        "announcements": announcements,
    }


def collect_asx():
    """ASX 锂矿板块公告总采集。"""
    result = {}
    for code, label in ASX_LITHIUM_CODES.items():
        result[code] = collect_asx_announcements(code, label)
    return result


# =========================================================
# 美股锂业公司 IR（容错）
# =========================================================

ALB_IR = (
    "https://investors.albemarle.com/"
    "news-and-events/news/default.aspx"
)

SQM_IR = (
    "https://ir.sqm.com/"
    "news-events/news"
)


def extract_news_titles(html, limit=10):
    """从 IR 页面提取疑似新闻标题（过滤导航文字）。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # 常见 IR 新闻容器的 class / id 关键字
    container_selectors = [
        ".module-news",
        ".news",
        "#news",
        ".latest-news",
        ".news-list",
        ".newsitems",
        ".article",
        "[class*='news-item']",
        "[class*='NewsItem']",
        "[class*='news']",
    ]

    candidates = []
    seen = set()

    for selector in container_selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        for node in nodes:
            for a in node.find_all("a", href=True):
                title = " ".join(a.stripped_strings)
                if title and len(title) >= 12 and title not in seen:
                    seen.add(title)
                    candidates.append({
                        "title": title[:240],
                        "href": a["href"],
                    })

    return candidates[:limit]


def fetch_ir_page(name, url):
    """抓取 IR 页面。动态渲染页面可能失败，失败明确标注。"""
    html, error = safe_get_text(url, timeout=15, retries=1)

    if not html:
        return {
            "name": name,
            "source_url": url,
            "status": "error",
            "error": error or "页面获取失败（可能为动态渲染页面）",
            "titles": [],
        }

    titles = extract_news_titles(html)

    return {
        "name": name,
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed" if titles else "missing",
        "note": "IR页面多为动态渲染，若标题为空表示未能解析出新闻条目。",
        "titles": titles,
    }


def collect_official_supply():
    return {
        "ASX": collect_asx(),
        "ALB": fetch_ir_page("Albemarle Investor Relations", ALB_IR),
        "SQM": fetch_ir_page("SQM Investor Relations", SQM_IR),
        "verification_rule": (
            "供应端减产信息只有在官方来源中找到原始证据后"
            "才允许标记为 VERIFIED。"
        ),
    }
