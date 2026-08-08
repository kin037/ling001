import json
import os

from datetime import datetime

import requests


DEEPSEEK_URL = (
    "https://api.deepseek.com/"
    "chat/completions"
)


SYSTEM_PROMPT = """
你是锂产业链专业情报分析员。

你的任务不是创造数据，而是分析已经获得的数据。

必须遵守以下规则：

1. 不能自己补充缺失数字。
2. 不能把预测值写成实际值。
3. 不能把搜索新闻写成官方公告。
4. 必须区分：
   CONFIRMED
   DISCOVERY_ONLY
   UNVERIFIED
   MISSING

5. 如果实际开工率缺失：
   必须明确告诉用户数据缺失。

6. 如果供应端减产没有官方来源：
   不得写成已经确认减产。

7. 如果宏观数据恶化：
   可以提出降仓或暂缓。

8. 不允许因为用户希望上涨，
   就人为解释成利好。

最终输出应该重点分析：

- 锂价格
- 实际开工率
- 进出口
- 矿山供应
- ASX
- Albemarle
- SQM
- USD/CNH
- FOMC
- 数据可信度
- 仓位风险
"""


def deepseek_analyze(
    snapshot
):

    api_key = os.getenv(
        "DEEPSEEK_API_KEY"
    )

    if not api_key:

        return None

    payload = {

        "model":
            os.getenv(
                "DEEPSEEK_MODEL",
                "deepseek-v4-flash"
            ),

        "messages": [

            {
                "role":
                    "system",

                "content":
                    SYSTEM_PROMPT
            },

            {
                "role":
                    "user",

                "content":
                    json.dumps(
                        snapshot,
                        ensure_ascii=False
                    )
            }
        ],

        "temperature":
            0.1,

        "max_tokens":
            3000
    }

    response = requests.post(

        DEEPSEEK_URL,

        headers={

            "Authorization":
                f"Bearer {api_key}",

            "Content-Type":
                "application/json"
        },

        json=payload,

        timeout=90
    )

    response.raise_for_status()

    return (
        response
        .json()
        ["choices"][0]
        ["message"]["content"]
    )


def fallback_text(
    snapshot
):

    signals = snapshot[
        "signals"
    ]

    cnh = snapshot[
        "market"
    ][
        "USD_CNH"
    ]

    return (

        "系统数据健康度："

        + signals[
            "data_health"
        ][
            "overall"
        ]

        + "\n\n"

        + "USD/CNH："

        + str(
            cnh.get(
                "value",
                "--"
            )
        )

        + "\n\n"

        + "USD/CNH日变动："

        + str(
            cnh.get(
                "change_pct",
                "--"
            )
        )

        + "%\n\n"

        + "行动结论："

        + signals[
            "action"
        ]

        + "\n\n"

        + "核心开工率："

        + "未获得可靠结构化数据，"
          "系统拒绝让AI自行补值。"
    )


def build_report(
    snapshot
):

    # 使用中国北京时间
    from zoneinfo import ZoneInfo

    china_tz = ZoneInfo(
        "Asia/Shanghai"
    )

    now = datetime.now(
        china_tz
    )

    try:

        ai_result = (
            deepseek_analyze(
                snapshot
            )
        )

        if not ai_result:

            ai_result = fallback_text(
                snapshot
            )

    except Exception as e:

        ai_result = (
            "DeepSeek分析失败，"
            "系统已经自动切换为保守模式。\n\n"
            + str(e)
            + "\n\n"
            + fallback_text(
                snapshot
            )
        )

    title = (
        f"锂矿自动化情报日报｜"
        f"{now:%Y-%m-%d %H:%M}"
    )

    markdown = (

        f"# {title}\n\n"

        "## 一、AI核心判断\n\n"

        + ai_result

        + "\n\n"

        "## 二、数据真实性规则\n\n"

        "- 实际开工率没有来源就显示缺失。\n"

        "- 预测排产不能作为实际生产数据。\n"

        "- 境外减产必须寻找官方来源。\n"

        "- USD/CNH作为离岸人民币指标。\n"

        "- FOMC以美联储官方信息为准。\n"

        "- AI不得自行补充数据。\n"
    )

    return {

        "title":
            title,

        "generated_at":
            now.isoformat(),

        "markdown":
            markdown,

        "snapshot":
            snapshot
    }
