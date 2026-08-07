import os
import sys
import logging
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_data():
    logging.info("开始生成模拟数据...")
    return {
        "macro": {
            "cny": "6.78（离岸人民币兑美元）",
            "fed_rate": "56.9% 概率加息",
            "verdict": "🟡 观望",
            "position": "70% 仓位"
        },
        "prices": {
            "smm": "14.15",
            "futures": "14.00",
            "basis": "+0.15"
        },
        "util": {"signal": "🟢 8月排产+8%"},
        "inventory": {"change": "🟢 去库6773吨"},
        "overseas": {"conclusion": "ALB财报超预期，无突发减产"}
    }

def generate_report(data):
    now = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    return f"""
# 锂矿狙击手 · 每日情报简报
**时间：** {now}

## 宏观
- 汇率：{data['macro']['cny']}
- 美联储：{data['macro']['fed_rate']}
- 裁定：{data['macro']['verdict']}，{data['macro']['position']}

## 产业
- 现货：{data['prices']['smm']}万/吨 | 期货：{data['prices']['futures']}万/吨
- 基差：{data['prices']['basis']}
- 需求：{data['util']['signal']}
- 库存：{data['inventory']['change']}
- 海外：{data['overseas']['conclusion']}

## 建议
宏观🟡 + 需求🟢 + 库存🟢 → 逢低关注，止损-5%
---
*自动化生成 | 明日16:30更新*
"""

def push_to_wechat(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        logging.warning("未设置Token，仅打印报告：\n" + content)
        return
    try:
        import requests
        resp = requests.post(
            "https://www.pushplus.plus/send",
            json={"token": token, "title": "锂矿情报日报", "content": content, "template": "markdown"},
            timeout=10
        )
        if resp.status_code == 200:
            logging.info("✅ 微信推送成功！")
        else:
            logging.error(f"推送失败：{resp.text}")
    except Exception as e:
        logging.error(f"网络异常：{e}")

if __name__ == "__main__":
    try:
        data = fetch_data()
        report = generate_report(data)
        push_to_wechat(report)
        logging.info("脚本执行完毕。")
    except Exception as e:
        logging.error("程序异常：" + str(e))
        sys.exit(1)
