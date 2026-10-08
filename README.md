# RISE — 递归自我涨粉

<p align="center"><img src="assets/rise-hero.svg" width="100%" alt="RISE · Recursive Iterative Social Expansion · 递归自我涨粉：X 与 GitHub 互相引用，真实反馈推动下一轮内容" /></p>

<p align="center"><a href="references/algorithm.md"><img src="assets/badge-source.svg" alt="基于 X 开源推荐算法" /></a> <a href="public/metrics.json"><img src="assets/badge-evidence.svg" alt="真实观察，效果待验证" /></a> <a href="LICENSE"><img src="assets/badge-license.svg" alt="MIT license" /></a></p>

<p align="center"><b>Recursive Iterative Social Expansion</b><br/>X 自动涨粉与高质量增长技能<br/><a href="README.md">简体中文</a> · <a href="README.en.md">English</a></p>

## 递归自我涨粉，是整个项目的核心

**X 展示真实成果 → GitHub 开源可用技能 → 用户使用、反馈与 PR → 更新实测数据 → X 分享新的有价值结果 → 再次传播。**

每轮传播引用下一层证据：X 帖子链接本仓库；本仓库展示该帖的真实曝光、回复、点赞与收藏。热度是传播反馈，不是单独证明涨粉因果的证据。循环不等于无限刷屏；没有新价值或新数据就不重复推广。

**本技能基于 X 开源推荐算法 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)。** 用「行动 → 观察 → 反馈 → 调整」同时优化新增蓝 V 数量与高质量占比，争取增长和长期交流。支持浏览器行动、离线测量、个人 fork 与共同迭代。不是 X 官方产品，不保证指数增长。

## 真实实验记录

**当前挑战：真实总粉丝破 10 万。** 250 → 1,000 → 10,000 → 100,001 是复盘检查点；高质量蓝 V 仍需独立核验。到达日期未知。[阶段迭代方法](references/road-to-100k.md)。

<img src="assets/metrics.svg" width="100%" alt="真实账号粉丝变化及蓝 V 质量分类，未知值明确保留" />

<!-- RISE:METRICS:START -->
| 真实观察 | 当前结果 |
| --- | --- |
| 总粉丝 | 175 → 254，净变化 **+79** |
| 新观察到的蓝 V | **5** 个；精确新增粉丝未确认 |
| 质量分类 | 2 确认高质 / 3 未匹配主题 / 0 待判定 |
| 高质量占比 | 40.0% |
| 当前观察队列窗口 | 2026-10-07T22:58:02.912Z → 2026-10-08T00:10:06.403Z |
| 最新账号采集 | 2026-10-08T01:15:14.382Z |
| 上一独立观察队列 | 0 高质 / 11 未匹配 / 1 待判定（n=12） |
| 观察队列质量：已确认下界 / 可能上界 | 40.0%–40.0% |
| 首次账号采集 | Timestamp unavailable |
| 较早蓝 V 计数采集（独立窗口） | 2026-10-07T21:04:50.311Z |
| GitHub stars / forks | 1 / 0 · 2026-10-07T21:22:27.159136+00:00 |

上下界描述观察到的蓝 V 队列，并非已确认新增粉丝；无法排除认证升级及改名。公开互动计数可能包含账号自身操作。

[RISE launch post](https://x.com/LIghtJUNction_x/status/2107943767382847844)

[置顶帖下的最新进展](https://x.com/LIghtJUNction_x/status/2108004228832866696)
<!-- RISE:METRICS:END -->

完整原始聚合记录：[public/metrics.json](public/metrics.json)。首次总粉丝检查没有保留精确时间；这轮有其他账号活动，且首轮数据早于技能完成。**总粉丝净变化不等于蓝 V 新增，认证名单新增不一定是新关注。当前 5 人观察队列已完成质量复查；较早 12 人队列仍有 1 人未知，二者独立保留。** 我们公开这些限制，而不是把热度包装成保证效果。

前一轮回测：[技术案例约 60 分钟的复查](public/backtests/2026-10-08-technical-case.md)。最新编辑版本 15 浏览、1 条具体外部回应、0 主页访问；账号 246→251，越过 250 人复盘点。尚不能把净增归因到技术帖；保留 [较早约 67 分钟的首次复查](public/backtests/2026-10-08.md)。新一轮 [三状态表格观察记录](public/backtests/2026-10-08-matrix.md) 已开始，固定窗口待复查。

可直接复现的资料：[AI 代码验收的三种 Git 状态](references/ai-code-review-case.md)，双语说明与真实命令输出。

<img src="assets/git-review-matrix.png" width="100%" alt="Git 三状态实测表：未跟踪文件在两种 diff 中均不可见；未暂存修改由普通 diff 展示；已暂存修改由 diff --cached 展示。先查 status，再读两种 diff 和新文件。" />

## X × GitHub：互相引用的反馈循环

<img src="assets/feedback.svg" width="100%" alt="X 实测帖与技能介绍帖的公开反馈" />

示例来自真实发布内容：

- [回应遮挡标注追问：CVAT 官方资料与复核记录](https://x.com/LIghtJUNction_x/status/2108004713065230723)
- [AI 文案改写：逐句指回事实](https://x.com/LIghtJUNction_x/status/2108000829303378383)
- [三状态 Git 图文：空 diff 不等于验收完成](https://x.com/LIghtJUNction_x/status/2107994469098508741)
- [收到真人反馈后的延续交流](https://x.com/LIghtJUNction_x/status/2107995153403465983)
- [AI 代码验收实测：未跟踪文件不会出现在 git diff](https://x.com/LIghtJUNction_x/status/2107979675960299994)
- [数据标注讨论：固定验证样本](https://x.com/LIghtJUNction_x/status/2107976452662817134)
- [调试讨论：新会话的五项交接信息](https://x.com/LIghtJUNction_x/status/2107977004314431778)
- [首轮 Codex 提示词实验](https://x.com/LIghtJUNction_x/status/2107934424151335154)
- [AI 编程回复：git diff 会漏掉什么](https://x.com/LIghtJUNction_x/status/2107936031907737758)
- [创作者收益讨论：如何衡量粉丝质量](https://x.com/LIghtJUNction_x/status/2107936390185193718)
- [回应 AI 视频创作者：口播一致性的对照测试](https://x.com/LIghtJUNction_x/status/2107947524829127073)

X 介绍帖作为固定入口：有新实测或实际改进时优先更新原置顶帖；无法编辑时在原帖下追加带时间戳的进展回复。

GitHub stars/forks 每 6 小时通过 GitHub Actions 更新；X 热度和粉丝数据仅在实际浏览器复查后更新，不将 GitHub 刷新时间冒充 X 数据采集时间。README 同步生成图表，保留历史观察。没有配置无人值守 X 调度器。

公开互动计数可能包含账号自身点赞或进展回复，不能将自互动当作独立受众认可。

前一轮技术案例已核实 1 条原创和 3 条实质回复（编辑版本不另算原创），并完成 [标注问题的后续交流](https://x.com/LIghtJUNction_x/status/2107983282281627907) 与 [Git 问题回应](https://x.com/LIghtJUNction_x/status/2107987971232375079)。认证名单 137→142 的完整复查得到 5 个新观察蓝 V：2 高质 / 3 未匹配 / 0 未知，观察队列占比 40%，精确新增未确认。截至台北 08:25，五次蓝 V 回关已重新加载确认。技术帖约 60 分钟复查已完成，24 小时观察点为 10 月 9 日 07:26。

随后两条待查蓝 V 事件已按固定主题完成复查：0 高质 / 2 未匹配 / 0 未知。它们是独立复查事件，非完整的新获客队列，不并入上述 5 人的 40%，也不代表本轮新增质量占比为 0%。

**最新迭代：** 台北 10 月 8 日 08:40:20 发布 [三状态原创图文](https://x.com/LIghtJUNction_x/status/2107994469098508741)，另核实 [1 条真人反馈延续回复](https://x.com/LIghtJUNction_x/status/2107995153403465983)、[1 条事实约束文案回复](https://x.com/LIghtJUNction_x/status/2108000829303378383)、其最新版父帖上的 1 次点赞和 1 次蓝 V 回关。08:56 早期观察：253 粉丝，比发帖前 252 净增 1、比前轮 251 净增 2；图文 4 浏览，距发布仅 16.10 分钟，**不是 60 分钟结果**。并行运营存在，不能归因于这一帖。

台北 09:15 再读主页为 **254 粉丝**，比前轮 251 净增 3、比发帖前 252 净增 2；图文为 6 浏览，仍未到 60 分钟。这个较晚计数不覆盖旧名单窗口，也不补齐其缺失身份。

全体粉丝名单采集到 251 条，比主页 253 少 2 条，暂不完整。相对旧 249 条基线，捕获到 2 个此前未列出的身份；当前均为蓝 V，并各读三条近期完整原创，复查为 2 高质 / 0 未匹配 / 0 未知。这只是未完整名单中的观察事件，确切新增与全窗口质量占比未知；不宣称全部新增蓝 V 为 2 或全窗口 100%，不改变原 5 人的 40%。[本轮回测记录](public/backtests/2026-10-08-matrix.md) 保留采集差额与时点；60 分钟观察点为 09:40:20，仍待复查，未设后台检查。表格形式、案例拓展及上一帖编辑均有差异，不是公平 A/B，也不构成增长承诺。

本轮后续收到文案作者的 1 次点赞和简短肯定回复；没有将它当成技术方法反馈或新粉丝。另一次具体标注追问已查阅 CVAT 官方资料后 [公开回复](https://x.com/LIghtJUNction_x/status/2108004713065230723)，与前面的标注交流来自同一作者。新版测量工具明确输出捕获分母和覆盖边界；118 项测试通过。

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
