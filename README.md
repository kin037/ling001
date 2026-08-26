# 锂矿自动化情报室 V3

自动化锂矿股市场情报汇报系统。每天定时采集真实数据，生成情报日报并推送微信。

## 核心改进（V3 相对 V2）

原版 V2 的问题与修复：

| 问题 | V2 现状 | V3 修复 |
| --- | --- | --- |
| 没有锂价核心数据 | 只有美股股价和汇率 | ✅ 新增碳酸锂期货行情（广期所全合约，新浪财经接口） |
| ASX 抓的是导航文字 | `asx.com.au` 旧接口返回帮助页 | ✅ 改用 ASX 官方公告 API（Markit Digital），返回真实公告 |
| ALB/SQM IR 抓的是菜单 | JS 动态页面，静态抓取全是导航 | ✅ 明确标注失败/缺失，不编造数据 |
| A 股锂矿股缺失 | 完全没有 | ✅ 新增 5 只 A 股 + 港股赣锋锂业（新浪接口） |
| FOMC 只是页面文本 | 抓 5000 字符全文 | ✅ 解析出每场会议日期与状态 |
| Google News 单一来源 | 易被限流 | ✅ Bing News 主源 + Google 备源双路冗余 |
| DeepSeek 模型名错误 | `deepseek-v4-flash`（非官方模型） | ✅ 修正为 `deepseek-chat`，可环境变量覆盖 |
| 无 AI key 时报告简陋 | 仅 5 行文本 | ✅ 本地规则引擎生成结构化降级报告 |
| Windows 无法运行 | tzdata 缺失 + GBK 打印崩溃 | ✅ 时区容错 + UTF-8 输出 |

## 数据源（全部无需登录）

| 数据 | 来源 | 接口 |
| --- | --- | --- |
| 碳酸锂期货（主力+各合约） | 新浪财经（广期所行情） | `hq.sinajs.cn/list=nf_LC0,...` |
| A股锂矿（天齐/赣锋/盐湖/中矿/永兴） | 新浪财经 | `hq.sinajs.cn/list=szXXXXXX` |
| 港股锂矿（赣锋锂业H） | 新浪财经 | `hq.sinajs.cn/list=hk01772` |
| 离岸人民币 USD/CNH | 新浪财经 | `hq.sinajs.cn/list=fx_susdcnh` |
| 美股锂业（ALB/SQM/LAC） | Yahoo Finance | `query1.finance.yahoo.com/v8/...` |
| FOMC 会议日程 | 美联储官网 | `federalreserve.gov/monetarypolicy/fomccalendars.htm` |
| ASX 官方公告 | ASX Markit Digital API | `asx.api.markitdigital.com/.../announcements` |
| 行业新闻 | Bing News RSS + Google News RSS | 双路冗余 |

## 快速开始

```bash
pip install -r requirements.txt

# 不带 AI key 运行：生成本地规则降级报告
python main.py

# 带 AI 分析运行
export DEEPSEEK_API_KEY="sk-xxxx"
export DEEPSEEK_MODEL="deepseek-chat"   # 可选
export PUSHPLUS_TOKEN="xxxx"            # 可选，微信推送
python main.py
```

## GitHub Actions 自动运行

仓库 Settings → Secrets 添加：

- `DEEPSEEK_API_KEY`：DeepSeek API 密钥（可选，不配则用本地降级报告）
- `PUSHPLUS_TOKEN`：PushPlus 微信推送令牌（可选）

每天北京时间 18:30 自动运行（`30 10 * * *` UTC），也可在 Actions 页面手动触发 `workflow_dispatch`。

## 输出

- `data/latest.json`：最新原始数据快照
- `data/reports/YYYY-MM-DD_daily.json`：每日报告（含 markdown）
- 微信推送（配置 PUSHPLUS_TOKEN 后）

## 数据真实性原则

1. 实际开工率没有来源就显示缺失，AI 不得自行补全
2. 预测排产不能作为实际生产数据
3. 期货价格是盘面预期，不等同于现货成交价
4. 境外减产必须找到官方来源才算确认
5. 新闻线索（RSS）仅作参考，标注 `discovery_only`
