# RISE — 递归自我涨粉

<p align="center"><img src="assets/rise-hero.svg" width="100%" alt="RISE · Recursive Iterative Social Expansion · 递归自我涨粉：X 与 GitHub 互相引用，真实反馈推动下一轮内容" /></p>

<p align="center"><a href="references/algorithm.md"><img src="assets/badge-source.svg" alt="基于 X 开源推荐算法" /></a> <a href="public/metrics.json"><img src="assets/badge-evidence.svg" alt="真实观察，效果待验证" /></a> <a href="LICENSE"><img src="assets/badge-license.svg" alt="MIT license" /></a></p>

<p align="center"><b>Recursive Iterative Social Expansion</b><br/>X 自动涨粉与高质量增长技能<br/><a href="README.md">简体中文</a> · <a href="README.en.md">English</a></p>

## 递归自我涨粉，是整个项目的核心

**X 展示真实成果 → GitHub 开源可用技能 → 用户使用、反馈与 PR → 更新实测数据 → X 分享新的有价值结果 → 再次传播。**

每轮传播引用下一层证据：X 帖子链接本仓库；本仓库展示该帖的真实曝光、回复、点赞与收藏。热度是传播反馈，不是单独证明涨粉因果的证据。循环不等于无限刷屏；没有新价值或新数据就不重复推广。

**本技能基于 X 开源推荐算法 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)。** 用「行动 → 观察 → 反馈 → 调整」同时优化新增蓝 V 数量与高质量占比，争取增长和长期交流。支持浏览器行动、离线测量、个人 fork 与共同迭代。不是 X 官方产品，不保证指数增长。

## 从开源算法得到的五条行动结论

<img src="assets/algorithm-route.svg" width="100%" alt="X 内容推荐路径：相关受众召回、过滤、预测评分、多样性与真实反馈" />

1. [先找相关受众](references/algorithm-field-guide.md#1-先找到相关受众再看互动数字)：单向关注首先改变自己的召回，不等于自己的曝光增加。
2. [保持专业主线](references/algorithm-field-guide.md#2-内容主线要和目标观看者匹配)：围绕 AI 开发、独立产品与真实案例交流；标签没有已知固定加权。
3. [置顶更新与原创分开](references/algorithm-field-guide.md#3-持续更新置顶同时区分更新与新内容)：同会话在 Home 可能被合并或过滤，新发现才写独立原创。
4. [每篇增加实际信息](references/algorithm-field-guide.md#4-保持主题一致让每篇确实增加信息)：作者多样性按候选池处理；DPP 还有启动和请求两道门，线上是否开启未知。
5. [优化真实新增与质量](references/algorithm-field-guide.md#5-优化真实目标不制造算法得分)：权重乘预测量，自己的操作数不能换算成推荐得分。

[30 个文件的来源绑定](references/upstream.json) 固定到官方提交 `78460ca8b65c57ddd3a05f9217c8aaeba214b628`；这不是完整源码审计或线上配置证明。[具体执行条件](references/algorithm.md)。以上策略仍需账号实验验证。

## 真实实验记录

**当前挑战：真实总粉丝破 10 万。** 250 → 1,000 → 10,000 → 100,001 是复盘检查点；高质量蓝 V 仍需独立核验。到达日期未知。[阶段迭代方法](references/road-to-100k.md)。

**新增运营目标：提高原创内容的认证首页展示，达到 90 天 50 万门槛。** 同时保留新增蓝 V 数量与高质量占比目标。评论展示排除；资格展示与收益合格展示分开。[当前 X 官方规则](https://help.x.com/en/using-x/original-content-rewards)。

<img src="assets/reward-reach.svg" width="100%" alt="2026年10月8日04:02至05:28UTC两次真实后台观察：90天认证首页展示534不变，认证粉丝167到171。滚动净变化不代表新入曝光或因果增长；预测与合格收益计数未知。" />

后台最新实际采集 **2026-10-08 05:28:49.830 UTC**：近 90 天、排除回复的认证首页展示仍为 **534 / 500,000（0.1068%）**，还差 **499,466**；认证粉丝 **171 / 500（34.2%）**，还差 **329**。认证粉丝是平台后台口径，不是已核验的蓝 V 或高质量人数。[真实门槛计数](public/reward-observations.json)。

前次 **04:02:12.455 UTC** 为 534 展示、167 认证粉丝；**86.62 分钟**后的滚动展示净变化为 **0**，认证粉丝净变化 **+4**。滚动净变化 0 不证明这期间新入展示为 0；这两次读数也不能证明运营动作带来的增长或收益资格。预测与合格收益计数仍未知。

模型新增目标为单帖未来 1 小时／24 小时的认证首页展示增量；目前缺该口径的逐帖标签，预测仍为未知，不用总 views 乘认证比例代替。账户 90 天进度还需扣除到期展示。官方将自动创作或发布的内容列为收益不合格；Codex 代发实验不作为合格收益证明，真人原创、人工发布与研究统计分别记录。[目标、内容策略与预测边界](references/reward-reach.md)。

<img src="assets/metrics.svg" width="100%" alt="真实账号粉丝变化及蓝 V 质量分类，未知值明确保留" />

<!-- RISE:METRICS:START -->
| 真实观察 | 当前结果 |
| --- | --- |
| 总粉丝 | 175 → 277，净变化 **+102** |
| 新观察到的蓝 V | **24** 个；精确新增粉丝未确认 |
| 质量分类 | 1 确认高质 / 2 未匹配主题 / 21 待判定 |
| 高质量占比 | 分类尚未完成，不能把未知当 0% |
| 当前观察队列窗口 | 2026-10-08T00:23:58.426Z → 2026-10-08T05:14:58.325Z |
| 最新账号采集 | 2026-10-08T05:33:06.588Z |
| 粉丝名单采集覆盖 | 已采集 273/276；名单不完整 |
| 全窗口高质量占比 | 未知；粉丝名单不完整 |
| 上一独立观察队列 | 2 高质 / 3 未匹配 / 0 待判定（n=5） |
| 观察队列质量：已确认下界 / 可能上界 | 4.2%–91.7% |
| 首次账号采集 | Timestamp unavailable |
| 较早蓝 V 计数采集（独立窗口） | 2026-10-07T21:04:50.311Z |
| GitHub stars / forks | 1 / 0 · 2026-10-07T21:22:27.159136+00:00 |

上下界描述观察到的蓝 V 队列，并非已确认新增粉丝；无法排除认证升级及改名。公开互动计数可能包含账号自身操作。

[RISE launch post](https://x.com/LIghtJUNction_x/status/2107943767382847844)

[置顶帖下的最新进展](https://x.com/LIghtJUNction_x/status/2108069404860887280)
<!-- RISE:METRICS:END -->

完整原始聚合记录：[public/metrics.json](public/metrics.json)。首次总粉丝检查没有保留精确时间；这轮有其他账号活动，且首轮数据早于技能完成。**总粉丝净变化不等于蓝 V 新增，认证名单新增不一定是新关注。当前部分名单观察队列为 24 人：1 高质、2 未匹配、21 未知。历史 5 人队列已完成质量复查；较早 12 人队列仍有 1 人未知，三个队列独立保留。** 我们公开这些限制，而不是把热度包装成保证效果。

较早实测：[算法聚焦轮](public/backtests/2026-10-08-algorithm.md) 记录 **270 粉丝**（02:49:34 UTC），较旧 256 净增 14；同期有其他视频和关注操作，无法逐帖归因。定向 Git 建议 10 浏览@73.89 分钟，Harness 建议 9 浏览@59.93 分钟，来源请求 20 浏览@63.66 分钟；后一帖的 1 条回复只是同一作者提供下载入口。两条技术建议均未观察到技术回应或主页访问，尚未证明新增高质获客。

可直接复现的资料：[AI 代码验收的三种 Git 状态](references/ai-code-review-case.md)，双语说明与真实命令输出。

<img src="assets/git-review-matrix.png" width="100%" alt="Git 三状态实测表：未跟踪文件在两种 diff 中均不可见；未暂存修改由普通 diff 展示；已暂存修改由 diff --cached 展示。先查 status，再读两种 diff 和新文件。" />

## X × GitHub：互相引用的反馈循环

<img src="assets/feedback.svg" width="100%" alt="X 实测帖与技能介绍帖的公开反馈" />

示例来自真实发布内容：

- [真实失败回测：小模型暂未胜过同窗简单基线](https://x.com/LIghtJUNction_x/status/2108064574675247167)
- [回应开发者反馈：复现入口、排除证据与修改理由](https://x.com/LIghtJUNction_x/status/2108060803639500970)
- [回应短片实验：重复任务并保留失败、耗时和费用](https://x.com/LIghtJUNction_x/status/2108067265497485702)
- [算法独立原创：关注方向与置顶会话过滤](https://x.com/LIghtJUNction_x/status/2108028923200339985)
- [交付给原作者的关键帧与样片](https://x.com/LIghtJUNction_x/status/2108025662980358354)
- [相关 Harness 训练讨论：本地与远程对照建议](https://x.com/LIghtJUNction_x/status/2108011337209270512)
- [针对真实多模型审查命令：diff 范围遗漏的复现建议](https://x.com/LIghtJUNction_x/status/2108007419154735157)
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

已完成的旧窗口：[矩阵 12 浏览@60.11 分钟](public/backtests/2026-10-08-matrix.md)、[技术案例 15 浏览@60.38 分钟及 1 位具体回应作者](public/backtests/2026-10-08-technical-case.md)、[方法帖 34 浏览@67.15 分钟](public/backtests/2026-10-08.md)。帖子年龄、版本和同时发生的操作不同，不能当作公平对照；旧时间和名单分母均保留在各轮记录。

本轮已有 [8 张粗框关键帧](https://x.com/LIghtJUNction_x/status/2108022019157873061) 与 [12 秒样片视频](https://x.com/LIghtJUNction_x/status/2108025662980358354) 实际交付给提出问题的作者；商品去向留未知，视频连续观看审核仍待完成。[Luna API 回复](https://x.com/LIghtJUNction_x/status/2108016718492909780) 是未实测建议。这是一位作者的持续交流，不能按消息数算新增作者或粉丝。

[算法独立原创](https://x.com/LIghtJUNction_x/status/2108028923200339985) 已于 **02:57:15 UTC** 发布，图片、ALT 和源码链接均重开核对；首核 2 浏览、互动均 0，属于早期读数。60 分钟实际复查 **03:57:42.584 UTC**（晚 27.584 秒）：33 浏览、0 外部回复、1 次可见自赞；独立点赞为 0。24 小时点为次日 **02:57:15 UTC**，仍待观察，不能当成公平 A/B。

五人观察队列的 40% 不变；旧不完整名单中的两个高质事件、指定对象质量复查和本轮两次蓝 V 回关分别保留。两位回关对象尚未完成质量核验，不报确证新增。没有配置后台 X 检查。上一轮覆盖边界迭代通过 118 项测试；历史源码与参数复核通过 **124 项测试**。本轮部分名单披露、真实反馈与独立认证首页目标更新通过 **226 项测试**，技能校验通过。

## 统计与预测：用真实误差检验模型

<img src="assets/statistics.svg" width="100%" alt="带真实时间的粉丝净速度与中点差加速度；缺失值和非等长窗口保留" />

最新主页读数是 **277 粉丝 / 269 关注**（2026-10-08 05:33:06.588 UTC）。从有准确时间的 204 到 277，平均净速度为 **8.60 人/小时**（0.002390 人/秒）；最近 17.05 分钟净变化为 +1。首次 175 没有准确时间，不能加入速度计算。五人观察队列的 **40%** 仍是原队列质量，不是全账号高质占比或确证新增质量率。

速度用 `Δ粉丝 / Δ时间`；加速度用两段速度之差除以**两窗口中点的时间差**，单位分别为人/小时与人/小时²。这些差分描述净变化，不能分离新增与取关，也不证明增长机制。单帖展示、互动、详情、主页访问和点击按来源及采集时间分别统计；公开浏览与 owner impressions 不混算，缺少归因的单帖获粉仍为 null。

<img src="assets/prediction.svg" width="100%" alt="同一预测起点与目标的热度回测：最后值、最近速度与三参数 PyTorch 曲线的真实误差比较" />

**已完成真实计数拟合，当前曲线尚未优于简单基线。** PyTorch 2.14 CPU 单线程训练了两个分别拟合的单帖曲线，每个仅 3 个参数；最终参数存档共用 19 个相关观察点，不是 19 条独立帖子。置顶帖有 7 个可评估的滚动预测起点，预测时只使用截至该起点可得的数据。

最新历史留出窗口为 **03:08:12.506 → 03:23:30.786 UTC**，约 15.30 分钟，实际 **661 浏览**。这是下一点历史回测，不是提前发布的预测；该次预测只用了此前 12 点，最终存档随后再拟合到包含留出点的可用历史。

| 模型 | 最新留出预测 | 绝对误差（浏览） | 同窗回测 MAE（浏览） |
| --- | ---: | ---: | ---: |
| 保持最后值 | 659 | 2 | **9.40** |
| 延续最近速度 | 668.85395 | 7.85395 | 12.30 |
| PyTorch 三参数曲线 | 673.22592 | 12.22592 | 28.30 |

MAE 是平均绝对误差，越低越好。最后一列只比较**同一置顶帖、相同 5 个起点与目标、15–60 分钟跨度**；这些样本相关，不能宣称跨帖泛化或统计胜出。24 小时外推尚无真实结果，误差区间未知；曝光预测也不能换算成蓝 V 新增或十万粉到达日期。

当前实现只用发布时间、观察时间与计数，统计实测仅覆盖 X。统一的正文、图片、视频、评论输入契约已设计，正文与媒体语义尚未进入训练，其他平台适配尚未验证。官方热门池参考分也不是未来曝光预测。[统计方法](references/growth-statistics.md) · [输入契约](references/model-inputs.md) · [官方时间参数](references/algorithm-time.md) · [推荐公式与边界](references/recommendation-formulas.md)

**新增第二目标：文案来源。** 设计为单独输出人写、AI 生成、混写的概率，证据不足保留未知；也可用截止前的折外预测概率辅助热度。[输入与概率校验器](scripts/authorship.py) 已实现，来源分类器尚未训练，也没有改善热度的实测。它不代表质量，也不是正文中 AI 字符的比例；[来源、标签和验证规则](references/model-inputs.md)。数据优先从 [现有资源复用](references/data-reuse.md)，不靠不断发新帖凑样本。

复现三份聚合结果；前两项只需 Python 标准库，曲线训练另需 PyTorch：

```sh
python3 scripts/growth_dynamics.py --output public/growth-dynamics.json
python3 scripts/post_statistics.py --output public/post-statistics.json
python3 scripts/predict_heat.py --model torch --output public/heat-prediction.json --model-outputpath runs/heat-model-state.json
python3 scripts/reward_progress.py --outputpath public/reward-progress.json
```

[粉丝差分结果](public/growth-dynamics.json) · [单帖统计](public/post-statistics.json) · [预测回测](public/heat-prediction.json)。模型、复现代码及真实回测已发布到 [Hugging Face / RISE-heat-baseline](https://huggingface.co/LIghtJUNction/RISE-heat-baseline)，版本 `ab23b84`；公开下载的参数和模型说明与本地 SHA-256 一致。

本次统计、预测与门槛测量迭代通过 **224 项测试**，技能格式检查通过。

下一轮固定 60 分钟、24 小时和 72 小时窗口，每轮只改变一个主要因素，并记录并行操作。按帖子或日期积累可比实验；页面刷新和同一作者多次回复不扩充独立样本。高质新增、队列留存、操作投入与模型误差分别评价，效果不足就继续保留简单基线。

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

基础测量使用 Python 3.10+ 标准库；可选曲线训练另需 PyTorch：

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
