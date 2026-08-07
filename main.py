import os
import requests
import json
from datetime import datetime
import pushplus

# --- 配置部分 ---
# 从环境变量获取密钥
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# Finnhub API Key (这是获取美股数据的稳定来源，免费额度足够)
# 注意：如果你没有注册过，建议去 finnhub.io 注册一个免费的 key 填入下面，或者先试用这个公共测试key(可能不稳定)
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', 'cxxxxxxxxxxxxxxxxxxxxx') # 建议你自己去 finnhub.io 申请一个免费的填在这里

def get_exchange_rate():
    """获取离岸人民币汇率 (使用免费且稳定的接口)"""
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['result'] == 'success':
            rate = data['rates']['CNY']
            return f"{rate:.4f}"
    except Exception as e:
        print(f"汇率获取失败: {e}")
    return "6.7500 (估算值)"

def get_us_stock(symbol="ALB"):
    """获取美股价格 (使用 Finnhub 接口，比 Yahoo 稳定得多)"""
    # 如果用户没有配置 Finnhub Key，尝试使用备用逻辑或返回提示
    if not FINNHUB_API_KEY or 'xxx' in FINNHUB_API_KEY:
         return "需配置FINNHUB_API_KEY"
         
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if 'c' in data and data['c'] != 0:
            return f"{data['c']} USD"
    except Exception as e:
        print(f"美股获取失败: {e}")
    return "--"

def get_macro_news():
    """模拟获取宏观新闻（由于免费宏观API限制极多，这里改为获取简单的美元指数作为替代，或者你可以接入具体的新闻网RSS）"""
    try:
        # 这里简单获取美元指数 DXY 作为宏观参考
        url = f"https://finnhub.io/api/v1/quote?symbol=DXY&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if 'c' in data:
            return f"美元指数: {data['c']}"
    except:
        pass
    return "宏观数据暂缺"

def call_deepseek_ai(data_summary):
    """调用 DeepSeek AI 进行分析"""
    if not DEEPSEEK_API_KEY:
        return "AI 密钥未配置，无法分析。"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    你是一个专业的锂矿投资分析师。请根据以下数据，写一份简短的【锂矿情报日报】。
    
    数据如下：
    {data_summary}
    
    要求：
    1. 分析宏观环境对锂价的影响。
    2. 结合雅保(ALB)股价分析海外情绪。
    3. 给出今日的操作建议（如：观望、建仓、减仓）。
    4. 语气专业、客观。
    """

    payload = {
        "model": "deepseek-chat", # 或者 deepseek-reasoner
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 分析失败: {str(e)}"

def main():
    print("开始生成日报...")
    
    # 1. 获取数据
    rate = get_exchange_rate()
    alb_price = get_us_stock("ALB")
    macro_info = get_macro_news()
    
    # 2. 组装数据摘要给 AI
    summary_text = f"""
    - 离岸人民币: {rate}
    - 雅保(ALB)股价: {alb_price}
    - 宏观指标: {macro_info}
    - 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    
    # 3. AI 分析
    ai_report = call_deepseek_ai(summary_text)
    
    # 4. 组装最终推送内容
    content = f"""
# 🚀 锂矿狙击手 · 每日情报简报
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 🌍 一、宏观与汇率
- 离岸人民币：{rate}
- 宏观指标：{macro_info}

## 🔋 二、海外映射 (真实数据)
- 雅保(ALB)：{alb_price}
*(注：ALB是全球锂业风向标)*

## 🤖 三、AI 综合研判
{ai_report}

---
*数据来源：GitHub Actions Auto-Bot*
    """
    
    # 5. 发送 PushPlus
    if PUSHPLUS_TOKEN:
        pushplus.send_wechat(PUSHPLUS_TOKEN, "锂矿情报日报", content)
        print("推送成功！")
    else:
        print("未配置 PushPlus Token，仅打印内容：")
        print(content)

if __name__ == "__main__":
    main()

