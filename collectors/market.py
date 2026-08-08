from datetime import datetime, timezone

from collectors.http import safe_get_json


YAHOO_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/{}?interval=1d&range=5d"
)


def yahoo_quote(symbol):

    data, error = safe_get_json(
        YAHOO_URL.format(symbol)
    )

    if not data:

        return {
            "symbol": symbol,
            "value": None,
            "change_pct": None,
            "source": "Yahoo Finance chart",
            "status": "error",
            "error": error
        }

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
            "status": "missing",
            "source": "Yahoo Finance chart"
        }

    result = result_list[0]

    meta = result.get("meta", {})

    value = meta.get(
        "regularMarketPrice"
    )

    previous = (
        meta.get("previousClose")
        or meta.get("chartPreviousClose")
    )

    change_pct = None

    if value is not None and previous:

        change_pct = (
            (value - previous)
            / previous
            * 100
        )

    return {

        "symbol": symbol,

        "value": value,

        "change_pct": change_pct,

        "currency": meta.get(
            "currency"
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
            "confirmed"
            if value is not None
            else "missing"
    }


def collect_market():

    symbols = {

        # 离岸人民币
        "USD_CNH": "CNH=X",

        # 海外锂业公司
        "ALB": "ALB",

        "SQM": "SQM",

        "LAC": "LAC",
    }

    result = {}

    for name, symbol in symbols.items():

        result[name] = yahoo_quote(
            symbol
        )

    return result
