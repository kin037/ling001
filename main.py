import json
import logging
import os
import sys

from datetime import datetime

from pathlib import Path

from zoneinfo import ZoneInfo

# Windows 控制台默认 GBK 无法打印 emoji，强制 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from collectors.market import collect_market
from collectors.macro import collect_macro
from collectors.official import collect_official_supply
from collectors.industry import collect_industry_discovery
from collectors.lithium import collect_lithium

from engine.signals import build_signals
from engine.report import build_report
from notify.pushplus import pushplus


def china_tz():
    """获取中国时区，Windows 无 tzdata 时回退 UTC+8。"""
    try:
        return ZoneInfo("Asia/Shanghai")
    except Exception:
        from datetime import timezone, timedelta
        return timezone(timedelta(hours=8))


CHINA_TZ = china_tz()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def now_china():
    return datetime.now(CHINA_TZ)


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    started = now_china()
    mode = os.getenv("REPORT_MODE", "daily")

    print("================================")
    print("🚀 锂矿自动化情报室 V3")
    print("================================")
    print("北京时间：", started)
    print("报告类型：", mode)

    # ============================
    # 1. 锂价数据（碳酸锂期货）
    # ============================

    logging.info("正在获取碳酸锂期货数据...")
    lithium = collect_lithium()

    # ============================
    # 2. 市场数据（A股/港股/汇率/美股）
    # ============================

    logging.info("正在获取市场数据...")
    market = collect_market()

    # ============================
    # 3. 宏观数据（FOMC）
    # ============================

    logging.info("正在获取宏观数据...")
    macro = collect_macro()

    # ============================
    # 4. 官方供应端（ASX 公告）
    # ============================

    logging.info("正在检查官方供应端公告...")
    official = collect_official_supply()

    # ============================
    # 5. 行业情报发现
    # ============================

    logging.info("正在扫描行业情报...")
    industry = collect_industry_discovery()

    # ============================
    # 6. 汇总快照
    # ============================

    snapshot = {
        "meta": {
            "generated_at": started.isoformat(),
            "timezone": "Asia/Shanghai",
            "mode": mode,
            "system_version": "3.0",
        },
        "lithium": lithium,
        "market": market,
        "macro": macro,
        "official_supply": official,
        "industry": industry,
    }

    # ============================
    # 7. 信号分析
    # ============================

    signals = build_signals(snapshot)
    snapshot["signals"] = signals

    # ============================
    # 8. 保存原始数据
    # ============================

    save_json(Path("data/latest.json"), snapshot)

    # ============================
    # 9. DeepSeek 生成报告
    # ============================

    report = build_report(snapshot)

    # ============================
    # 10. 保存报告
    # ============================

    report_path = (
        Path("data/reports")
        / f"{started:%Y-%m-%d}_{mode}.json"
    )
    save_json(report_path, report)

    # ============================
    # 11. 微信推送
    # ============================

    pushplus(report["title"], report["markdown"])

    print("================================")
    print("✅ 情报日报生成完成")
    print("数据健康度：", signals["data_health"]["summary"])
    print("行动建议：", signals["action"])
    print("报告文件：", report_path)
    print("================================")


if __name__ == "__main__":
    main()
