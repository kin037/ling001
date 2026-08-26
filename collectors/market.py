# -*- coding: utf-8 -*-
"""
市场行情采集器
========================

数据源（全部实测可用，无需登录）：

1. 新浪财经 A 股行情：hq.sinajs.cn/list=szXXXXXX
   返回 GBK 文本，字段：
   [0]名称 [1]今开 [2]昨收 [3]最新 [4]最高 [5]最低
   [6]买一价 [7]卖一价 [8]成交量(股) [9]成交额(元) [30]日期 [31]时间

2. 新浪财经 港股行情：hq.sinajs.cn/list=hkXXXXX
   字段：[0]英文名 [1]中文名 [2]今开 [3]昨收 [4]最高 [5]最低
        [6]最新 [7]涨跌额 [8]涨跌幅%

3. 新浪财经 离岸人民币：hq.sinajs.cn/list=fx_susdcnh
   字段：[1]最新 [10]涨跌幅 [11]涨跌额 [17]日期

4. Yahoo Finance：美股锂业公司（ALB / SQM / LAC），失败自动容错
"""

import time

from datetime import datetime, timezone

from collectors.http import safe_get_text, safe_get_json

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
}

# =========================================================
# 新浪 A 股
# =========================================================

# 核心锂矿 A 股（代码 -> 名称）
A_SHARES = {
    "sz002466": "天齐锂业",
    "sz002460": "赣锋锂业",
    "sz000792": "盐湖股份",
    "sz002738": "中矿资源",
    "sz002756": "永兴材料",
}

# 新浪港股（赣锋锂业 H 股）
H_SHARES = {
    "hk01772": "赣锋锂业H",
}


def _parse_sina_a(line):
    """解析新浪 A 股行情。"""
    if "=" not in line:
        return None
    _, quoted = line.split("=", 1)
    quoted = quoted.strip().strip('";').strip('"')
    fields = quoted.split(",")
    if len(fields) < 32:
        return None
    name = fields[0]
    prev_close = _num(fields[2])
    last = _num(fields[3])
    return {
        "name": name,
        "open": _num(fields[1]),
        "prev_close": prev_close,
        "last": last,
        "high": _num(fields[4]),
        "low": _num(fields[5]),
        "volume": _num(fields[8]),
        "amount": _num(fields[9]),
        "date": fields[30],
        "time": fields[31],
        "change_pct": _change_pct(prev_close, last),
    }


def _parse_sina_hk(line):
    """解析新浪港股行情。"""
    if "=" not in line:
        return None
    _, quoted = line.split("=", 1)
    quoted = quoted.strip().strip('";').strip('"')
    fields = quoted.split(",")
    if len(fields) < 9:
        return None
    name = fields[1]
    last = _num(fields[6])
    return {
        "name": name,
        "open": _num(fields[2]),
        "prev_close": _num(fields[3]),
        "high": _num(fields[4]),
        "low": _num(fields[5]),
        "last": last,
        "change_pct": _num(fields[8]),
        "change": _num(fields[7]),
    }


def _parse_sina_fx(line):
    """解析新浪离岸人民币汇率。"""
    if "=" not in line:
        return None
    _, quoted = line.split("=", 1)
    quoted = quoted.strip().strip('";').strip('"')
    fields = quoted.split(",")
    if len(fields) < 13:
        return None
    last = _num(fields[1])
    return {
        "name": fields[9] if len(fields) > 9 else "离岸人民币",
        "last": last,
        "high": _num(fields[6]),
        "low": _num(fields[7]),
        "change_pct": _num(fields[10]),
        "change": _num(fields[11]),
        "date": fields[17] if len(fields) > 17 else None,
    }


def _num(text):
    try:
        if text in ("", "-", "0.00", "0.000"):
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _change_pct(prev, last):
    if prev in (None, 0) or last is None:
        return None
    return (last - prev) / prev * 100


def sina_quotes(codes):
    """批量请求新浪行情，返回 {code: parsed}。"""
    url = "https://hq.sinajs.cn/list=" + ",".join(codes)
    text, error = safe_get_text(url, headers=SINA_HEADERS)
    if not text:
        return {}, error
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        code = line.split("=", 1)[0].replace("var hq_str_", "").strip()
        parsed = None
        if code.startswith("sz"):
            parsed = _parse_sina_a(line)
        elif code.startswith("hk"):
            parsed = _parse_sina_hk(line)
        elif code.startswith("fx_"):
            parsed = _parse_sina_fx(line)
        if parsed:
            result[code] = parsed
    return result, None


# =========================================================
# Yahoo Finance（美股，容错）
# =========================================================

YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/{}"
    "?interval=1d"
    "&range=5d"
)


def yahoo_quote(symbol):
    url = YAHOO_URL.format(symbol)
    data, error = safe_get_json(url, timeout=20, retries=2)

    if not data:
        return {
            "symbol": symbol,
            "value": None,
            "change_pct": None,
            "currency": None,
            "source": "Yahoo Finance chart",
            "status": "error",
            "error": error,
        }

    result_list = data.get("chart", {}).get("result") or []
    if not result_list:
        return {
            "symbol": symbol,
            "value": None,
            "change_pct": None,
            "source": "Yahoo Finance chart",
            "status": "missing",
            "error": "Yahoo Finance 返回空 result",
        }

    result = result_list[0]
    meta = result.get("meta", {})
    value = meta.get("regularMarketPrice")
    previous = meta.get("previousClose") or meta.get("chartPreviousClose")
    change_pct = _change_pct(previous, value)

    return {
        "symbol": symbol,
        "value": value,
        "change_pct": change_pct,
        "currency": meta.get("currency"),
        "market_state": meta.get("marketState"),
        "exchange": meta.get("exchangeName"),
        "source": "Yahoo Finance chart",
        "source_url": f"https://finance.yahoo.com/quote/{symbol}",
        "status": "confirmed" if value is not None else "missing",
    }


# =========================================================
# 总采集
# =========================================================

def collect_market():
    """市场数据总采集：A股锂矿 + 港股 + 汇率 + 美股。"""

    # ---------- 新浪 A 股 + 港股 + 汇率 ----------
    sina_codes = list(A_SHARES.keys()) + list(H_SHARES.keys()) + ["fx_susdcnh"]
    sina_data, sina_error = sina_quotes(sina_codes)

    a_shares = {}
    for code, label in A_SHARES.items():
        item = sina_data.get(code)
        if item:
            item["label"] = label
            a_shares[label] = item

    h_shares = {}
    for code, label in H_SHARES.items():
        item = sina_data.get(code)
        if item:
            item["label"] = label
            h_shares[label] = item

    cnh = sina_data.get("fx_susdcnh")

    # ---------- Yahoo 美股 ----------
    us_stocks = {}
    for name, symbol in {"ALB": "ALB", "SQM": "SQM", "LAC": "LAC"}.items():
        us_stocks[name] = yahoo_quote(symbol)
        time.sleep(0.5)  # 温和限速，避免 Yahoo 429

    return {
        "a_shares_lithium": a_shares or (
            {"error": "新浪A股行情获取失败", "detail": sina_error}
        ),
        "h_shares_lithium": h_shares,
        "usd_cnh": {
            "value": cnh["last"] if cnh else None,
            "change_pct": cnh["change_pct"] if cnh else None,
            "change": cnh["change"] if cnh else None,
            "high": cnh["high"] if cnh else None,
            "low": cnh["low"] if cnh else None,
            "date": cnh["date"] if cnh else None,
            "source": "新浪财经 离岸人民币",
            "source_url": "https://finance.sina.com.cn/forex/",
            "status": "confirmed" if cnh else "error",
            "error": None if cnh else sina_error,
        },
        "us_stocks": us_stocks,
    }
