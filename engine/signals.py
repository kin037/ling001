# -*- coding: utf-8 -*-
"""
信号分析引擎
========================

基于真实采集数据生成：
- 锂价信号（碳酸锂期货涨跌幅、持仓变化）
- A 股锂矿板块情绪
- 宏观风险（USD/CNH、FOMC）
- 数据健康度
"""


def is_number(value):
    return isinstance(value, (int, float))


def _pct(value):
    """把百分比数值规整为 float。"""
    return value if is_number(value) else None


def build_signals(snapshot):
    market = snapshot.get("market", {})
    lithium = snapshot.get("lithium", {})

    # =========================
    # 1. 锂价信号（碳酸锂期货）
    # =========================

    futures = (lithium.get("carbonate_futures") or {})
    main = futures.get("main_contract") or {}
    top = futures.get("top_contracts") or []

    main_last = main.get("last")
    main_change = _pct(main.get("change_pct"))
    main_volume = main.get("volume")
    main_oi = main.get("open_interest")

    lithium_signal = "neutral"
    lithium_note = "碳酸锂期货价格平稳。"

    if is_number(main_change):
        if main_change <= -2.0:
            lithium_signal = "bearish"
            lithium_note = (
                f"碳酸锂期货主力下跌 {main_change:.2f}%，"
                "价格走弱，留意供需恶化风险。"
            )
        elif main_change >= 2.0:
            lithium_signal = "bullish"
            lithium_note = (
                f"碳酸锂期货主力上涨 {main_change:.2f}%，"
                "价格走强，关注上涨持续性。"
            )
        else:
            lithium_note = (
                f"碳酸锂期货主力变动 {main_change:+.2f}%，"
                "价格区间震荡。"
            )

    # 持仓量变化无法跨日对比时仅记录绝对值
    lithium_price = {
        "main_last": main_last,
        "main_change_pct": main_change,
        "main_volume": main_volume,
        "main_open_interest": main_oi,
        "top_contracts": [
            {
                "contract": c.get("contract"),
                "last": c.get("last"),
                "change_pct": _pct(c.get("change_pct")),
                "open_interest": c.get("open_interest"),
            }
            for c in top
        ],
        "signal": lithium_signal,
        "note": lithium_note,
        "status": "confirmed" if is_number(main_last) else "error",
    }

    # =========================
    # 2. A 股锂矿板块情绪
    # =========================

    a_shares = market.get("a_shares_lithium") or {}
    up_count = 0
    total_count = 0
    changes = []

    for label, item in a_shares.items():
        if not isinstance(item, dict):
            continue
        pct = _pct(item.get("change_pct"))
        if pct is None:
            continue
        total_count += 1
        changes.append(pct)
        if pct > 0:
            up_count += 1

    sector_signal = "neutral"
    if total_count >= 2:
        avg_change = sum(changes) / len(changes)
        if avg_change >= 2.0:
            sector_signal = "bullish"
        elif avg_change <= -2.0:
            sector_signal = "bearish"

    sector = {
        "count": total_count,
        "up_count": up_count,
        "down_count": total_count - up_count,
        "avg_change_pct": (
            round(sum(changes) / len(changes), 2) if changes else None
        ),
        "signal": sector_signal,
        "status": "confirmed" if total_count else "missing",
    }

    # =========================
    # 3. 宏观风险
    # =========================

    cnh = market.get("usd_cnh") or {}
    cnh_change = _pct(cnh.get("change_pct"))

    macro_watch = {
        "cnh": (
            "watch"
            if is_number(cnh_change) and abs(cnh_change) >= 0.35
            else "normal"
        ),
        "fomc": "monitor",
    }

    # =========================
    # 4. 官方供应端数据健康度
    # =========================

    official = snapshot.get("official_supply") or {}
    asx_data = official.get("ASX") or {}
    confirmed_asx = sum(
        1 for v in asx_data.values()
        if isinstance(v, dict) and v.get("status") == "confirmed"
    )
    confirmed_ir = sum(
        1 for key in ("ALB", "SQM")
        if isinstance(official.get(key), dict)
        and official[key].get("status") == "confirmed"
    )

    # =========================
    # 5. 数据健康度汇总
    # =========================

    health_parts = []

    # 锂价
    if lithium_price["status"] == "confirmed":
        health_parts.append("锂价:OK")
    else:
        health_parts.append("锂价:MISSING")

    # A股
    health_parts.append(f"A股:{sector['status']}")

    # 官方供应端
    health_parts.append(
        f"ASX公告:{confirmed_asx}/5 IR:{confirmed_ir}/2"
    )

    # 汇率
    health_parts.append(
        "汇率:OK" if cnh.get("status") == "confirmed" else "汇率:MISSING"
    )

    data_health = {
        "lithium_price": lithium_price["status"],
        "a_shares": sector["status"],
        "asx_announcements": confirmed_asx,
        "ir_pages": confirmed_ir,
        "usd_cnh": cnh.get("status"),
        "summary": " | ".join(health_parts),
        "overall": "PARTIAL",
    }

    if (
        lithium_price["status"] == "confirmed"
        and sector["status"] == "confirmed"
        and cnh.get("status") == "confirmed"
        and confirmed_asx >= 1
    ):
        data_health["overall"] = "GOOD"

    # =========================
    # 6. 行动建议
    # =========================

    actions = []
    risk_actions = []

    if lithium_signal == "bearish":
        actions.append("🟠 锂价走弱：谨慎对待板块反弹，等待企稳信号。")
    elif lithium_signal == "bullish":
        actions.append("🟢 锂价走强：可关注产业链情绪修复，但需验证持续性。")

    if sector_signal == "bearish":
        risk_actions.append("A股锂矿板块整体下跌，短期情绪偏弱。")
    elif sector_signal == "bullish":
        actions.append("🔵 A股锂矿板块普涨，市场情绪回暖。")

    if macro_watch["cnh"] == "watch":
        risk_actions.append("USD/CNH出现较明显波动，注意汇率风险。")

    if lithium_price["status"] != "confirmed":
        risk_actions.append("核心锂价数据缺失，系统拒绝让AI自行补值。")

    action = " ".join(actions) if actions else "🟡 观望：暂无明显单边信号。"
    if risk_actions:
        action += " 风险提示：" + " ".join(risk_actions)

    return {
        "lithium_price": lithium_price,
        "sector": sector,
        "macro_watch": macro_watch,
        "action": action,
        "data_health": data_health,
        "industry_confirmed": False,
        "rules": [
            "预测排产不能等同实际开工率",
            "搜索新闻不能等同官方减产公告",
            "缺失数据不能让AI自行补全",
            "宏观指标只能用于风险过滤",
            "期货价格仅代表盘面预期，不等同于现货成交价",
        ],
    }
