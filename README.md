# RISE — 递归自我涨粉

<p align="center"><img src="assets/rise-hero.svg" width="100%" alt="RISE · Recursive Iterative Social Expansion · 递归自我涨粉：X 与 GitHub 互相引用，真实反馈推动下一轮内容" /></p>

<p align="center"><a href="references/algorithm.md"><img src="assets/badge-source.svg" alt="基于 X 开源推荐算法" /></a> <a href="public/metrics.json"><img src="assets/badge-evidence.svg" alt="真实观察，效果待验证" /></a> <a href="LICENSE"><img src="assets/badge-license.svg" alt="MIT license" /></a></p>

<p align="center"><b>Recursive Iterative Social Expansion</b><br/>X 自动涨粉与高质量增长技能<br/><a href="README.md">简体中文</a> · <a href="README.en.md">English</a></p>

## 递归自我涨粉，是整个项目的核心

**X 展示真实成果 → GitHub 开源可用技能 → 用户使用、反馈与 PR → 更新实测数据 → X 分享新的有价值结果 → 再次传播。**

每轮传播引用下一层证据：X 帖子链接本仓库；本仓库展示该帖的真实曝光、回复、点赞与收藏。热度是传播反馈，不是单独证明涨粉因果的证据。循环不等于无限刷屏；没有新价值或新数据就不重复推广。

**本技能基于 X 开源推荐算法 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)。** 用「行动 → 观察 → 反馈 → 调整」同时优化新增蓝 V 数量与高质量占比，争取增长和长期交流。支持浏览器行动、离线测量、个人 fork 与共同迭代。不是 X 官方产品，不保证指数增长。

## 真实实验记录

<img src="assets/metrics.svg" width="100%" alt="真实账号粉丝变化及蓝 V 质量分类，未知值明确保留" />

<!-- RISE:METRICS:START -->
| 真实观察 | 当前结果 |
| --- | --- |
| 总粉丝 | 175 → 243，净变化 **+68** |
| 新观察到的蓝 V | **12** 个；精确新增粉丝未确认 |
| 质量分类 | 0 确认高质 / 4 未匹配主题 / 8 待判定 |
| 高质量占比 | 分类尚未完成，不能把未知当 0% |
| 最新账号采集 | 2026-10-07T22:54:52.489Z |
| 观察队列质量：已确认下界 / 可能上界 | 0.0%–66.7% |
| 首次账号采集 | Timestamp unavailable |
| 最新蓝 V 名单采集（独立窗口） | 2026-10-07T21:04:50.311Z |
| GitHub stars / forks | 1 / 0 · 2026-10-07T21:22:27.159136+00:00 |

上下界描述观察到的蓝 V 队列，并非已确认新增粉丝；无法排除认证升级及改名。公开互动计数可能包含账号自身操作。

[RISE launch post](https://x.com/LIghtJUNction_x/status/2107943767382847844)

[置顶帖下的最新进展](https://x.com/LIghtJUNction_x/status/2107969836794171834)
<!-- RISE:METRICS:END -->

完整原始聚合记录：[public/metrics.json](public/metrics.json)。首次总粉丝检查没有保留精确时间；这轮有其他账号活动，且首轮数据早于技能完成。**总粉丝净变化不等于蓝 V 新增，认证名单新增不一定是新关注；高质量分类还未完成。** 我们公开这些限制，而不是把热度包装成保证效果。

最新回测：[约 67 分钟的首次复查](public/backtests/2026-10-08.md)。方法帖 34 浏览、1 条外部回应、0 主页访问；账号同期净增 16，尚不能归因于方法帖。已修正用刚发布低计数判断内容失败的假说。

## X × GitHub：互相引用的反馈循环

<img src="assets/feedback.svg" width="100%" alt="X 实测帖与技能介绍帖的公开反馈" />

示例来自真实发布内容：

- [首轮 Codex 提示词实验](https://x.com/LIghtJUNction_x/status/2107934424151335154)
- [AI 编程回复：git diff 会漏掉什么](https://x.com/LIghtJUNction_x/status/2107936031907737758)
- [创作者收益讨论：如何衡量粉丝质量](https://x.com/LIghtJUNction_x/status/2107936390185193718)
- [回应 AI 视频创作者：口播一致性的对照测试](https://x.com/LIghtJUNction_x/status/2107947524829127073)

X 介绍帖作为固定入口：有新实测或实际改进时优先更新原置顶帖；无法编辑时在原帖下追加带时间戳的进展回复。

GitHub stars/forks 每 6 小时通过 GitHub Actions 更新；X 热度和粉丝数据仅在实际浏览器复查后更新，不将 GitHub 刷新时间冒充 X 数据采集时间。README 同步生成图表，保留历史观察。没有配置无人值守 X 调度器。

公开互动计数可能包含账号自身点赞或进展回复，不能将自互动当作独立受众认可。

## 核心区别

- 算法分析固定提交，代码事实有逐文件出处，策略推断单列。
- 权重乘预测概率，不用“1 评论=10 赞”之类兑换公式。
- 蓝 V 与高质量分别判断；只基于公开相关性、原创内容和实质交流。
- 新增、流失、净变化和老粉新认证分开；部分名单不报精确新增。
- 未知数据记 null；质量未知留在分母；小样本不包装成成功证明。
- 关注、发帖要核对实际保存；遇到限制停止对应动作。

## 安装与使用

把本仓库作为技能目录克隆到 Codex 的 skills 文件夹（已有目录不要覆盖）：

```sh
git clone https://github.com/LIghtJUNction/x-quality-growth.git ~/.codex/skills/x-quality-growth
```

已有源码仓库可用符号链接安装，继续在源码目录迭代。

```text
请使用 $x-quality-growth，操作我当前登录的 X 账号。
定位：AI 工具、独立开发、产品商业化。
授权：发帖、点赞、实质评论、精选引用、关注相关蓝 V 与回关。
目标：提高每轮新增蓝 V 数量及其中高质量占比。
先记录基线，执行一轮小批次，核对动作保存，观察后汇报。
使用 #蓝v互关 #真诚交友 #浇朋友 #创作者收益 #X变现 #流量 发现账号，
内容按实际相关性选标签，不重复模板刷屏。遇到平台限制停止对应动作。
```

需要已连接并登录的浏览器；本仓库没有登录凭据、X 私有接口或常驻机器人。技能负责引导 Codex 执行，Python 脚本负责离线测量。跨会话自动检查需要用户环境提供并实际配置调度器；未配置时不会假称后台持续运营。

## 测量与验证

Python 3.10+，运行工具无第三方依赖：

```sh
python3 scripts/measure.py examples/before.json examples/after.json
python3 -m unittest discover -s tests -v
python3 scripts/audit_source.py --source /path/to/x-algorithm --output references/upstream.json
python3 scripts/render_public.py
python3 scripts/diagnose_growth.py
python3 scripts/plan_update.py plan --language zh --change '本轮实际改进'
python3 scripts/contribute.py --sync  # 只读检查；技能授权迭代时用 --apply --sync
```

[技能入口](SKILL.md) · [算法分析](references/algorithm.md) · [测量格式](references/measurement.md) · [来源清单](references/upstream.json)

示例和测试全部虚构，真实账号实验记录默认不公开。质量评分是本技能定义的运营指标，非 X 官方标签。本技能没有已验证的增长率或对照实验结果。

## Fork · 迭代 · 回馈上游

有可访问的 GitHub MCP 或已登录 `gh` 时，技能自动检查并创建本仓库的个人 fork，在 fork 中迭代、同步上游。有新改进时按固定复查周期提交或更新 PR，复用已有 fork/分支/PR。不会为了完成定时任务创建空 PR；上游作者直接维护源仓库。

可运行的 fork／同步辅助：`python3 scripts/contribute.py --apply --sync`。上游作者跳过自建 fork，其他账号创建或复用已验证的个人 fork；原 remotes 和未提交工作保留。PR 仍由真实改进驱动。

具体流程：[共同迭代](references/contributing.md)。周期默认每周一次复查，有可用调度器时实际配置；没有时记录待复查，不伪称已在后台运行。

## 涨粉变慢时怎么判断

先检查已确认动作是否减少，再看曝光、实质互动、粉丝与质量。按真实采集时间计算每段净变化，不把缺时间的首次检查算成速度，不把总粉丝净增算成蓝 V 新增。固定窗口不一致时，只展示事实，不宣称策略胜出或 X 限流。

[增长诊断](references/growth-diagnostics.md) · [置顶帖去重更新](references/pinned-updates.md)

## 持续更新

算法上游每周一 03:43 UTC 复查，版本未变不创建空 PR；新版本生成待审报告，尝试向当前仓库提交草稿 PR，经过语义复核再更新已审结论。[周审机制与边界](references/upstream-review.md)。它不代表跨 fork 的自动贡献或 X 后台运营。

在源码仓库中迭代。公开聚合数据与引用经复核后提交，私有粉丝名单始终在忽略的 `runs/`。更新真实 X 数值后运行 `scripts/render_public.py`，两个语言版本的表格与 SVG 一起刷新。算法有新提交时重读执行路径，更新来源清单和策略，而不是仅替换提交号。

源码和原创文档采用 MIT 许可证；上游算法是 Apache-2.0，本仓库引用其位置与参数，没有打包上游代码。非 X / xAI 官方或关联产品。
