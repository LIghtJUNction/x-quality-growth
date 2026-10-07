# 实验与测量

## 质量判定

仅依据公开职业/内容证据，不按语言、国籍、性别或政治/宗教信仰筛选。blue 是范围条件，不是质量得分。对新增者读简介与至少 3 条近期原创内容，再给三个布尔项：

1. `relevant`：公开内容与本账号事先确定的主题/目标受众相符。
2. `original`：能看到原创方法、作品、案例或独立观点，而不是仅有转贴/互关口号。
3. `substantive`：公开回复/讨论含实质信息，存在可以继续交流的话题。

三项均 true 且附公开证据 URL 才标 `high`。明确不满足任一项标 `not_high`，没读够、账号受保护或没看到证据标 `unknown`。这是严格的运营评分，不宣称鉴定真伪或专业能力。标准按账号定位调整一次并记录，跨轮保持不变；不为涨比例改变标准。

## 快照格式

`python3 scripts/measure.py before.json after.json`。示例在 `examples/`，全部是虚构数据。真实记录放忽略的 `runs/`。

```json
{
  "account": "example_owner",
  "observed_at": "2026-10-08T04:00:00+08:00",
  "scope": "all_followers",
  "complete": true,
  "evidence": "完整列表采集或获授权的数据导出路径",
  "total_followers": 1,
  "followers": [{
    "id": "123456789",
    "handle": "example_follower",
    "badge": "blue",
    "quality": {
      "status": "high",
      "relevant": true, "original": true, "substantive": true,
      "evidence": ["https://x.com/example_follower/status/123"]
    }
  }],
  "posts": {
    "https://x.com/example_owner/status/123": {
      "replies": 0, "likes": 0, "reposts": 0,
      "bookmarks": null, "views": 10
    }
  }
}
```

scope 可为 `all_followers` 或 `verified_followers`。complete=true 必须有完整性证据；只有全粉丝完整快照可以排除老粉新认证。全粉丝完整快照的 `total_followers` 必须等于名单长度；分页采集中总数波动应重采或标 partial。用户 ID 可获授权读取时优先记录；只有 handle 时有改名歧义，工具不把它算确认新增。

时区明确、账号一致、after 时间较晚。每个 id/handle 唯一，不能把同一账号多次加载计成多个粉丝。只看蓝 V 列表与全粉丝列表不可混比。

## 输出解释

- confirmed_new_blue：在两次完整全粉丝、全稳定 ID 快照中，新增身份且 after 为 blue 的人数。
- observed_blue_arrivals：新观察到的蓝 V 身份数。部分列表、认证列表或 handle 匹配时只用这项，不声称确认新增。
- existing_became_blue：同一已存在粉丝从非 blue 变 blue，单列而不算新增粉丝。
- observed_blue_departures：前轮 blue 后轮名单没出现；部分列表不证明实际取关。
- quality_share：新增/观察到的新 blue 中 high/N；unknown 留分母，另输出可能区间 high/N 至 (high+unknown)/N。N=0 为 null。未知者不能伪装成“已确认低质”。
- quality_share_wilson95：对已确认新增、且全部已完成质量判定的样本给 Wilson 区间，反映小样本不确定性；不是因果置信度。
- 同一帖子两次公开计数相减；计数不可见、之前没采集、计数下降或帖子缺失时增量为 null，保留原因。新帖从发布时确认的 0 计数开始测，不假造之前的基线。
- 实验期存在其他人/自动任务运营时记录混杂因素。仅看粉丝先后变化不能给单帖因果归因。

实际日志包括时间、action type、target URL、策略版本、变量、attempted/confirmed/failed、证据与固定窗口。发布需记录 permalink；关注需重新打开检查；转贴/点赞需检查持久状态。初始界面按钮不等于保存。

## 优化与停止

每轮对比新增 blue 数 N、高质量 H、H/N 与行动预算、观察时间。报告两个指标同时变化，保留帕累托更好的方案（至少一个提高且另一个不下降）；冲突时优先保护受众匹配与原创交流，再试另一变量。不把 1 人、5 分钟的变化说成策略胜出。没有新增时比例未定义，应调整话题/内容价值/分发入口，不通过随便判低质或减分母制造提高。

可见负反馈、重复状态回退或平台提示限制时，停止对应动作，记录风险，不“优化”到规避限制。未设调度器不得把 24/72 小时窗口标完成。
