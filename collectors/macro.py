from datetime import datetime, timezone

from bs4 import BeautifulSoup

from collectors.http import safe_get_text


FOMC_URL = (
    "https://www.federalreserve.gov/"
    "monetarypolicy/fomccalendars.htm"
)


def collect_fomc():

    html, error = safe_get_text(
        FOMC_URL
    )

    if not html:

        return {

            "source":
                "Federal Reserve",

            "source_url":
                FOMC_URL,

            "status":
                "error",

            "error":
                error,

            "upcoming":
                []
        }

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = " ".join(
        soup.stripped_strings
    )

    return {

        "source":
            "Federal Reserve",

        "source_url":
            FOMC_URL,

        "retrieved_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            "confirmed",

        "page_excerpt":
            text[:5000],

        "note":
            "会议时间以美联储官方FOMC页面为准。"
    }


def collect_macro():

    return {

        "fomc":
            collect_fomc()
    }
