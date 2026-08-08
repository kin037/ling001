from datetime import datetime, timezone

from collectors.http import safe_get_json


# =========================================================
# Yahoo Finance
# =========================================================

YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/{}"
    "?interval=1d"
    "&range=5d"
)


# =========================================================
# Yahoo Finance 单个行情
# =========================================================

def yahoo_quote(symbol):

    url = YAHOO_URL.format(symbol)

    data, error = safe_get_json(
        url,
        timeout=20,
        retries=3
    )

    # -----------------------------------------
    # 请求失败
    # -----------------------------------------

    if not data:

        return {

            "symbol": symbol,

            "value": None,

            "change_pct": None,

            "currency": None,

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "source":
                "Yahoo Finance chart",

            "source_url":
                f"https://finance.yahoo.com/quote/{symbol}",

            "status":
                "error",

            "error":
                error
        }

    # -----------------------------------------
    # 获取 result
    # -----------------------------------------

    result_list = (
        data
        .get("chart", {})
        .get("result")
        or []
    )

    if not result_list:

        return {

            "symbol": symbol,

            "value": None,

            "change_pct": None,

            "currency": None,

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "source":
                "Yahoo Finance chart",

            "source_url":
                f"https://finance.yahoo.com/quote/{symbol}",

            "status":
                "missing",

            "error":
                "Yahoo Finance 返回空 result"
        }

    # -----------------------------------------
    # 解析数据
    # -----------------------------------------

    result = result_list[0]

    meta = result.get(
        "meta",
        {}
    )

    value = meta.get(
        "regularMarketPrice"
    )

    previous = (
        meta.get("previousClose")
        or
        meta.get("chartPreviousClose")
    )

    change_pct = None

    if (
        value is not None
        and previous not in (None, 0)
    ):

        change_pct = (
            (value - previous)
            / previous
            * 100
        )

    # -----------------------------------------
    # 判断数据状态
    # -----------------------------------------

    if value is not None:

        status = "confirmed"

    else:

        status = "missing"

    return {

        "symbol":
            symbol,

        "value":
            value,

        "change_pct":
            change_pct,

        "currency":
            meta.get(
                "currency"
            ),

        "market_state":
            meta.get(
                "marketState"
            ),

        "exchange":
            meta.get(
                "exchangeName"
            ),

        "retrieved_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source":
            "Yahoo Finance chart",

        "source_url":
            f"https://finance.yahoo.com/quote/{symbol}",

        "status":
            status
    }


# =========================================================
# 市场数据总采集
# =========================================================

def collect_market():

    symbols = {

        # 离岸人民币
        "USD_CNH":
            "CNH=X",

        # 美国锂业公司
        "ALB":
            "ALB",

        "SQM":
            "SQM",

        "LAC":
            "LAC",
    }

    result = {}

    for name, symbol in symbols.items():

        result[name] = yahoo_quote(
            symbol
        )

    return result
