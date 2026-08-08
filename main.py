import json
import logging

import os

from datetime import datetime

from pathlib import Path

from zoneinfo import ZoneInfo


from collectors.market import (
    collect_market
)

from collectors.macro import (
    collect_macro
)

from collectors.official import (
    collect_official_supply
)

from collectors.industry import (
    collect_industry_discovery
)

from engine.signals import (
    build_signals
)

from engine.report import (
    build_report
)

from notify.pushplus import (
    pushplus
)


CHINA_TZ = ZoneInfo(
    "Asia/Shanghai"
)


logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(message)s"
    )
)


def now_china():

    return datetime.now(
        CHINA_TZ
    )


def save_json(
    path,
    payload
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(

        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"
    )


def main():

    started = now_china()

    mode = os.getenv(
        "REPORT_MODE",
        "daily"
    )

    print(
        "================================"
    )

    print(
        "🚀 锂矿自动化情报室 V2"
    )

    print(
        "================================"
    )

    print(
        "北京时间：",
        started
    )

    print(
        "报告类型：",
        mode
    )

    # ============================
    # 1. 市场数据
    # ============================

    logging.info(
        "正在获取市场数据..."
    )

    market = collect_market()

    # ============================
    # 2. 宏观数据
    # ============================

    logging.info(
        "正在获取宏观数据..."
    )

    macro = collect_macro()

    # ============================
    # 3. 官方供应端
    # ============================

    logging.info(
        "正在检查官方供应端公告..."
    )

    official = (
        collect_official_supply()
    )

    # ============================
    # 4. 行业情报发现
    # ============================

    logging.info(
        "正在扫描行业情报..."
    )

    industry = (
        collect_industry_discovery()
    )

    # ============================
    # 5. 汇总
    # ============================

    snapshot = {

        "meta": {

            "generated_at":
                started.isoformat(),

            "timezone":
                "Asia/Shanghai",

            "mode":
                mode,

            "system_version":
                "2.0"
        },

        "market":
            market,

        "macro":
            macro,

        "official_supply":
            official,

        "industry":
            industry
    }

    # ============================
    # 6. 信号分析
    # ============================

    signals = build_signals(
        snapshot
    )

    snapshot[
        "signals"
    ] = signals

    # ============================
    # 7. 保存原始数据
    # ============================

    save_json(

        Path(
            "data/latest.json"
        ),

        snapshot
    )

    # ============================
    # 8. DeepSeek生成报告
    # ============================

    report = build_report(
        snapshot
    )

    # ============================
    # 9. 保存报告
    # ============================

    report_path = Path(
        "data/reports"
    ) / (
        f"{started:%Y-%m-%d}"
        f"_{mode}.json"
    )

    save_json(
        report_path,
        report
    )

    # ============================
    # 10. 微信推送
    # ============================

    pushplus(

        report["title"],

        report["markdown"]
    )

    print(
        "================================"
    )

    print(
        "✅ 情报日报生成完成"
    )

    print(
        "数据健康度：",
        signals[
            "data_health"
        ][
            "overall"
        ]
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
