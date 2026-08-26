# -*- coding: utf-8 -*-
"""
宏观数据采集器
========================

数据源：美联储 FOMC 官方日历页面
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

页面结构（实测）：
    <div class="row fomc-meeting">
        <div class="fomc-meeting__month"><strong>January</strong></div>
        <div class="fomc-meeting__date">27-28</div>
        ...
    </div>

解析出每年每次会议的月份 / 日期 / 状态（是否已过）。
"""

import calendar

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.http import safe_get_text

FOMC_URL = (
    "https://www.federalreserve.gov/"
    "monetarypolicy/fomccalendars.htm"
)

MONTH_MAP = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}


def _parse_meeting_rows(soup, year):
    """解析指定年份的 FOMC 会议。"""
    meetings = []
    # 年份标题形如 "2026 FOMC Meetings" 的 <h4>
    heading = None
    for h4 in soup.find_all("h4"):
        text = " ".join(h4.stripped_strings)
        if str(year) in text and "FOMC" in text:
            heading = h4
            break
    if not heading:
        return meetings
    panel = heading.find_parent("div", class_="panel")
    if not panel:
        return meetings

    now_utc = datetime.now(timezone.utc)

    for row in panel.select(".fomc-meeting"):
        month_el = row.select_one(".fomc-meeting__month")
        date_el = row.select_one(".fomc-meeting__date")
        if not month_el or not date_el:
            continue
        month = " ".join(month_el.stripped_strings).strip().lower()
        date_range = " ".join(date_el.stripped_strings).strip()
        month_num = MONTH_MAP.get(month)

        # 会议日期状态（按会议区间最后一天判断是否已结束）
        status = "unknown"
        try:
            clean_range = date_range.replace("*", "").strip()
            if "-" in clean_range:
                start_day, end_day = clean_range.split("-", 1)
                end_day = int(end_day.strip())
            else:
                end_day = int(clean_range.strip())
            meeting_end = datetime(
                year, month_num or 1, end_day,
                tzinfo=timezone.utc,
            )
            status = "past" if meeting_end < now_utc else "upcoming"
        except (ValueError, TypeError):
            pass

        meetings.append({
            "month": month.capitalize(),
            "dates": date_range,
            "status": status,
        })

    return meetings


def collect_fomc():
    """抓取并解析 FOMC 会议日历。"""
    html, error = safe_get_text(FOMC_URL, timeout=25)

    if not html:
        return {
            "source": "Federal Reserve",
            "source_url": FOMC_URL,
            "status": "error",
            "error": error,
            "meetings": [],
        }

    soup = BeautifulSoup(html, "html.parser")

    now = datetime.now()
    years = [now.year, now.year + 1]

    meetings = []
    for year in years:
        meetings.extend(_parse_meeting_rows(soup, year))

    return {
        "source": "Federal Reserve",
        "source_url": FOMC_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed" if meetings else "partial",
        "meetings": meetings,
        "note": "会议时间以美联储官方FOMC页面为准。",
    }


def collect_macro():
    return {
        "fomc": collect_fomc(),
    }
