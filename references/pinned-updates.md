# 固定置顶帖的更新计划

固定入口来自 `public/metrics.json` 的 `launch_post`，源码为 https://github.com/LIghtJUNction/x-quality-growth 。每次先检查原帖编辑入口及限制；能编辑则更新同一原帖，不能编辑则在固定帖下回复进展。检查置顶仍存在，不擅自换入口或删除原帖。

`scripts/plan_update.py` 只生成离线计划和记录人工核验的结果，**不发送 X 帖子、不启动浏览器、不创建定时任务**。没有连接的调度器与真实执行记录，就必须说明未配置跨会话后台检查。

## 生成计划

```sh
python3 scripts/plan_update.py plan --language zh
python3 scripts/plan_update.py plan --language en --change 'Fixed incomplete measurement labels'
```

默认读取公开指标，计划写入忽略的 `runs/pinned-update-plan.json`；已发布状态存 `runs/pinned-update-state.json`。只在总粉丝、蓝 V 名单人数、质量判定、事先质量标准或明确的技能改进有变化时建议更新。更换采集时间而数值相同、帖子计数增加、GitHub 热度增加均不单独触发推广。默认至少间隔 60 分钟是可调整的运营预算，不是 X 安全阈值。必须核对 `should_update`；false 时没有可发布草稿。

各类指标保留各自采集时间，不能把旧蓝 V 测量写成最新总粉丝采集时刻。未分类占比单列，高质量占比在仍有未知者时只称下界。认证名单新观察到的人数不是确认新增，公开互动可能包含自己的点赞/回复，也不是技能效果的证明。首次观察没有保留时间时不推造时间。

已有公开 `progress_updates` 但本地没有发布快照时，按其中 `reported_profile_observation` 找到已报告粉丝数。其他没有完整历史的指标基线明确记未知，不能声称当时质量已公布；只在该指标有晚于上次更新的真实观测时触发，避免重复推广。质量分类完成时间可单独记录 `blue_cohort.classified_at`；未提供时沿用队列 `window_ended_at`，不伪造分类时间。后续确认发布后改用完整本地快照；各项观测时间回退均拒绝。实际改进用 `--change` 指定；需是已经完成、可验证的变化，不能填营销口号。相同改进重复填写不会再次触发。

## 浏览器确认之后才记录

实际编辑/回复仍由获授权的浏览器执行。重新打开永久链接，核对文本、父帖、作者和持久状态；点击发送或看到编辑框不算成功。将真实观察写入 `runs/browser-publication.json`：

```json
{
  "source": "browser",
  "confirmed": true,
  "method": "thread_reply",
  "url": "https://x.com/YOUR_ACCOUNT/status/ACTUAL_REPLY_ID",
  "parent": "https://x.com/YOUR_ACCOUNT/status/ACTUAL_FIXED_POST_ID",
  "verified_at": "ACTUAL_TIME_WITH_TIMEZONE",
  "observation": "重新打开回复，核对正文、作者和固定父帖；此处填写真实观察"
}
```

这是占位说明，不是已发布证据。编辑原帖时用 `method: edit` 且 `url` 等于固定入口。不要复制假 ID 或假时间以通过验证；脚本不能独立证明浏览器观察真实，执行者负责提供证据。

```sh
python3 scripts/plan_update.py record --browser-evidence runs/browser-publication.json
```

计划生成不会改变已发布基线；只有该命令接受真实、显式 `confirmed: true`、合法永久链接和晚于计划的核验记录，才写入本地历史。重复或过期计划不能再次记成功。同步公开 `progress_updates` 仍需维护者核对后进行；本脚本不将私人观察原文上传 GitHub。

集成接口为 `make_plan(metrics, state, now=..., language='zh', changes=..., min_interval_minutes=60)` 与 `record_publication(plan, evidence, state)`。按本轮真实观察调用，先判断计划再浏览器核验，最后记录。持续运行必须另有实际授权、已配置的调度器和执行证据。
