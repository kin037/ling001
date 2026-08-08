from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.http import safe_get_text


ASX_URL = (
    "https://www.asx.com.au/"
    "asx/v2/statistics/announcements.do"
)

ALB_IR = (
    "https://investors.albemarle.com/"
    "news-and-events/news/default.aspx"
)

SQM_IR = (
    "https://ir.sqm.com/"
    "news-events/news"
)


def extract_titles(
    html,
    limit=15
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    titles = []

    for link in soup.find_all(
        "a",
        href=True
    ):

        title = " ".join(
            link.stripped_strings
        )

        if title and len(title) > 8:

            titles.append(
                title[:240]
            )

        if len(titles) >= limit:
            break

    return list(
        dict.fromkeys(titles)
    )


def fetch_page(
    name,
    url
):

    html, error = safe_get_text(
        url
    )

    if not html:

        return {

            "name":
                name,

            "source_url":
                url,

            "status":
                "error",

            "error":
                error
        }

    return {

        "name":
            name,

        "source_url":
            url,

        "retrieved_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            "confirmed",

        "titles":
            extract_titles(
                html
            )
    }


def collect_asx():

    return fetch_page(
        "ASX announcements",
        ASX_URL
    )


def collect_official_supply():

    return {

        "ASX":
            collect_asx(),

        "ALB":
            fetch_page(
                "Albemarle Investor Relations",
                ALB_IR
            ),

        "SQM":
            fetch_page(
                "SQM Investor Relations",
                SQM_IR
            ),

        "verification_rule":

            "供应端减产信息只有在官方来源中找到原始证据后才允许标记为 VERIFIED。"
    }
