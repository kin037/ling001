import requests
import json
import os
from datetime import datetime
import pytz

# ---------- 1. 模拟抓取数据（现阶段先跑通，之后再替换成真实网址）----------
def fetch_data():
    print("开始抓取数据（模拟模式）...")
    # 为了让你第一步就能成功，这里全是预设的可靠数据
    return {
        "macro": {
            "cny": "6.78（离岸人民币兑美元）",
            "fed_rate": "56.9% 概率加息25个基点",
            "verdict": "🟡 观望（加息预期压制）",
            "position": "建议 70% 仓位"
        },
        "prices": {
            "smm": "14.15",
            "futures": "14.00",
            "basis": "+0.15（现货升水）"
        },
        "util": {
            "signal": "🟢 需求确认（8月排产环比+8%）"
        },
        "inventory": {
            "change": "🟢 去库 6,773 吨",
            "trend": "偏多"
        },
        "overseas": {
            "conclusion": "无突发减产，ALB财报超预期"
        }
    }

# ---------- 2. 生成报告（你指定的模板）----------
def generate_report(data):
    now = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    return f"""
# 锂矿狙击手 · 每日情报简报
**报告时间：** {now}（北京时间）

## 一、正上方·宏观避雷针
- 汇率：{data['macro']['cny']}
- 美联储：{data['macro']['fed_rate']}
- 裁定：{data['macro']['verdict']}，{data['macro']['position']}

## 二、左侧·主战场预警
- 现货价：{data['prices']['smm']} 万元/吨
- 期货价：{data['prices']['futures']} 万元/吨
- 基差：{data['prices']['basis']}
- 需求信号：{data['util']['signal']}
- 库存动态：{data['inventory']['change']}

## 三、右侧·核实区
- 海外动态：{data['overseas']['conclusion']}

## 四、今日总参谋
信号共振：宏观🟡 + 需求🟢 + 库存🟢  
操作建议：逢低关注，止损设 -5%。
---
*本报告由自动化系统生成*  
*下次更新：明天 16:30*
"""

# ---------- 3. 推送到微信（通过PushPlus）----------
def push_to_wechat(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("警告：未设置 PUSHPLUS_TOKEN，报告如下：")
        print(content)
        return
    url = "https://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": "锂矿情报日报",
        "content": content,
        "template": "markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("推送成功！")
        else:
            print("推送失败", resp.text)
    except Exception as e:
        print("网络错误", e)

# ---------- 4. 启动 ----------
if __name__ == "__main__":
    data = fetch_data()
    report = generate_report(data)
    push_to_wechat(report)
