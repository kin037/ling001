iimport logging
import time

import requests


# =========================================================
# HTTP 基础请求模块
# =========================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        Chrome/131.0.0.0 "
        Safari/537.36"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "text/html,"
        "*/*"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
})


# =========================================================
# 通用 GET
# =========================================================

def request_get(
    url,
    timeout=20,
    headers=None,
    retries=3
):

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            logging.info(
                "HTTP GET [%s/%s]: %s",
                attempt,
                retries,
                url
            )

            response = SESSION.get(
                url,
                timeout=timeout,
                headers=headers
            )

            logging.info(
                "HTTP STATUS: %s",
                response.status_code
            )

            response.raise_for_status()

            return response

        except requests.RequestException as e:

            last_error = e

            logging.warning(
                "HTTP 请求失败 [%s/%s]: %s",
                attempt,
                retries,
                e
            )

            if attempt < retries:

                wait_seconds = attempt * 2

                logging.info(
                    "等待 %s 秒后重试...",
                    wait_seconds
                )

                time.sleep(
                    wait_seconds
                )

    raise last_error


# =========================================================
# 获取 JSON
# =========================================================

def get_json(
    url,
    timeout=20,
    headers=None,
    retries=3
):

    response = request_get(
        url=url,
        timeout=timeout,
        headers=headers,
        retries=retries
    )

    try:

        return response.json()

    except ValueError as e:

        logging.error(
            "JSON 解析失败: %s",
            e
        )

        logging.error(
            "响应内容前500字符: %s",
            response.text[:500]
        )

        raise


# =========================================================
# 获取网页文本
# =========================================================

def get_text(
    url,
    timeout=20,
    headers=None,
    retries=3
):

    response = request_get(
        url=url,
        timeout=timeout,
        headers=headers,
        retries=retries
    )

    return response.text


# =========================================================
# 安全获取 JSON
# =========================================================

def safe_get_json(
    url,
    timeout=20,
    headers=None,
    retries=3
):

    try:

        data = get_json(
            url=url,
            timeout=timeout,
            headers=headers,
            retries=retries
        )

        return data, None

    except Exception as e:

        logging.error(
            "GET JSON 最终失败: %s",
            url
        )

        logging.error(
            "错误原因: %s",
            e
        )

        return None, str(e)


# =========================================================
# 安全获取网页
# =========================================================

def safe_get_text(
    url,
    timeout=20,
    headers=None,
    retries=3
):

    try:

        data = get_text(
            url=url,
            timeout=timeout,
            headers=headers,
            retries=retries
        )

        return data, None

    except Exception as e:

        logging.error(
            "GET TEXT 最终失败: %s",
            url
        )

        logging.error(
            "错误原因: %s",
            e
        )

        return None, str(e)
