import os
import sys
import json
import logging
import re
from datetime import datetime
# 【修复】不再依赖 pytz，改用 Python 3.9+ 自带的 zoneinfo
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
    
    # 1.1 抓取真实汇率
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        cny_rate = data.get("usd", {}).get("cny")
        if cny_rate:
            macro_data["cny"] = f"{cny_rate}"
            logging.info(f"汇率获取成功: {cny_rate}")
    except Exception as e:
        logging.warning(f"汇率获取失败: {e}")

    # 1.2 宏观裁定逻辑
    try:
        if float(macro_data["cny"]) > 7.25:
            macro_data["verdict"] = "🔴 偏空（汇率贬值压力）"
            macro_data["position"] = "建议 30% 仓位"
        else:
            macro_data["verdict"] = "🟢 偏稳"
            macro_data["position"] = "建议 70% 仓位"
    except:
        pass
        
    return macro_data

# ---------- 2. 真实锂价数据（国内现货 + 期货）----------
def fetch_real_lithium_prices():
    price_data = {
        "smm": "--",
        "futures": "--",
        "basis": "--"
    }
    
    # 2.1 现货价格（SMM）
    try:
        smm_url = "https://hq.smm.cn/price"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(smm_url, timeout=12, headers=headers)
        
        # 尝试匹配 "电池级碳酸锂" 后的价格
        price_match = re.search(r'电池级碳酸锂.*?(\d+[,.]?\d+?)\s*元', resp.text, re.DOTALL)
        if price_match:
            raw = price_match.group(1).replace(',', '')
            price_yuan = float(raw) / 10000 
            price_data["smm"] = f"{price_yuan:.2f}"
            logging.info(f"SMM现货价获取成功: {price_yuan:.2f}")
        else:
            # 备用正则
            fallback = re.search(r'(\d{5,6})\s*元/吨', resp.text)
            if fallback:
                price_yuan = float(fallback.group(1)) / 10000
                price_data["smm"] = f"{price_yuan:.2f}"
    except Exception as e:
        logging.warning(f"SMM现货价抓取失败: {e}")

    # 2.2 期货价格（东方财富接口）
    try:
        # 广期所碳酸锂主力合约 secid 通常为 106.LC0 或 106.LC9999
        future_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=106.LC0&fields=f43,f44,f45,f46"
        resp = requests.get(future_url, timeout=10)
        data = resp.json()
        if data.get("data"):
            price = data["data"].get("f43")
            if price:
                price_yuan = float(price) / 10000
                price_data["futures"] = f"{price_yuan:.2f}"
                logging.info(f"期货价获取成功: {price_yuan:.2f}")
    except Exception as e:
        logging.warning(f"期货价抓取失败: {e}")

    # 2.3 计算基差
    try:
        smm_val = float(re.search(r'(\d+\.\d+)', price_data["smm"]).group(1))
        fut_val = float(re.search(r'(\d+\.\d+)', price_data["futures"]).group(1))
        basis = smm_val - fut_val
        price_data["basis"] = f"{basis:+.2f}"
    except:
        price_data["basis"] = "--"
    
    return price_data

# ---------- 3. 海外锂矿股监控（Finnhub API）----------
def fetch_overseas_stocks():
    api_key = os.environ.get("FINNHUB_API_KEY")
    stocks_info = {
        "ALB": "--",  # Albemarle (雅保)
        "LAC": "--",  # Lithium Americas
        "SQM": "--"   # SQM (智利矿业)
    }
    
    if not api_key:
        logging.warning("未检测到 FINNHUB_API_KEY，跳过美股数据抓取")
        return stocks_info

    headers = {"X-Finnhub-Token": api_key}
    
    for symbol in ["ALB", "LAC", "SQM"]:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}"
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            
            # c: 当前价格, d: 涨跌额, dp: 涨跌幅%
            current_price = data.get('c', 0)
            change_percent = data.get('dp', 0)
            
            if current_price and change_percent is not None:
                color = "🔴" if change_percent < 0 else "🟢"
                stocks_info[symbol] = f"${current_price:.2f} ({color}{change_percent:+.2f}%)"
                logging.info(f"美股 {symbol} 获取成功: {current_price}")
        except Exception as e:
            logging.warning(f"美股 {symbol} 获取失败: {e}")
            
    return stocks_info

# ---------- 4. 核心数据整合 ----------
def fetch_data():
    logging.info("开始抓取全部数据...")
    macro = fetch_real_macro()
    prices = fetch_real_lithium_prices()
    overseas_stocks = fetch_overseas_stocks()
    
    return {
        "macro": macro,
        "prices": prices,
        "stocks": overseas_stocks,
        # 模拟供需数据（保持原样）
        "util": {"signal": "🟢 8月排产+8%（模拟）"},
        "inventory": {"change": "🟢 去库6773吨（模拟）"}
    }

# ---------- 5. DeepSeek AI 分析 ----------
def fetch_ai_analysis(data):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "（💡 未配置 AI Key）"
    
    try:
        prompt = f"""
你是资深锂电分析师。根据以下数据给出**50字以内**研判：
1. 汇率：{data['macro']['cny']}
2. 碳酸锂现货：{data['prices']['smm']} 万元/吨
3. 碳酸锂期货：{data['prices']['futures']} 万元/吨
4. 基差：{data['prices']['basis']}
5. 美股雅保(ALB)：{data['stocks']['ALB']}
6. 美股LAC：{data['stocks']['LAC']}
7. 供需信号：{data['util']['signal']}

请只输出研判结论。
"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat", # 或者 deepseek-v3
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
        if resp.status_code == 200:
            result = resp.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            return f"（AI调用失败：{resp.status_code}）"
    except Exception as e:
        return f"（AI异常：{str(e)}）"

# ---------- 6. 生成报告 ----------
def generate_report(data, ai_text):
    # 【修复】使用 ZoneInfo 替代 pytz
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    
    return f"""
# 锂矿狙击手 · 每日情报简报
**报告时间：** {now}

## 一、宏观与海外情绪
- 离岸人民币：**{data['macro']['cny']}** ({data['macro']['verdict']})
- 美股雅保(ALB)：**{data['stocks']['ALB']}**
- 美股LAC：**{data['stocks']['LAC']}**
- 智利SQM：**{data['stocks']['SQM']}**

## 二、国内主战场（锂价）
- 现货：**{data['prices']['smm']}** 万元/吨
- 期货：**{data['prices']['futures']}** 万元/吨
- 基差：**{data['prices']['basis']}**
- 供需信号：{data['util']['signal']}

## 三、🤖 AI 综合研判
{ai_text}

---
*数据来源：SMM, EastMoney, Finnhub, DeepSeek*
"""

# ---------- 7. 微信推送 ----------
def push_to_wechat(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print(content) # 如果没有Token，直接打印
        return
    try:
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

# ---------- 8. 启动 ----------
if __name__ == "__main__":
    try:
        data = fetch_data()
        ai_text = fetch_ai_analysis(data)
        report = generate_report(data, ai_text)
        push_to_wechat(report)
        logging.info("✅ 任务执行完毕。")
    except Exception as e:
        logging.error("程序异常：" + str(e))
