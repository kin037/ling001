import os
import sys
import json
import logging
import re
from datetime import datetime
# 【修复1】彻底移除 pytz，改用 Python 自带的 zoneinfo
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo 

import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- 1. 真实宏观数据（汇率）----------
def fetch_real_macro():
    macro_data = {
        "cny": "--",
        "verdict": "🟡 观望",
        "position": "建议 50% 仓位"
    }
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        cny_rate = data.get("usd", {}).get("cny")
        if cny_rate:
            macro_data["cny"] = f"{cny_rate}"
            # 简单逻辑：汇率破7.3偏空
            if cny_rate > 7.3:
                macro_data["verdict"] = "🔴 偏空"
                macro_data["position"] = "建议 30% 仓位"
            else:
                macro_data["verdict"] = "🟢 偏稳"
                macro_data["position"] = "建议 70% 仓位"
    except Exception as e:
        logging.warning(f"汇率获取失败: {e}")
    return macro_data

# ---------- 2. 真实锂价数据（国内现货+期货）----------
def fetch_real_lithium_prices():
    price_data = {"smm": "--", "futures": "--", "basis": "--"}
    
    # 2.1 现货 (SMM) - 保持原有逻辑，若失败则留空
    try:
        smm_url = "https://hq.smm.cn/price"
        resp = requests.get(smm_url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        price_match = re.search(r'电池级碳酸锂.*?(\d+[,.]?\d+?)\s*元', resp.text, re.DOTALL)
        if price_match:
            raw = price_match.group(1).replace(',', '')
            price_yuan = float(raw) / 10000
            price_data["smm"] = f"{price_yuan:.2f}"
    except Exception as e:
        logging.warning(f"SMM现货抓取失败: {e}")

    # 2.2 期货 (东方财富)
    try:
        future_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=106.LC9999&fields=f43,f44,f45,f46"
        resp = requests.get(future_url, timeout=10)
        data = resp.json()
        if data.get("data") and data["data"].get("f43"):
            price_yuan = float(data["data"]["f43"]) / 10000
            price_data["futures"] = f"{price_yuan:.2f}"
    except Exception as e:
        logging.warning(f"期货价抓取失败: {e}")

    # 2.3 计算基差
    try:
        if price_data["smm"] != "--" and price_data["futures"] != "--":
            basis = float(price_data["smm"]) - float(price_data["futures"])
            price_data["basis"] = f"{basis:+.2f}"
    except:
        pass
    
    return price_data

# ---------- 3. 【新增】海外锂矿股监控 (Finnhub + Yahoo 双备份) ----------
def fetch_overseas_stocks():
    stocks_info = {}
    symbols = ["ALB", "LAC", "SQM"]
    
    # --- 方案 A: 尝试 Finnhub (需要 Key) ---
    api_key = os.environ.get("FINNHUB_API_KEY")
    if api_key:
        for symbol in symbols:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                resp = requests.get(url, timeout=8)
                data = resp.json()
                if 'c' in data and data['c'] != 0:
                    change_pct = data.get('d', 0) / data.get('c', 1) * 100
                    stocks_info[symbol] = f"${data['c']:.2f} ({change_pct:+.2f}%)"
                    continue # 成功则跳过方案 B
            except Exception as e:
                logging.warning(f"Finnhub 获取 {symbol} 失败: {e}")
    else:
        logging.info("未检测到 FINNHUB_API_KEY，将直接使用 Yahoo Finance 备用源。")

    # --- 方案 B: 备用 Yahoo Finance (无需 Key，GitHub Actions 兼容性好) ---
    # 检查哪些还没获取到
    missing_symbols = [s for s in symbols if s not in stocks_info]
    
    if missing_symbols:
        try:
            # 使用 crumb 机制或简单的正则抓取 Yahoo Finance 页面
            # 这里使用一个公开的聚合接口作为备选，或者模拟浏览器请求
            headers = {"User-Agent": "Mozilla/5.0"}
            for symbol in missing_symbols:
                # 使用 query1.finance.yahoo.com 接口
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
                resp = requests.get(url, headers=headers, timeout=10)
                data = resp.json()
                result = data['chart']['result'][0]
                meta = result['meta']
                price = meta['regularMarketPrice']
                prev_close = meta['previousClose']
                change_pct = (price - prev_close) / prev_close * 100
                stocks_info[symbol] = f"${price:.2f} ({change_pct:+.2f}%)"
                logging.info(f"Yahoo Finance 获取 {symbol} 成功: {stocks_info[symbol]}")
        except Exception as e:
            logging.error(f"Yahoo Finance 备用源也失败了: {e}")
            for s in missing_symbols:
                stocks_info[s] = "数据获取失败"

    return stocks_info

# ---------- 4. 核心数据整合 ----------
def fetch_data():
    logging.info("开始抓取全部数据...")
    macro = fetch_real_macro()
    prices = fetch_real_lithium_prices()
    overseas_stocks = fetch_overseas_stocks()
    
    # 构造海外动态文本
    overseas_text_parts = []
    for symbol, info in overseas_stocks.items():
        overseas_text_parts.append(f"{symbol}: {info}")
    overseas_conclusion = " | ".join(overseas_text_parts) if overseas_text_parts else "暂无数据"

    return {
        "macro": macro,
        "prices": prices,
        "overseas_stocks": overseas_stocks,
        "overseas_conclusion": overseas_conclusion,
        # 模拟数据保留
        "util": "🟢 8月排产+8%（模拟）",
        "inventory": "🟢 去库6773吨（模拟）"
    }

# ---------- 5. DeepSeek AI 分析 ----------
def fetch_ai_analysis(data):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "（未配置 AI Key，无法生成研判）"
    
    try:
        prompt = f"""
你是锂电分析师。基于以下数据给出50字内研判：
汇率：{data['macro']['cny']}
锂现货：{data['prices']['smm']}万
锂期货：{data['prices']['futures']}万
基差：{data['prices']['basis']}
海外锂股：{data['overseas_conclusion']}
排产：{data['util']}
库存：{data['inventory']}
只输出结论。
"""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat", # 建议使用 deepseek-chat 或 deepseek-v3
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 200
        }
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"AI调用失败: {resp.status_code}"
    except Exception as e:
        return f"AI异常: {str(e)}"

# ---------- 6. 生成报告 ----------
def generate_report(data, ai_text):
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    return f"""
# 锂矿狙击手 · 每日情报简报
**时间：** {now}

## 一、宏观避雷针
- 人民币汇率：**{data['macro']['cny']}**
- 综合裁定：**{data['macro']['verdict']}**，{data['macro']['position']}

## 二、主战场（锂价）
- 现货：**{data['prices']['smm']}** 万元/吨
- 期货：**{data['prices']['futures']}** 万元/吨
- 基差：**{data['prices']['basis']}**

## 三、海外风向标（美股锂矿）
- {data['overseas_conclusion']}

## 四、供需与库存
- 需求：{data['util']}
- 库存：{data['inventory']}

## 五、🤖 AI 综合研判
{ai_text}

---
*数据来源：SMM, EastMoney, Finnhub/Yahoo Finance*
"""

# ---------- 7. 微信推送 ----------
def push_to_wechat(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print(content) # 没Token直接打印
        return
    try:
        resp = requests.post(
            "https://www.pushplus.plus/send",
            json={"token": token, "title": "锂矿情报日报", "content": content, "template": "markdown"},
            timeout=10
        )
        logging.info(f"推送结果: {resp.text}")
    except Exception as e:
        logging.error(f"推送异常: {e}")

# ---------- 8. 启动 ----------
if __name__ == "__main__":
    try:
        data = fetch_data()
        ai_text = fetch_ai_analysis(data)
        report = generate_report(data, ai_text)
        push_to_wechat(report)
        logging.info("✅ 任务执行完毕。")
    except Exception as e:
        logging.error(f"程序崩溃: {e}", exc_info=True)
        sys.exit(1)
