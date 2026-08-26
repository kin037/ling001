import os

import requests


def pushplus(
    title,
    content
):

    token = os.getenv(
        "PUSHPLUS_TOKEN"
    )

    if not token:

        print(
            "PUSHPLUS_TOKEN没有配置，跳过微信推送。"
        )

        return

    url = (
        "https://www.pushplus.plus/send"
    )

    payload = {

        "token":
            token,

        "title":
            title,

        "content":
            content,

        "template":
            "markdown"
    }

    response = requests.post(

        url,

        json=payload,

        timeout=30
    )

    response.raise_for_status()

    print(
        "PushPlus微信推送成功。"
    )
