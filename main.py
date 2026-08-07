import os
import requests
import json
from datetime import datetime
import time

# --- 配置部分 ---
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
# 这里会自动读取你刚才在 GitHub Secrets 里配置的 FINNHUB_API_KEY
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') 

def get_exchange_rate():
    """获取离岸人民币汇率 (使用免费且稳定的接口)"""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['result'] == 'success':
            rate = data['rates']['CNH']
            return f"{rate:.4f}"
    except Exception as e:
        print(f"汇率获取失败: {e}")
    return "N/A"

def get_fed_rate():
    """获取美联储利率 (FRED API 或 硬编码备用)"""
    # 注意：FRED API 需要申请 Key，为了稳定性，这里暂时使用固定值或简单抓取
    # 如果你需要实时精确值，建议去 St. Louis Fed 申请 Key
    try:
        # 尝试一个简单的宏观数据源，如果失败则返回最近已知数据
        url = "https://api.federalreserve.gov/data.json" # 这是一个示例，实际可能需要更复杂的解析
        # 为了保证不报错，这里我们做一个简单的模拟返回，或者你可以填入你的 FRED KEY
        return "5.25% - 5.50% (维持不变)" 
    except:
        return "5.25% - 5.50% (参考值)"

def get_us_stock(symbol):
    """使用 Finnhub 获取美股数据"""
    if not FINNHUB_API_KEY or FINNHUB_API_KEY.startswith('cxxx'):
        return "Error: 请配置 Finnhub API Key"
    
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Finnhub 返回: c:当前价格, d:涨跌额, dp:涨跌幅, h:最高, l:最低
        if 'c' in data and data['c'] != 0:
            price = data['c']
            change = data['d']
            percent = data['dp']
            sign = "+" if change > 0 else ""
            return f"${price:.2f} ({sign}{change:.2f}, {sign}{percent:.2f}%)"
        else:
            return "休市中或无数据"
    except Exception as e:
        return f"Error: {str(e)[:30]}"

def get_ai_analysis(stock_data, macro_data):
    """调用 DeepSeek 进行综合研判"""
    if not DEEPSEEK_API_KEY:
        return "AI Key 未配置"
    
    prompt = f"""
    你是一个专业的金融分析师。请根据以下数据生成一份简短的【每日投资内参】：
    
    1. 市场数据：
       - 雅保(ALB) 股价：{stock_data}
       - 美元兑离岸人民币：{macro_data.get('rate', 'N/A')}
       - 美联储利率环境：{macro_data.get('fed', 'N/A')}
    
    2. 分析要求：
       - 结合锂矿行业现状（如碳酸锂价格波动）分析 ALB 走势。
       - 结合汇率分析对中概股或跨境资金的影响。
       - 给出具体的操作建议（如：观望、低吸、高抛）。
       - 语气专业、客观，字数控制在 300 字以内。
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers, timeout=15)
        result = resp.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 生成失败: {e}"

def send_pushplus(title, content):
    """发送 PushPlus 消息"""
    if not PUSHPLUS_TOKEN:
        print("未配置 PushPlus Token")
        return
    
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown"
    }
    requests.post(url, json=data)

def main():
    print("开始收集数据...")
    
    # 1. 获取基础数据
    alb_price = get_us_stock("ALB")
    usd_cnh = get_exchange_rate()
    fed_rate = get_fed_rate()
    
    # 2. 组装宏观数据包
    macro_data = {
        "rate": usd_cnh,
        "fed": fed_rate
    }
    
    # 3. 生成 AI 研判
    ai_comment = get_ai_analysis(alb_price, macro_data)
    
    # 4. 组装最终日报
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"""
### 📅 每日投资内参 | {today}

**1. 核心标的追踪**
- **雅保 (ALB)**: `{alb_price}`
- **美元/离岸人民币**: `{usd_cnh}`

**2. 宏观环境**
- **美联储利率**: {fed_rate}

---

### 🤖 AI 综合研判
{ai_comment}

> *注：数据仅供参考，不构成投资建议。*
"""
    
    print("发送日报...")
    send_pushplus(f"投资内参-{today}", report)
    print("任务完成！")

if __name__ == "__main__":
    main()
