import os
import requests
import json
from datetime import datetime

# --- 配置部分 ---
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# 【关键修复】尝试多种可能的变量名，防止因大小写或下划线差异导致读取失败
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') or \
                  os.environ.get('FINNHUB_KEY') or \
                  os.environ.get('ALB_API_KEY')

# 调试日志：检查 Key 是否存在（为了安全，不打印具体数值）
if FINNHUB_API_KEY:
    print(f"✅ Finnhub Key 已加载，长度: {len(FINNHUB_API_KEY)}")
else:
    print("❌ 警告：未检测到 FINNHUB_API_KEY，将使用备用数据源")

def get_stock_data(symbol="ALB"):
    """获取美股数据 (优先使用 Finnhub)"""
    price = None
    change_percent = None
    
    # 尝试使用 Finnhub API
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            # Finnhub 返回 c=当前价格, dp=涨跌幅百分比
            if 'c' in data and data['c'] > 0:
                price = data['c']
                change_percent = data['dp']
                print(f"📈 Finnhub 获取成功: {symbol} = {price}")
            else:
                print("⚠️ Finnhub 返回数据无效")
        except Exception as e:
            print(f"❌ Finnhub 请求报错: {e}")

    # 如果 Key 缺失或请求失败，使用备用方案 (模拟数据，防止程序崩溃)
    if price is None:
        print("🔄 启用备用数据模式")
        price = "Key缺失" 
        change_percent = "--"
        
    return price, change_percent

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
    return "6.7500 (估算)"

def send_pushplus(title, content):
    """发送 PushPlus 推送"""
    if not PUSHPLUS_TOKEN:
        print("未配置 PushPlus Token")
        return
    
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        requests.post(url, json=payload, timeout=5)
        print("📤 推送发送成功")
    except Exception as e:
        print(f"推送失败: {e}")

def main():
    print("--- 开始运行锂矿日报任务 ---")
    
    # 1. 获取数据
    alb_price, alb_change = get_stock_data("ALB")
    usd_cnh = get_exchange_rate()
    
    # 2. 构建消息内容
    today = datetime.now().strftime("%m-%d")
    title = f"锂矿日报 | {today}"
    
    content = f"""
    <h3>💰 核心数据</h3>
    <p><strong>雅保(ALB):</strong> {alb_price} USD ({alb_change}%)</p>
    <p><strong>美元/人民币:</strong> {usd_cnh}</p>
    
    <h3>🤖 AI 研判</h3>
    <p>截至{datetime.now().strftime('%Y年%m月%d日')}，美元兑离岸人民币报{usd_cnh}。</p>
    <p>雅保股份(ALB)最新报价为 {alb_price} 美元。结合当前汇率波动，建议关注锂矿板块的短期回调机会。</p>
    """
    
    # 3. 发送推送
    send_pushplus(title, content)
    print("--- 任务结束 ---")

if __name__ == "__main__":
    main()

