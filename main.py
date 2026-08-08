import os
import sys
import json
import logging
import re
from datetime import datetime
import pytz
import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- 1. 真实宏观数据（汇率 + 替代利率）----------
def fetch_real_macro():
    macro_data = {
        "cny": "--",
        "fed_rate": "--",
        "verdict": "🟡 观望",
        "position": "建议 50% 仓位"
    }
    
    # 1.1 抓取真实汇率 (使用 ExchangeRate-API，免费且快)
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        cny_rate = data.get("rates", {}).get("CNY")
        if cny_rate:
            macro_data["cny"] = f"{cny_rate:.4f}（在岸参考）"
            logging.info(f"✅ 汇率获取成功: {cny_rate}")
    except Exception as e:
        logging.warning(f"❌ 汇率获取失败: {e}")

    # 1.2 获取市场利率 (使用 NY Fed SOFR 作为美联储利率的实时代理指标)
    # CME网页无法爬虫，SOFR是更稳定的免费API数据源
    try:
        # 纽约联储 SOFR 接口 (JSON格式)
        sofr_url = "https://api.newyorkfed.org/markets/api/reference-rates/sofr"
        headers = {"Accept": "application/json"}
        resp = requests.get(sofr_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            # 解析最新的 SOFR 值
            if 'refRates' in data and len(data['refRates']) > 0:
                rate = data['refRates'][0].get('sofr')
                if rate:
                    macro_data["fed_rate"] = f"{rate}%（SOFR实时）"
                    logging.info(f"✅ 市场利率获取成功: {rate}%")
                else:
                    macro_data["fed_rate"] = "API返回空值"
            else:
                macro_data["fed_rate"] = "暂无今日数据"
        else:
            macro_data["fed_rate"] = f"API错误({resp.status_code})"
    except Exception as e:
        logging.warning(f"❌ 利率获取失败: {e}")
        macro_data["fed_rate"] = "获取超时/失败"

    # 1.3 宏观裁定逻辑
    try:
        cny_val = re.search(r'(\d+\.\d+)', macro_data["cny"])
        if cny_val and float(cny_val.group(1)) > 7.25:
            macro_data["verdict"] = "🔴 偏空（汇率承压）"
            macro_data["position"] = "建议 30% 仓位"
        else:
            macro_data["verdict"] = "🟢 偏稳（汇率正常）"
            macro_data["position"] = "建议 70% 仓位"
    except:
        pass
        
    return macro_data

# ---------- 2. 真实锂价数据（东方财富接口）----------
def fetch_real_lithium_prices():
    price_data = {
        "futures": "--",
        "change": "--",
        "basis": "--"
    }
    
    # 2.1 核心：抓取碳酸锂主力合约 (LC0 / LC9999)
    # 东方财富 Push2 接口，非常稳定
    try:
        # secid 113.LC0 代表广期所碳酸锂主力连续
        url = "https://push2.eastmoney.com/api/qt/stock/get?secid=113.LC0&fields=f43,f44,f45,f46,f170"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if data.get("data"):
            d = data["data"]
            price = d.get("f43") # 最新价
            change_pct = d.get("f170") # 涨跌幅
            
            if price:
                price_wan = price / 10000 # 转换为万元/吨
                price_data["futures"] = f"{price_wan:.2f}"
                
                if change_pct is not None:
                    sign = "+" if change_pct > 0 else ""
                    price_data["change"] = f"{sign}{change_pct}%"
                    
                logging.info(f"✅ 锂期货主力获取成功: {price_wan}万元/吨")
            else:
                price_data["futures"] = "休市中/无数据"
        else:
            price_data["futures"] = "接口无数据"
            
    except Exception as e:
        logging.warning(f"❌ 期货数据抓取失败: {e}")

    # 2.2 现货价格说明 (SMM等现货数据免费接口极少，此处做逻辑处理)
    # 如果有期货，我们通常用期货作为主要参考。
    # 这里为了报告完整性，如果抓不到现货，就只显示期货。
    if price_data["futures"] == "--":
        price_data["basis"] = "无法计算基差"
    else:
        price_data["basis"] = "需结合SMM现货(付费)计算"

    return price_data

# ---------- 3. 核心数据整合 ----------
def fetch_data():
    logging.info("开始抓取全部真实数据...")
    macro = fetch_real_macro()
    prices = fetch_real_lithium_prices()
    
    # 供需数据（保持模拟，因为真实库存数据也是付费的）
    lithium_data = {
        "util": {"signal": "🟢 8月排产环比+8%（模拟数据）"},
        "inventory": {"change": "🔴 社会库存微增（模拟数据）"},
        "overseas": {"conclusion": "ALB财报符合预期（模拟数据）"}
    }
    
    return {
        "macro": macro,
        "prices": prices,
        "util": lithium_data["util"],
        "inventory": lithium_data["inventory"],
        "overseas": lithium_data["overseas"]
    }

# ---------- 4. DeepSeek AI 分析 ----------
def fetch_ai_analysis(data):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "（💡 未配置 AI Key，请在 GitHub Secrets 添加 DEEPSEEK_API_KEY）"
    
    try:
        prompt = f"""
你是一位资深锂电行业分析师。根据以下今日真实数据，给出**50字以内**的综合研判（仅文字）：

人民币汇率：{data['macro']['cny']}
市场参考利率(SOFR)：{data['macro']['fed_rate']}
碳酸锂期货主力：{data['prices']['futures']} 万元/吨
涨跌幅：{data['prices']['change']}
需求信号：{data['util']['signal']}
库存动态：{data['inventory']['change']}
海外动态：{data['overseas']['conclusion']}

请只输出研判结论，不要包含任何其他说明。
"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat", # 修正模型名称
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 200
        }
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
        if resp.status_code == 200:
            result = resp.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else "AI生成内容为空"
        else:
            return f"（AI调用失败：{resp.status_code}）"
    except Exception as e:
        return f"（AI分析异常：{str(e)}）"

# ---------- 5. 生成报告 ----------
def generate_report(data, ai_text):
    now = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    return f"""
# 🚀 锂矿狙击手 · 每日情报简报
**报告时间：** {now}（北京时间）

## 一、正上方·宏观避雷针
- 离岸人民币汇率：**{data['macro']['cny']}**
- 市场参考利率(SOFR)：**{data['macro']['fed_rate']}**
- 综合裁定：**{data['macro']['verdict']}**，{data['macro']['position']}

## 二、左侧·主战场预警（真实锂价）
- 碳酸锂期货主力：**{data['prices']['futures']}** 万元/吨
- 今日涨跌：**{data['prices']['change']}**
- 基差状态：{data['prices']['basis']}
- 需求信号：{data['util']['signal']}
- 库存动态：{data['inventory']['change']}

## 三、右侧·核实区
- 海外动态：{data['overseas']['conclusion']}

## 四、🤖 AI 综合研判（DeepSeek V3）
{ai_text}

## 五、今日总参谋
信号共振：{data['macro']['verdict']} + 需求🟢 + 库存🟢  
---
*本报告由自动化系统生成 | 数据仅供参考，不构成投资建议*  
*下次更新：明天 16:30*
"""

# ---------- 6. 微信推送 ----------
def push_to_wechat(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        logging.warning("⚠️ 未设置 PUSHPLUS_TOKEN，仅打印报告：\n" + content)
        print(content) # 在控制台也打印一份方便调试
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
            logging.error(f"❌ 推送失败：{resp.text}")
    except Exception as e:
        logging.error(f"❌ 网络异常：{e}")

# ---------- 7. 启动 ----------
if __name__ == "__main__":
    try:
        data = fetch_data()
        ai_text = fetch_ai_analysis(data)
        report = generate_report(data, ai_text)
        push_to_wechat(report)
        logging.info("✅ 全部任务执行完毕。")
    except Exception as e:
        logging.error("💥 程序严重异常：" + str(e))
        sys.exit(1)
