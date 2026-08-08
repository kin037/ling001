import logging
import requests

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "ling001-lithium-intel/2.0 (+GitHub Actions)",
    "Accept": "application/json,text/plain,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def get_json(url, timeout=20, headers=None):
    response = SESSION.get(
        url,
        timeout=timeout,
        headers=headers
    )

    response.raise_for_status()

    return response.json()


def get_text(url, timeout=20, headers=None):
    response = SESSION.get(
        url,
        timeout=timeout,
        headers=headers
    )

    response.raise_for_status()

    return response.text


def safe_get_json(url, timeout=20, headers=None):

    try:
        data = get_json(
            url,
            timeout=timeout,
            headers=headers
        )

        return data, None

    except Exception as e:

        logging.warning(
            "GET JSON failed %s: %s",
            url,
            e
        )

        return None, str(e)


def safe_get_text(url, timeout=20, headers=None):

    try:

        data = get_text(
            url,
            timeout=timeout,
            headers=headers
        )

        return data, None

    except Exception as e:

        logging.warning(
            "GET TEXT failed %s: %s",
            url,
            e
        )

        return None, str(e)
