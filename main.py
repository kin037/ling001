import os
import sys
import json
import logging
import re
import time
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 1. 配置管理
# ============================================================

class Config:
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    REQ_TIMEOUT = 10
    REQ_TIMEOUT_LONG = 20
    MAX_RETRIES = 2
    RETRY_BACKOFF = 1.0

    EXCHANGE_RATE_PRIMARY = (
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api"
        "@latest/v1/currencies/usd.min.json"
    )
    EXCHANGE_RATE_FALLBACK = "https://api.exchangerate-api.com/v4/latest/USD"

    CME_FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
    CME_FEDWATCH_FALLBACK = (
        "https://api.allorigins.win/raw?url="
        "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
    )

    FUTURE_SECID_PRIMARY = "106.LC0"
    FUTURE_SECID_FALLBACK = "106.LC9999"
    FUTURE_API_TEMPLATE = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        "?secid={secid}&fields=f43,f44,f45,f46,f47"
    )

    SMM_URL = "https://hq.smm.cn/price"

    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    PUSHPLUS_URL = "https://www.pushplus.plus/send"

    DEMO_DATA = {
        "cny_rate": 6.75,
        "fed_rate": 25.0,
        "spot_price": 7.85,
        "future_price": 7.92,
        "util_signal": "🟢 8月排产+8%（模拟，待真实源）",
        "inventory_change": "🟢 去库6773吨（模拟，待真实源）",
        "overseas_conclusion": "ALB财报超预期（模拟，待官方核实）",
    }


# ============================================================
# 2. 日志配置
# ============================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("lithium_hunter")
    logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
        logger.addHandler(handler)
    return logger


log = setup_logging()


# ============================================================
# 3. HTTP 请求工具（连接池 + 重试）
# ============================================================

def _create_session() -> requests.Session:
    """创建带重试策略的 Session"""
    session = requests.Session()
    retry = Retry(
        total=Config.MAX_RETRIES,
        backoff_factor=Config.RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=4,
        pool_maxsize=4,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    })
    return session


def _safe_get(
    session: requests.Session,
    url: str,
    timeout: int = Config.REQ_TIMEOUT,
    **kwargs,
) -> Optional[requests.Response]:
    """安全 GET 请求，统一异常处理"""
    try:
        resp = session.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.exceptions.Timeout as e:
        log.warning(f"请求超时: {url} -> {e}")
    except requests.exceptions.ConnectionError as e:
        log.warning(f"连接失败: {url} -> {e}")
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP错误: {url} -> {e.response.status_code} {e.response.text[:100]}")
    except requests.exceptions.RequestException as e:
        log.warning(f"请求异常: {url} -> {type(e).__name__}: {e}")
    return None


def _safe_post(
    session: requests.Session,
    url: str,
    json_data: dict,
    timeout: int = Config.REQ_TIMEOUT,
) -> Optional[requests.Response]:
    """安全 POST 请求"""
    try:
        resp = session.post(url, json=json_data, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.Timeout as e:
        log.warning(f"POST超时: {url} -> {e}")
    except requests.exceptions.ConnectionError as e:
        log.warning(f"POST连接失败: {url} -> {e}")
    except requests.exceptions.HTTPError as e:
        log.warning(f"POST HTTP错误: {url} -> {e.response.status_code} {e.response.text[:100]}")
    except requests.exceptions.RequestException as e:
        log.warning(f"POST异常: {url} -> {type(e).__name__}: {e}")
    return None


# ============================================================
# 4. 宏观数据抓取（汇率 + 美联储）
# ============================================================

def fetch_exchange_rate(session: requests.Session) -> Optional[float]:
    """抓取 USD/CNY 汇率，多源降级。返回: 1 USD = X CNY"""
    # 主源
    try:
        resp = _safe_get(session, Config.EXCHANGE_RATE_PRIMARY)
        if resp:
            data = resp.json()
            cny = data.get("usd", {}).get("cny")
            if cny and float(cny) > 0:
                log.info(f"汇率(主源)获取成功: 1 USD = {cny} CNY")
                return float(cny)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log.warning(f"汇率(主源)解析失败: {e}")

    # 备用源
    try:
        resp = _safe_get(session, Config.EXCHANGE_RATE_FALLBACK)
        if resp:
            data = resp.json()
            cny = data["rates"].get("CNY")
            if cny and float(cny) > 0:
                log.info(f"汇率(备用源)获取成功: 1 USD = {cny} CNY")
                return float(cny)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log.warning(f"汇率(备用源)解析失败: {e}")

    log.warning("汇率全部数据源不可用")
    return None


def fetch_fed_rate(session: requests.Session) -> Optional[float]:
    """抓取美联储目标利率，多源降级。返回: 利率百分比数值（如25.0表示2.50%）"""
    # 主源：CME FedWatch
    try:
        resp = _safe_get(session, Config.CME_FEDWATCH_URL)
        if resp and resp.text:
            matches = re.findall(r"(\d+\.\d)\s*%", resp.text)
            if matches:
                rate = float(matches[0])
                log.info(f"美联储利率(CME)获取成功: {rate}%")
                return rate
            log.warning("CME页面未匹配到利率数据（可能需JS渲染）")
    except requests.RequestException as e:
        log.warning(f"美联储(CME主源)请求失败: {e}")

    # 备用源：代理
    try:
        resp = _safe_get(session, Config.CME_FEDWATCH_FALLBACK)
        if resp and resp.text:
            matches = re.findall(r"(\d+\.\d)\s*%", resp.text)
            if matches:
                rate = float(matches[0])
                log.info(f"美联储利率(代理源)获取成功: {rate}%")
                return rate
    except requests.RequestException as e:
        log.warning(f"美联储(代理源)请求失败: {e}")

    log.warning("美联储利率全部数据源不可用")
    return None


def make_macro_verdict(cny_rate: Optional[float], fed_rate: Optional[float]) -> Tuple[str, str]:
    """根据宏观数据生成裁定"""
    if cny_rate is not None:
        if cny_rate > 7.3:
            return "🔴 偏空（汇率贬值压力）", "建议 30% 仓位"
        elif cny_rate > 7.1:
            return "🟡 中性（汇率波动正常）", "建议 50% 仓位"
        else:
            return "🟢 偏稳（汇率走势稳健）", "建议 70% 仓位"
    elif fed_rate is not None:
        if fed_rate >= 5.0:
            return "🟡 偏紧（高利率持续）", "建议 40% 仓位"
        else:
            return "🟢 偏稳（利率有所回落）", "建议 60% 仓位"
    else:
        return "🟡 观望（数据暂缺）", "建议 50% 仓位"


def fetch_macro_data(session: requests.Session) -> Dict[str, Any]:
    """宏观数据抓取入口"""
    log.info("开始抓取宏观数据...")
    cny_rate = fetch_exchange_rate(session)
    fed_rate = fetch_fed_rate(session)
    verdict, position = make_macro_verdict(cny_rate, fed_rate)

    macro = {
        "cny": f"{cny_rate:.4f}（实时汇率）" if cny_rate else "--（暂未获取）",
        "fed_rate": f"{fed_rate}%（CME数据）" if fed_rate else "--（暂未获取）",
        "verdict": verdict,
        "position": position,
    }
    log.info(f"宏观裁定: {verdict} | {position}")
    return macro


# ============================================================
# 5. 锂价数据抓取（现货 + 期货）
# ============================================================

def fetch_spot_price_smm(session: requests.Session) -> Optional[float]:
    """抓取 SMM 现货价（万元/吨）"""
    try:
        resp = _safe_get(session, Config.SMM_URL, timeout=12)
        if not resp or not resp.text:
            return None
        text = resp.text

        # 匹配模式1
        match = re.search(r"电池级碳酸锂.*?(\d+[,.]?\d+?)\s*元", text, re.DOTALL)
        if match:
            raw = match.group(1).replace(",", "")
            price = float(raw) / 10000
            log.info(f"SMM现货价(匹配1)获取成功: {price:.2f}万元/吨")
            return price

        # 匹配模式2
        match = re.search(r"(\d{5,6})\s*元/吨", text)
        if match:
            price = float(match.group(1)) / 10000
            log.info(f"SMM现货价(匹配2)获取成功: {price:.2f}万元/吨")
            return price

        # 匹配模式3: JSON字段
        prices = re.findall(r'"price"\s*:\s*(\d+\.?\d*)', text)
        if prices:
            price = float(prices[0]) / 10000
            log.info(f"SMM现货价(匹配3)获取成功: {price:.2f}万元/吨")
            return price

        log.warning("SMM页面未匹配到价格数据（可能需JS渲染）")
    except requests.RequestException as e:
        log.warning(f"SMM现货价请求失败: {e}")
    except (ValueError, IndexError) as e:
        log.warning(f"SMM现货价解析失败: {e}")
    return None


def fetch_future_price(session: requests.Session, secid: str) -> Optional[float]:
    """通过东方财富 API 抓取期货最新价（万元/吨）"""
    url = Config.FUTURE_API_TEMPLATE.format(secid=secid)
    try:
        resp = _safe_get(session, url, timeout=10)
        if resp:
            data = resp.json()
            price = data.get("data", {}).get("f43")
            if price and float(price) > 0:
                price_wan = float(price) / 10000
                log.info(f"期货价({secid})获取成功: {price_wan:.2f}万元/吨")
                return price_wan
            log.warning(f"期货({secid})未返回有效价格")
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log.warning(f"期货({secid})解析失败: {e}")
    return None


def fetch_lithium_prices(session: requests.Session) -> Dict[str, Any]:
    """锂价数据抓取入口（多源降级）"""
    log.info("开始抓取锂价数据...")

    spot = fetch_spot_price_smm(session)
    if spot is None:
        log.warning("SMM现货价不可用，尝试备用源...")
        try:
            resp = _safe_get(session, "https://hq.smm.cn/v1/price/Li202508.json", timeout=8)
            if resp:
                data = resp.json()
                price_val = data.get("price") or data.get("latest") or data.get("close")
                if price_val:
                    spot = float(price_val) / 10000
                    log.info(f"SMM备用现货价获取成功: {spot:.2f}万元/吨")
        except Exception as e:
            log.warning(f"SMM备用现货价失败: {e}")

    future = fetch_future_price(session, Config.FUTURE_SECID_PRIMARY)
    if future is None:
        log.warning("期货(主secid)不可用，尝试备用secid...")
        future = fetch_future_price(session, Config.FUTURE_SECID_FALLBACK)

    basis = None
    if spot is not None and future is not None:
        basis = round(spot - future, 2)
        sign = "+" if basis >= 0 else ""
        basis = f"{sign}{basis:.2f}（现货-期货）"

    prices = {
        "smm": f"{spot:.2f}（SMM现货）" if spot else "--（暂未获取）",
        "futures": f"{future:.2f}（主力期货）" if future else "--（暂未获取）",
        "basis": basis if basis else "--（暂无法计算）",
    }
    log.info(f"现货: {prices['smm']} | 期货: {prices['futures']} | 基差: {prices['basis']}")
    return prices


# ============================================================
# 6. 核心数据整合
# ============================================================

def fetch_data(session: requests.Session, demo: bool = False) -> Dict[str, Any]:
    """数据抓取总入口"""
    if demo:
        log.info("=== 模拟模式（Demo）=== 使用模拟数据，不请求外部API")
        d = Config.DEMO_DATA
        macro = {
            "cny": f"{d['cny_rate']:.4f}（模拟汇率）",
            "fed_rate": f"{d['fed_rate']}%（模拟利率）",
            "verdict": "🟡 观望（模拟数据）",
            "position": "建议 50% 仓位（模拟）",
        }
        prices = {
            "smm": f"{d['spot_price']:.2f}（模拟现货）",
            "futures": f"{d['future_price']:.2f}（模拟期货）",
            "basis": f"+{d['spot_price']-d['future_price']:.2f}（模拟基差）",
        }
        return {
            "macro": macro,
            "prices": prices,
            "util": {"signal": d["util_signal"]},
            "inventory": {"change": d["inventory_change"]},
            "overseas": {"conclusion": d["overseas_conclusion"]},
        }

    log.info("开始抓取全部真实数据...")
    macro = fetch_macro_data(session)
    prices = fetch_lithium_prices(session)
    return {
        "macro": macro,
        "prices": prices,
        "util": {"signal": "🟢 8月排产+8%（模拟，待真实源）"},
        "inventory": {"change": "🟢 去库6773吨（模拟，待真实源）"},
        "overseas": {"conclusion": "ALB财报超预期（模拟，待官方核实）"},
    }


# ============================================================
# 7. DeepSeek AI 分析
# ============================================================

def fetch_ai_analysis(session: requests.Session, data: Dict[str, Any]) -> str:
    """调用 DeepSeek API 进行综合分析"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "（💡 未配置 AI Key，如需启用请在环境变量添加 DEEPSEEK_API_KEY）"

    prompt = (
        f"你是一位资深锂电行业分析师。根据以下今日真实数据，"
        f"给出50字以内的综合研判（仅文字）：\n\n"
        f"人民币汇率：{data['macro']['cny']}\n"
        f"美联储利率：{data['macro']['fed_rate']}\n"
        f"碳酸锂现货价：{data['prices']['smm']} 万元/吨\n"
        f"碳酸锂期货价：{data['prices']['futures']} 万元/吨\n"
        f"基差：{data['prices']['basis']}\n"
        f"需求信号：{data['util']['signal']}\n"
        f"库存动态：{data['inventory']['change']}\n"
        f"海外动态：{data['overseas']['conclusion']}\n\n"
        f"请只输出研判结论，不要包含任何其他说明。"
    )

    payload = {
        "model": Config.DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 200,
    }

    resp = _safe_post(session, Config.DEEPSEEK_API_URL, payload, timeout=Config.REQ_TIMEOUT_LONG)
    if resp:
        try:
            result = resp.json()
            return result["choices"][0]["message"]["content"].strip()
        except (json.JSONDecodeError, KeyError) as e:
            return f"（AI解析失败: {e}）"
    return "（AI调用失败，网络异常）"


# ============================================================
# 8. 报告生成
# ============================================================

def generate_report(data: Dict[str, Any], ai_text: str) -> str:
    """生成 Markdown 格式日报"""
    now = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 锂矿狙击手 · 每日情报简报",
        f"**报告时间：** {now}（北京时间）",
        "",
        "## 一、正上方·宏观避雷针",
        f"- 离岸人民币汇率：**{data['macro']['cny']}**",
        f"- 美联储利率：**{data['macro']['fed_rate']}**",
        f"- 综合裁定：**{data['macro']['verdict']}**，{data['macro']['position']}",
        "",
        "## 二、左侧·主战场预警（真实锂价）",
        f"- 碳酸锂现货：**{data['prices']['smm']}** 万元/吨",
        f"- 碳酸锂期货：**{data['prices']['futures']}** 万元/吨",
        f"- 基差：**{data['prices']['basis']}**",
        f"- 需求信号：{data['util']['signal']}",
        f"- 库存动态：{data['inventory']['change']}",
        "",
        "## 三、右侧·核实区",
        f"- 海外动态：{data['overseas']['conclusion']}",
        "",
        "## 四、🤖 AI 综合研判（DeepSeek V4-Flash）",
        ai_text,
        "",
        "## 五、今日总参谋",
        f"信号共振：{data['macro']['verdict']} + 需求🟢 + 库存🟢",
        "",
        "---",
        "*本报告由自动化系统生成 | 数据仅供参考，不构成投资建议*",
        "*下次更新：明天 16:30*",
    ]
    return "\n".join(lines)


# ============================================================
# 9. 微信推送
# ============================================================

def push_to_wechat(session: requests.Session, content: str) -> bool:
    """推送到微信（PushPlus）"""
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        log.warning("未设置 PUSHPLUS_TOKEN，仅打印报告")
        return False

    try:
        resp = _safe_post(
            session, Config.PUSHPLUS_URL,
            {"token": token, "title": "锂矿情报日报", "content": content, "template": "markdown"},
            timeout=10,
        )
        if resp and resp.status_code == 200:
            log.info("✅ 微信推送成功！")
            return True
        log.error("推送失败")
    except Exception as e:
        log.error(f"推送异常: {e}")
    return False


# ============================================================
# 10. 启动入口
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="锂矿狙击手 · 每日情报简报")
    parser.add_argument("--demo", action="store_true", help="使用模拟数据（无需外部API可用）")
    args = parser.parse_args()

    log.info("=" * 50)
    log.info("锂矿狙击手 v2.0 启动")
    if args.demo:
        log.info("⚠️  模拟模式（Demo）已启用")
    log.info("=" * 50)

    session = _create_session()
    try:
        data = fetch_data(session, demo=args.demo)
        ai_text = fetch_ai_analysis(session, data)
        report = generate_report(data, ai_text)
        print("\n" + report)
        push_to_wechat(session, report)
        log.info("✅ 全部任务执行完毕。")
    except KeyboardInterrupt:
        log.info("⚠️  用户中断执行")
        sys.exit(130)
    except Exception as e:
        log.error(f"程序异常: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
