import os
import requests
import json
from datetime import datetime

# --- 1. 强制读取并检查环境变量 ---
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# 【关键修改】尝试所有可能的变量名，防止因拼写差异导致失败
# 注意：这里会优先读取 FINNHUB_API_KEY，如果没有，会尝试 FINNHUB_KEY
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') or os.environ.get('FINNHUB_KEY')

# 调试日志：在后台打印状态（不会打印Key的具体内容，保证安全）
if not FINNHUB_API_KEY:
    print("❌ 严重错误：未找到 Finnhub API Key！")
    print(f"   当前环境变量列表: {list(os.environ.keys())}") 
    # 如果没有Key，我们给一个默认的错误提示，防止程序崩溃
    STOCK_PRICE = "Key缺失"
    CHANGE_PCT = "--"
else:
    print(f"✅ 成功读取到 Finnhub Key (长度: {len(FINNHUB_API_KEY)})")
    
    # --- 2. 获取股票数据 (只有在有Key时才运行) ---
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol=ALB&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Finnhub 返回的数据结构：c=当前价格, dp=涨跌幅百分比
        if 'c' in data and data['c'] > 0:
            STOCK_PRICE = str(data['c'])
            CHANGE_PCT = str(round(data['dp'], 2)) + "%"
        else:
            STOCK_PRICE = "API返回异常"
            CHANGE_PCT = "--"
    except Exception as e:
        print(f"获取股价出错: {e}")
        STOCK_PRICE = "获取失败"
        CHANGE_PCT = "--"

# --- 3. 获取汇率 (使用免费接口) ---
try:
    # 使用 exchangerate-api 的免费公开接口
    rate_url = "https://api.exchangerate-api.com/v4/latest/USD"
    r_data = requests.get(rate_url, timeout=10).json()
    USD_CNY = str(r_data['rates']['CNY'])
except:
    USD_CNY = "6.75 (估算)"

# --- 4. 组装推送内容 ---
date_str = datetime.now().strftime("%m-%d")
title = f"锂矿日报 | {date_str}"

content = f"""
<h3>💰 核心数据</h3>
<p><b>雅保(ALB):</b> {STOCK_PRICE} USD ({CHANGE_PCT})</p>
<p><b>美元/人民币:</b> {USD_CNY}</p>

<h3>🤖 AI 研判</h3>
<p>截至2026年{date_str}，美元兑离岸人民币报{USD_CNY}。</p>
<p>雅保股份(ALB)最新报价为 <b>{STOCK_PRICE}</b> 美元。结合当前汇率波动，建议关注锂矿板块的短期回调机会。</p>
"""

# --- 5. 发送 PushPlus 推送 ---
if PUSHPLUS_TOKEN:
    push_url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        requests.post(push_url, json=payload)
        print("📤 推送发送成功")
    except Exception as e:
        print(f"推送失败: {e}")
else:
    print("⚠️ 未配置 PUSHPLUS_TOKEN，跳过推送")
