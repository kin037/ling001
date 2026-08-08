import os
import sys
import json
import logging
import re
from datetime import datetime
# 【修改】不再使用 pytz，改用 Python 自带的 zoneinfo
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # 兼容极老版本的 Python (虽然 GitHub Actions 一般不需要)
    from backports.zoneinfo import ZoneInfo 

import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- 1. 真实宏观数据（汇率 + 美联储）----------
def fetch_real_macro():
    macro_data = {
        "cny": "--（暂未获取）",
        "fed_rate": "--（暂未获取）",
        "verdict": "🟡 观望",
        "position": "建议 50% 仓位"
    }
    
    # 1.1 抓取真实汇率
    try:
        # 增加 headers 模拟浏览器，防止被拦截
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json"
        resp = requests.get(url, timeout=10, headers=headers)
        data = resp.json()
        cny_rate = data.get("usd", {}).get("cny")
        if cny_rate:
            macro_data["cny"] = f"{cny_rate:.4f}（USD/CNH）"
            logging.info(f"汇率获取成功: {cny_rate}")
    except Exception as e:
        logging.warning(f"汇率获取失败: {e}")

    # 1.2 抓取美联储加息概率 (CME 网页结构经常变，这里做简单的正则尝试)
    try:
        cme_url = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(cme_url, timeout=15, headers=headers)
        # 尝试寻找类似 96.5% 这种高概率数字，或者具体的利率预期
        # 注意：CME 是动态加载页面，requests 直接抓取可能只能拿到空壳，这里保留原逻辑作为尝试
        matches = re.findall(r'(\d+\.\d)\s*%', resp.text)
        if matches:
            # 取第一个看起来像概率的数字
            macro_data["fed_rate"] = f"{matches[0]}%（CME估算）"
            logging.info(f"美联储数据获取成功: {matches[0]}%")
        else:
            macro_data["fed_rate"] = "页面未解析到数据"
    except Exception as e:
        logging.warning(f"美联储数据获取失败: {e}")

    # 1.3 宏观裁定
    try:
        cny_val = re.search(r'(\d+\.\d+)', macro_data["cny"])
        if cny_val and float(cny_val.group(1)) > 7.30:
            macro_data["verdict"] = "🔴 偏空（汇率贬值压力）"
            macro_data["position"] = "建议 30% 仓位"
        else:
            macro_data["verdict"] = "🟢 偏稳（汇率波动正常）"
            macro_data["position"] = "建议 70% 仓位"
    except:
        pass
    return macro_data

# ---------- 2. 真实锂价数据（现货 + 期货）----------
def fetch_real_lithium_prices():
    price_data = {
        "smm": "--（暂未获取）",
        "futures": "--（暂未获取）",
        "basis": "--（暂无法计算）"
    }
    
    # 2.1 现货价格（SMM 往往有反爬，这里尝试抓取）
    try:
        smm_url = "https://hq.smm.cn/price"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(smm_url, timeout=12, headers=headers)
        
        # 正则匹配逻辑优化
        price_match = re.search(r'电池级碳酸锂.*?(\d+[,.]?\d+?)\s*元', resp.text, re.DOTALL)
        if price_match:
            raw = price_match.group(1).replace(',', '')
            price_yuan = float(raw) / 10000  # 转成万元/吨
            price_data["smm"] = f"{price_yuan:.2f}（SMM现货）"
            logging.info(f"SMM现货价获取成功: {price_yuan:.2f}万元/吨")
        else:
            # 备用匹配：直接找 5-6 位数字
            fallback = re.search(r'(\d{5,6})\s*元/吨', resp.text)
            if fallback:
                price_yuan = float(fallback.group(1)) / 10000
                price_data["smm"] = f"{price_yuan:.2f}（SMM现货）"
                logging.info(f"SMM现货价获取成功(备用): {price_yuan:.2f}万元/吨")
    except Exception as e:
        logging.warning(f"SMM现货价抓取失败: {e}")

    # 2.2 期货价格（东方财富接口）
    try:
        # 广期所碳酸锂主力合约代码通常是 LC0 或 LC9999，这里用 LC0 试试
        future_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=106.LC0&fields=f43,f44,f45,f46"
        resp = requests.get(future_url, timeout=10)
        data = resp.json()
        if data.get("data"):
            price = data["data"].get("f43")
            if price:
                # 期货通常单位是元/吨，需要除以 10000 变万元
                price_yuan = float(price) / 10000
                price_data["futures"] = f"{price_yuan:.2f}（主力期货）"
                logging.info(f"期货价获取成功: {price_yuan:.2f}万元/吨")
    except Exception as e:
        logging.warning(f"期货价抓取失败: {e}")

    # 2.3 计算基差
    try:
        smm_match = re.search(r'(\d+\.\d+)', price_data["smm"])
        fut_match = re.search(r'(\d+\.\d+)', price_data["futures"])
        
        if smm_match and fut_match:
            smm_val = float(smm_match.group(1))
            fut_val = float(fut_match.group(1))
            basis = smm_val - fut_val
            price_data["basis"] = f"{basis:+.2f}（现货-期货）"
    except:
        pass
    
    return price_data

# ---------- 3. 核心数据整合 ----------
def fetch_data():
    logging.info("开始抓取全部真实数据...")
    macro = fetch_real_macro()
    prices = fetch_real_lithium_prices()
    
    # 供需数据（暂时保留模拟，因为这部分很难有免费公开 API）
    lithium_data = {
        "util": {"signal": "🟢 8月排产+8%（模拟，待真实源）"},
        "inventory": {"change": "🟢 去库6773吨（模拟，待真实源）"},
        "overseas": {"conclusion": "ALB财报超预期（模拟，待官方核实）"}
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
        return "（💡 未配置 AI Key，如需启用请在 GitHub Secrets 添加 DEEPSEEK_API_KEY）"
    
    try:
        prompt = f"""
你是一位资深锂电行业分析师。根据以下今日真实数据，给出**50字以内**的综合研判（仅文字）：

人民币汇率：{data['macro']['cny']}
美联储加息概率：{data['macro']['fed_rate']}
碳酸锂现货价：{data['prices']['smm']}
碳酸锂期货价：{data['prices']['futures']}
基差：{data['prices']['basis']}
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
            "model": "deepseek-chat", # 建议使用 deepseek-chat 或具体模型名
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
            return result["choices"][0]["message"]["content"].strip()
        else:
            return f"（AI调用失败，状态码：{resp.status_code}）"
    except Exception as e:
        return f"（AI分析异常：{str(e)}）"

# ---------- 5. 生成报告 ----------
def generate_report(data, ai_text):
    # 【修改】使用 ZoneInfo 替代 pytz
    shanghai_tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(shanghai_tz).strftime("%Y-%m-%d %H:%M")
    
    return f"""
# 锂矿狙击手 · 每日情报简报
**报告时间：** {now}（北京时间）

## 一、正上方·宏观避雷针
- 离岸人民币汇率：**{data['macro']['cny']}**
- 美联储加息概率：**{data['macro']['fed_rate']}**
- 综合裁定：**{data['macro']['verdict']}**，{data['macro']['position']}

## 二、左侧·主战场预警（真实锂价）
- 碳酸锂现货：**{data['prices']['smm']}** 万元/吨
- 碳酸锂期货：**{data['prices']['futures']}** 万元/吨
- 基差：**{data['prices']['basis']}**
- 需求信号：{data['util']['signal']}
- 库存动态：{data['inventory']['change']}

## 三、右侧·核实区
- 海外动态：{data['overseas']['conclusion']}

## 四、🤖 AI 综合研判（DeepSeek）
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
        logging.warning("未设置 PUSHPLUS_TOKEN，仅打印报告：\n" + content)
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

# ---------- 7. 启动 ----------
if __name__ == "__main__":
    try:
        data = fetch_data()
        ai_text = fetch_ai_analysis(data)
        report = generate_report(data, ai_text)
        push_to_wechat(report)
        logging.info("✅ 全部任务执行完毕。")
    except Exception as e:
        logging.error("程序异常：" + str(e))
        sys.exit(1)
