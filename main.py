import os
import requests
import json
from datetime import datetime

# --- 配置部分 ---
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') 

def send_pushplus(title, content):
    """直接使用 requests 发送推送，无需安装 pushplus 包"""
    if not PUSHPLUS_TOKEN:
        print("未配置 PUSHPLUS_TOKEN，跳过推送")
        return
    
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html" 
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"推送结果: {resp.text}")
    except Exception as e:
        print(f"推送失败: {e}")

def get_exchange_rate():
    """获取离岸人民币汇率"""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['result'] == 'success':
            return f"{data['rates']['CNH']:.4f}"
    except Exception as e:
        print(f"汇率获取失败: {e}")
    return "N/A"

def get_us_stock(symbol):
    """使用 Finnhub 获取美股数据"""
    if not FINNHUB_API_KEY or FINNHUB_API_KEY.startswith('cxxx'):
        return {"price": "Key缺失", "change": "--"}
        
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        current_price = data.get('c', 0)
        previous_close = data.get('pc', 1)
        
        if current_price == 0:
            return {"price": "休市中", "change": "--"}
            
        change_pct = ((current_price - previous_close) / previous_close) * 100
        return {
            "price": f"{current_price:.2f}",
            "change": f"{change_pct:+.2f}%"
        }
    except Exception as e:
        print(f"美股数据获取失败: {e}")
        return {"price": "Error", "change": "--"}

def get_ai_analysis(stock_data, rate):
    """调用 DeepSeek 进行分析"""
    if not DEEPSEEK_API_KEY:
        return "未配置 DeepSeek Key，无法分析"
        
    prompt = f"""
    作为锂矿行业分析师，请根据以下数据给出简短点评（100字内）：
    1. 雅保(ALB)现价: {stock_data.get('price')}美元，涨跌幅: {stock_data.get('change')}
    2. 美元兑离岸人民币: {rate}
    3. 当前时间: {datetime.now().strftime('%Y-%m-%d')}
    请重点分析汇率对锂矿进口成本的影响及股价短期趋势。
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"AI分析失败: {str(e)[:50]}"

def main():
    print("开始采集数据...")
    
    # 1. 获取基础数据
    rate = get_exchange_rate()
    alb_data = get_us_stock("ALB")
    
    # 2. 组装消息
    title = f"锂矿日报 | {datetime.now().strftime('%m-%d')}"
    content = f"""
    <h3>💰 核心数据</h3>
    <ul>
        <li><b>雅保(ALB):</b> {alb_data['price']} USD ({alb_data['change']})</li>
        <li><b>美元/人民币:</b> {rate}</li>
    </ul>
    <hr>
    <h3>🤖 AI 研判</h3>
    <p>{get_ai_analysis(alb_data, rate)}</p>
    """
    
    # 3. 发送推送
    send_pushplus(title, content)
    print("任务完成")

if __name__ == "__main__":
    main()
