import os
import sys
import json
import logging
import re
import warnings
from datetime import datetime

# 【修复1】彻底移除 pytz，改用 Python 自带的 zoneinfo
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo 

import requests
# 关闭 SSL 警告，防止 Actions 环境报错
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 【修复2】全局伪装浏览器头，这是解决 GitHub Actions 403 错误的关键
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

# ---------- 1. 真实宏观数据（汇率）----------
def fetch_real_macro():
    macro_data = {
        "cny": "-- (获取失败)",
        "verdict": "🟡 观望",
        "position": "建议 50% 仓位"
    }
    
    # 尝试方案 A: jsdelivr (通常较快)
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            rate = resp.json().get("usd", {}).get("cny")
            if rate:
                macro_data["cny"] = f"{rate:.4f}"
                logging.info(f"✅ 汇率获取成功 (Source A): {rate}")
                return macro_data
    except Exception as e:
        logging.warning(f"⚠️ 汇率源 A 失败: {e}")

    # 尝试方案 B: 备用接口
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            rate = resp.json().get("rates", {}).get("CNY")
            if rate:
                macro_data["cny"] = f"{rate:.4f}"
                logging.info(f"✅ 汇率获取成功 (Source B): {rate}")
    except Exception as e:
        logging.error(f"❌ 汇率获取彻底失败: {e}")
        
    return macro_data

# ---------- 2. 海外锂矿股监控（Finnhub + 备用）----------
def fetch_overseas_stocks():
    stocks = {
        "ALB": {"price": "--", "change": "--"},
        "LAC": {"price": "--", "change": "--"},
        "SQM": {"price": "--", "change": "--"}
    }
    
    api_key = os.environ.get("FINNHUB_API_KEY")
    
    # 策略 A: 使用 Finnhub API
    if api_key:
        logging.info("🔍 检测到 Finnhub Key，正在尝试获取美股数据...")
        for symbol in ["ALB", "LAC", "SQM"]:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                data = resp.json()
                
                # Finnhub 返回 c (当前价格), d (涨跌额), dp (涨跌幅)
                if data.get("c") and data["c"] > 0:
                    stocks[symbol]["price"] = f"${data['c']:.2f}"
                    sign = "+" if data['d'] >= 0 else ""
                    stocks[symbol]["change"] = f"{sign}{data['d']:.2f} ({sign}{data['dp']:.2f}%)"
                    logging.info(f"✅ {symbol} (Finnhub): {stocks[symbol]['price']}")
                else:
                    logging.warning(f"⚠️ {symbol} 市场休市或数据无效")
            except Exception as e:
                logging.error(f"❌ {symbol} (Finnhub) 失败: {e}")
    else:
        logging.warning("⚠️ 未检测到 FINNHUB_API_KEY，跳过 Finnhub 获取。")

    # 策略 B: 如果上面全是 "--"，尝试用 yfinance 逻辑（模拟网页抓取，无需Key）
    # 注意：GitHub Actions 有时也会封锁 yfinance，这里做一个简单的尝试
    all_failed = all(v["price"] == "--" for v in stocks.values())
    
    if all_failed and not api_key: 
        # 如果没有Key且没数据，尝试直接用公开网页抓取（作为最后的兜底）
        logging.info("🔍 尝试通过公开网页兜底获取美股数据...")
        for symbol in ["ALB", "LAC", "SQM"]:
            try:
                # 使用 Yahoo Finance 的简易接口
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                data = resp.json()
                
                result = data.get("chart", {}).get("result", [{}])[0]
                meta = result.get("meta", {})
                regular_market_price = meta.get("regularMarketPrice")
                
                if regular_market_price:
                    prev_close = meta.get("previousClose", regular_market_price)
                    change = regular_market_price - prev_close
                    pct = (change / prev_close) * 100
                    
                    stocks[symbol]["price"] = f"${regular_market_price:.2f}"
                    sign = "+" if change >= 0 else ""
                    stocks[symbol]["change"] = f"{sign}{change:.2f} ({sign}{pct:.2f}%)"
                    logging.info(f"✅ {symbol} (Yahoo Backup): {stocks[symbol]['price']}")
            except Exception as e:
                logging.error(f"❌ {symbol} (Backup) 也失败了: {e}")

    return stocks

# ---------- 3. 主运行逻辑 ----------
def main():
    print("="*30)
    print("🚀 锂矿情报日报启动")
    print("="*30)
    
    # 1. 获取宏观数据
    macro = fetch_real_macro()
    
    # 2. 获取美股数据
    us_stocks = fetch_overseas_stocks()
    
    # 3. 打印结果用于调试
    print(f"\n💰 汇率: {macro['cny']}")
    print(f"📈 美股 ALB: {us_stocks['ALB']['price']} ({us_stocks['ALB']['change']})")
    print(f"📈 美股 LAC: {us_stocks['LAC']['price']} ({us_stocks['LAC']['change']})")
    
    # 这里你可以继续接原来的 AI 生成报告逻辑...
    # generate_report(macro, us_stocks) ...

if __name__ == "__main__":
    main()
