import os

from datetime import datetime, timezone

from urllib.parse import quote

from xml.etree import ElementTree

from collectors.http import safe_get_text


QUERIES = {

    "battery_operating_rate":

        os.getenv(
            "INDUSTRY_QUERY_1",
            "锂电池 开工率 实际 调研"
        ),

    "lithium_supply":

        os.getenv(
            "INDUSTRY_QUERY_2",
            "锂盐 开工率 产量 调研"
        ),
}


def google_news_rss(
    query
):

    url = (
        "https://news.google.com/rss/search?"
        + "q="
        + quote(query)
        + "&hl=zh-CN"
        + "&gl=CN"
        + "&ceid=CN:zh-Hans"
    )

    xml, error = safe_get_text(
        url
    )

    if not xml:

        return {

            "status":
                "error",

            "source_url":
                url,

            "error":
                error
        }

    try:

        root = ElementTree.fromstring(
            xml
        )

        items = []

        for item in root.findall(
            ".//item"
        )[:10]:

            items.append({

                "title":
                    item.findtext(
                        "title"
                    ),

                "link":
                    item.findtext(
                        "link"
                    ),

                "published":
                    item.findtext(
                        "pubDate"
                    ),

                "description":
                    (
                        item.findtext(
                            "description"
                        )
                        or ""
                    )[:1000]
            })

        return {

            "status":
                "discovery_only",

            "source_url":
                url,

            "retrieved_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "items":
                items,

            "warning":
                "RSS搜索结果只能作为线索，不能直接作为真实开工率。"
        }

    except Exception as e:

        return {

            "status":
                "error",

            "source_url":
                url,

            "error":
                str(e)
        }


def collect_industry_discovery():

    result = {}

    for key, query in QUERIES.items():

        result[key] = google_news_rss(
            query
        )

    return result
