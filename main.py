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
    
    # --- 2. 获取股票数据 (ALB) ---
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol=ALB&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        # Finnhub 返回的数据结构: c=当前价格, d=涨跌额, dp=涨跌幅
        if 'c' in data and data['c'] > 0:
            STOCK_PRICE = data['c']
            CHANGE_PCT = data['dp']
        else:
            STOCK_PRICE = "API限流或错误"
            CHANGE_PCT = "--"
    except Exception as e:
        STOCK_PRICE = f"网络错误: {str(e)}"
        CHANGE_PCT = "--"

# --- 3. 获取汇率数据 (使用免费接口) ---
try:
    # 使用免费的汇率接口
    rate_url = "https://api.exchangerate-api.com/v4/latest/USD"
    rate_res = requests.get(rate_url).json()
    USD_CNY = rate_res['rates']['CNY']
except:
    USD_CNY = 7.10  # 默认备用值

# --- 4. 构建 AI 分析 Prompt ---
ai_prompt = f"""
你是一位专业的锂矿行业分析师。
当前时间：{datetime.now().strftime('%Y-%m-%d')}
核心数据：
1. 雅保(ALB)股价：{STOCK_PRICE} USD (涨跌幅: {CHANGE_PCT}%)
2. 美元/人民币汇率：{USD_CNY}

请根据以上数据，结合锂矿行业近期趋势（如供需关系、电动车销量等），写一段简短的【AI研判】（200字以内）。
如果股价数据异常，请在研判中提示风险。
"""

# --- 5. 调用 DeepSeek API 进行分析 ---
ai_analysis = "暂无分析"
if DEEPSEEK_API_KEY and STOCK_PRICE != "Key缺失":
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": ai_prompt}],
            "temperature": 0.7
        }
        res = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        ai_analysis = res.json()['choices'][0]['message']['content']
    except Exception as e:
        ai_analysis = f"AI分析失败: {str(e)}"

# --- 6. 组装最终消息并推送 ---
content = f"""
# 💰 核心数据
**雅保(ALB): {STOCK_PRICE} USD ({CHANGE_PCT}%)**
**美元/人民币: {USD_CNY}**

# 🤖 AI 研判
{ai_analysis}
"""

# 推送到 PushPlus
if PUSHPLUS_TOKEN:
    push_url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"锂矿日报 | {datetime.now().strftime('%m-%d')}",
        "content": content,
        "template": "markdown"
    }
    r = requests.post(push_url, json=data)
    print(f"PushPlus 推送结果: {r.text}")
else:
    print("❌ 未配置 PUSHPLUS_TOKEN")
