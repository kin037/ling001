def is_number(value):

    return isinstance(
        value,
        (int, float)
    )


def build_signals(snapshot):

    market = snapshot["market"]

    cnh = market[
        "USD_CNH"
    ]

    cnh_value = cnh.get(
        "value"
    )

    cnh_change = cnh.get(
        "change_pct"
    )

    # -------------------------
    # 宏观风险
    # -------------------------

    macro_watch = {

        "cnh":

            "watch"

            if (
                is_number(cnh_change)
                and abs(cnh_change) >= 0.35
            )

            else "normal",

        "fomc":
            "monitor"
    }

    # -------------------------
    # 官方供应端数据健康度
    # -------------------------

    official_sources = [

        "ASX",
        "ALB",
        "SQM"
    ]

    confirmed = 0

    for source in official_sources:

        if (
            snapshot[
                "official_supply"
            ][source].get(
                "status"
            )
            == "confirmed"
        ):

            confirmed += 1

    # -------------------------
    # 核心开工率
    # -------------------------

    # 目前还没有可靠的结构化真实开工率。
    # 所以故意设置为 False。
    #
    # 这是为了防止 AI 自己“猜数据”。

    industry_confirmed = False

    # -------------------------
    # 数据健康度
    # -------------------------

    market_confirmed = sum(

        1

        for item in market.values()

        if item.get(
            "status"
        ) == "confirmed"
    )

    data_health = {

        "market":
            market_confirmed,

        "official_supply_pages":
            confirmed,

        "industry_operating_rate":
            "MISSING/UNVERIFIED",

        "overall":
            "PARTIAL"
    }

    # -------------------------
    # 行动建议
    # -------------------------

    action = (
        "🟡 观望："
        "核心锂产业真实开工率尚未得到结构化确认。"
    )

    if (
        macro_watch["cnh"]
        == "watch"
    ):

        action = (
            "🟠 降仓/暂缓："
            "USD/CNH出现较明显波动，"
            "同时核心锂产业数据尚未完整确认。"
        )

    return {

        "macro_watch":
            macro_watch,

        "action":
            action,

        "data_health":
            data_health,

        "industry_confirmed":
            industry_confirmed,

        "rules": [

            "预测排产不能等同实际开工率",

            "搜索新闻不能等同官方减产公告",

            "缺失数据不能让AI自行补全",

            "宏观指标只能用于风险过滤"
        ]
    }
