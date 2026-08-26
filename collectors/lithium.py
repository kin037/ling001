# -*- coding: utf-8 -*-
"""
碳酸锂期货价格采集器
========================

数据源：新浪财经期货行情接口（无需登录 / 无需 cookie）

- 主力连续合约：nf_LC0
- 具体合约：nf_LC2608 ~ nf_LC2612（广期所碳酸锂）

返回 GBK 编码文本，格式：
    var hq_str_nf_LC0="碳酸锂连续,时间,开盘,最高,最低,昨收,买价,卖价,
                       最新价,结算价,昨结算,买量,卖量,成交量,持仓量,
                       ...,品种,日期,..."

字段索引（逗号分隔）：
    [0]  名称
    [1]  时间
    [2]  开盘价
    [3]  最高价
    [4]  最低价
    [5]  收盘价（当日）
    [6]  买价
    [7]  卖价
    [8]  最新价
    [9]  结算价（当日加权）
    [10] 昨结算价（期货涨跌幅官方基准）
    [11] 买量
    [12] 卖量
    [13] 成交量（手）
    [14] 持仓量（手）
    [15] （空）
    [16] 品种名
    [17] 行情日期
    [18] 主力标志（1=当前主力）
"""

from datetime import datetime, timezone

from collectors.http import safe_get_text

SINA_FUT_URL = "https://hq.sinajs.cn/list={codes}"

SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
}

# 碳酸锂期货合约：主力连续 + 当前活跃合约
# 注：近月合约会随时间变化，LC0 始终代表主力连续，
# 具体合约列表按"当前年月 + 未来12个月"动态生成，过期合约会自动失效。
FUTURE_MONTHS = ["01", "02", "03", "04", "05", "06",
                 "07", "08", "09", "10", "11", "12"]


def _contract_codes(now=None):
    """动态生成碳酸锂合约代码列表（主力 + 未来12个月）。"""
    now = now or datetime.now()
    codes = ["nf_LC0"]
    year = now.year
    month = now.month
    for i in range(13):
        m = (month + i - 1) % 12 + 1
        y = year + (month + i - 1) // 12
        # 广期所碳酸锂合约代码规则：LC + 年(2位) + 月(2位)
        codes.append(f"nf_LC{str(y)[-2:]}{FUTURE_MONTHS[m - 1]}")
    return codes


def _parse_line(line):
    """解析一行 hq_str_nf_XXX="..." 数据。"""
    if "=" not in line:
        return None
    _, quoted = line.split("=", 1)
    quoted = quoted.strip()
    if not quoted.startswith('"'):
        return None
    quoted = quoted[1:]
    if quoted.endswith(";"):
        quoted = quoted[:-1]
    if quoted.endswith('"'):
        quoted = quoted[:-1]
    fields = quoted.split(",")
    if len(fields) < 19:
        return None
    return {
        "contract": fields[0],
        "open": _num(fields[2]),
        "high": _num(fields[3]),
        "low": _num(fields[4]),
        "close": _num(fields[5]),
        "last": _num(fields[8]),
        "settle": _num(fields[9]),
        "prev_settle": _num(fields[10]),
        "volume": _num(fields[13]),
        "open_interest": _num(fields[14]),
        "product": fields[16],
        "date": fields[17],
        "is_main": fields[18] == "1" if len(fields) > 18 else False,
    }


def _num(text):
    """字符串转数字，失败返回 None。"""
    try:
        if text in ("", "-", "0.000", "0"):
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _change_pct(prev, last):
    if prev in (None, 0) or last is None:
        return None
    return (last - prev) / prev * 100


def sina_lithium_futures():
    """抓取碳酸锂期货行情（多合约一次请求）。"""
    codes = _contract_codes()
    url = SINA_FUT_URL.format(codes=",".join(codes))

    text, error = safe_get_text(url, headers=SINA_HEADERS)

    if not text:
        return {
            "status": "error",
            "source": "新浪财经-广期所碳酸锂期货",
            "source_url": "https://finance.sina.com.cn/futures/quotes/LC0.shtml",
            "error": error,
            "contracts": [],
        }

    contracts = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "hq_str_nf_" not in line:
            continue
        parsed = _parse_line(line)
        if not parsed:
            continue
        # 只保留有实际行情的合约（日期与最新交易日一致）
        if parsed["last"] is None:
            continue
        # 期货涨跌幅按交易所标准：相对昨结算价
        parsed["change_pct"] = _change_pct(
            parsed["prev_settle"],
            parsed["last"],
        )
        contracts.append(parsed)

    if not contracts:
        return {
            "status": "error",
            "source": "新浪财经-广期所碳酸锂期货",
            "source_url": "https://finance.sina.com.cn/futures/quotes/LC0.shtml",
            "error": "未解析到任何有效合约数据",
            "contracts": [],
        }

    # 主力 = LC0 或 is_main 标志的合约，其余按持仓量排序取前5
    main = None
    others = []
    main_oi = -1
    for c in contracts:
        if c["contract"] == "碳酸锂连续" or c["is_main"]:
            if main is None or (c["open_interest"] or 0) > main_oi:
                main = c
                main_oi = c["open_interest"] or 0
        else:
            others.append(c)

    # 排除与主力完全相同的合约（主力连续跟随主力合约，会重复）
    others = [
        c for c in others
        if not (c["last"] == main["last"] and c["contract"] != main["contract"] and c["open_interest"] == main["open_interest"])
    ]
    others.sort(key=lambda x: (x["open_interest"] or 0), reverse=True)
    others = others[:5]

    return {
        "status": "confirmed",
        "source": "新浪财经-广期所碳酸锂期货",
        "source_url": "https://finance.sina.com.cn/futures/quotes/LC0.shtml",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "main_contract": main,
        "top_contracts": others,
        "note": "价格为广期所碳酸锂期货结算行情，单位为元/吨；"
                "现货价未获得可靠公开源时，以主力期货价格作为价格锚。",
    }


def collect_lithium():
    """对外统一入口。"""
    return {
        "carbonate_futures": sina_lithium_futures(),
    }
