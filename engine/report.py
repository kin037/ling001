# -*- coding: utf-8 -*-
"""
报告生成引擎
========================

- 调用 DeepSeek API 生成分析（模型默认 deepseek-chat，可通过
  DEEPSEEK_MODEL 环境变量覆盖）
- API 不可用时自动降级为本地格式化报告（fallback）
- 严格遵守"缺失数据不能让 AI 自行补全"原则
"""

import json
import os

from datetime import datetime

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = """
你是锂产业链专业情报分析员。

你的任务不是创造数据，而是分析已经获得的数据。

必须遵守以下规则：

1. 不能自己补充缺失数字。
2. 不能把预测值写成实际值。
3. 不能把搜索新闻写成官方公告。
4. 必须区分数据状态：
   CONFIRMED（官方/交易所确认）
   DISCOVERY_ONLY（仅新闻线索）
   UNVERIFIED（未验证）
   MISSING（缺失）

5. 如果碳酸锂期货或现货价格缺失：必须明确告诉用户数据缺失。
6. 期货价格是盘面预期，不能等同于现货成交价。
7. 如果供应端减产没有官方来源：不得写成已经确认减产。
8. 如果宏观数据恶化：可以提出降仓或暂缓。
9. 不允许因为用户希望上涨，就人为解释成利好。

最终输出应该重点分析：

- 碳酸锂期货价格与变动（元/吨）
- A股锂矿板块表现（天齐锂业、赣锋锂业、盐湖股份等）
- 美股锂业公司（Albemarle、SQM、LAC）
- 离岸人民币 USD/CNH
- FOMC 会议日程
- ASX 锂矿公司官方公告（Pilbara、Mineral Resources 等）
- 行业新闻线索（仅作参考，不视为事实）
- 数据可信度与缺失项
- 仓位风险
"""


def deepseek_analyze(snapshot):
    """调用 DeepSeek API。返回 None 表示未配置 key。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 3000,
    }

    response = requests.post(
        DEEPSEEK_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# =========================================================
# 本地降级报告（无 AI key 或 API 失败时使用）
# =========================================================

def _fmt(value, suffix="", placeholder="--"):
    if value is None:
        return placeholder
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _lithium_section(lithium):
    """格式化锂价段落。"""
    futures = (lithium or {}).get("carbonate_futures") or {}
    main = futures.get("main_contract") or {}
    top = futures.get("top_contracts") or []

    if main.get("last") is None:
        return (
            "### 碳酸锂期货\n\n"
            "**数据缺失**：未能获取广期所碳酸锂期货行情。\n"
            "系统拒绝让 AI 自行补值。\n"
        )

    lines = [
        "### 碳酸锂期货（广期所）\n",
        f"- 主力连续（LC0）：**{_fmt(main.get('last'))} 元/吨**\n",
        f"- 当日变动：{_fmt(main.get('change_pct'), '%')}（相对昨结算价，期货标准口径）\n",
        f"- 开盘：{_fmt(main.get('open'))} ｜ "
        f"最高：{_fmt(main.get('high'))} ｜ "
        f"最低：{_fmt(main.get('low'))}\n",
        f"- 成交量：{_fmt(main.get('volume'), ' 手')} ｜ "
        f"持仓量：{_fmt(main.get('open_interest'), ' 手')}\n",
        f"- 行情日期：{main.get('date') or '--'}\n",
    ]

    if top:
        lines.append("\n活跃合约（按持仓量）：\n")
        for c in top:
            lines.append(
                f"- {c.get('contract')}：{_fmt(c.get('last'))} 元/吨"
                f"（{_fmt(c.get('change_pct'), '%')}，"
                f"持仓 {_fmt(c.get('open_interest'), ' 手')}）\n"
            )

    lines.append(
        "\n> 注：期货价格反映盘面预期，不等同于现货成交价；"
        "现货价未获得可靠公开源。\n"
    )
    return "".join(lines)


def _market_section(market):
    """格式化股市段落。"""
    lines = ["### 锂矿板块行情\n"]

    a_shares = (market or {}).get("a_shares_lithium") or {}
    if isinstance(a_shares, dict) and a_shares.get("error"):
        lines.append("- A股行情获取失败\n")
    else:
        for label, item in a_shares.items():
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {label}：{_fmt(item.get('last'))} 元"
                f"（{_fmt(item.get('change_pct'), '%')}）\n"
            )

    h_shares = (market or {}).get("h_shares_lithium") or {}
    for label, item in h_shares.items():
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {label}：{_fmt(item.get('last'))} 港元"
            f"（{_fmt(item.get('change_pct'), '%')}）\n"
        )

    us = (market or {}).get("us_stocks") or {}
    for name, item in us.items():
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status == "confirmed":
            lines.append(
                f"- {name}（美股）：${_fmt(item.get('value'))}"
                f"（{_fmt(item.get('change_pct'), '%')}）\n"
            )
        else:
            lines.append(f"- {name}（美股）：数据不可用\n")

    cnh = (market or {}).get("usd_cnh") or {}
    lines.append(
        f"- USD/CNH：{_fmt(cnh.get('value'))}"
        f"（{_fmt(cnh.get('change_pct'), '%')}）\n"
    )
    return "".join(lines)


def _official_section(official):
    """格式化官方公告段落。"""
    lines = ["### 官方供应端公告\n"]
    asx = (official or {}).get("ASX") or {}
    for code, item in asx.items():
        if not isinstance(item, dict):
            continue
        lines.append(f"**{code}**（{item.get('label', '')}）：\n")
        anns = item.get("announcements") or []
        if not anns:
            lines.append(f"- 状态：{item.get('status')}（{item.get('error') or '无公告'}）\n")
        for a in anns[:4]:
            sensitive = "🔴敏感" if a.get("price_sensitive") else ""
            lines.append(
                f"- [{a.get('date', '')[:10]}] {a.get('headline')} {sensitive}\n"
            )
    return "".join(lines)


def _macro_section(macro):
    """格式化宏观段落。"""
    lines = ["### 宏观（FOMC）\n"]
    fomc = (macro or {}).get("fomc") or {}
    meetings = fomc.get("meetings") or []
    if not meetings:
        lines.append(f"- 状态：{fomc.get('status')}（{fomc.get('error') or '未解析到会议'}）\n")
    for m in meetings:
        lines.append(
            f"- {m.get('month')} {m.get('dates')}：{m.get('status')}\n"
        )
    return "".join(lines)


def fallback_text(snapshot):
    """无 AI 时的本地降级报告。"""
    signals = snapshot.get("signals", {})
    lithium = snapshot.get("lithium")
    market = snapshot.get("market")
    official = snapshot.get("official_supply")
    macro = snapshot.get("macro")

    parts = [
        "> 本报告由本地规则引擎生成（未调用 AI 分析，仅展示真实采集数据）。\n",
        _lithium_section(lithium),
        _market_section(market),
        _official_section(official),
        _macro_section(macro),
        "### 信号与风险\n",
        f"- 行动建议：{signals.get('action', '--')}\n",
        f"- 数据健康度：{signals.get('data_health', {}).get('summary', '--')}\n",
    ]
    return "\n".join(parts)


# =========================================================
# 报告构建
# =========================================================

def build_report(snapshot):
    try:
        from zoneinfo import ZoneInfo
        china_tz = ZoneInfo("Asia/Shanghai")
    except Exception:
        from datetime import timezone, timedelta
        china_tz = timezone(timedelta(hours=8))

    now = datetime.now(china_tz)

    try:
        ai_result = deepseek_analyze(snapshot)
        if not ai_result:
            ai_result = fallback_text(snapshot)
    except Exception as e:
        ai_result = (
            "DeepSeek 分析失败，已自动切换为本地规则模式。\n\n"
            f"错误信息：{e}\n\n"
            + fallback_text(snapshot)
        )

    title = f"锂矿自动化情报日报｜{now:%Y-%m-%d %H:%M}"

    markdown = (
        f"# {title}\n\n"
        "## 一、分析结论\n\n"
        + ai_result
        + "\n\n"
        "## 二、数据真实性规则\n\n"
        "- 实际开工率没有来源就显示缺失。\n"
        "- 预测排产不能作为实际生产数据。\n"
        "- 境外减产必须寻找官方来源。\n"
        "- 期货价格不能等同现货价格。\n"
        "- USD/CNH 作为离岸人民币指标。\n"
        "- FOMC 以美联储官方信息为准。\n"
        "- AI 不得自行补充数据。\n"
    )

    return {
        "title": title,
        "generated_at": now.isoformat(),
        "markdown": markdown,
        "snapshot": snapshot,
    }
