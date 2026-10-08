# 推荐评分公式与 RISE 实验模型

固定来源：X 官方 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)，提交 `78460ca8b65c57ddd3a05f9217c8aaeba214b628`，核对日期 2026-10-08。以下“官方公式”描述该提交的实际代码；“RISE 模型”是我们提出的测量方法。公开默认、进程启动参数和线上每次请求配置必须分开看。

## 官方：加权的是观看者预测，不是实际事件计数

对观看者 (u) 和候选帖 (i)，先计算：

$$q_{ui}=\sum_h w_h(i)p_{ui,h}+\sum_j v_jc_{ui,j}$$

(p) 是模型预测的行为概率，(c) 是连续输出槽或预测量的乘积；槽名带有时间不代表单位必然是秒，具体配置可能输出超过某个时长的二元概率，见[时间参数与预测头](algorithm-time.md)。缺失值按 0 处理。代码没有在这一步把实际点赞、回复或举报次数代入公式。[scoring.rs L57](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L57)、[L69](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L69)

VM 参数公开默认：

| 预测项 | 默认权重 | 定位 |
| --- | --- | --- |
| favorite / reply / retweet | .5 / 5 / 1 | [params L3](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L3) |
| photo_expand / video_open / click / open_link | .05 / .07 / .3 / .2 | [L6](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L6) |
| profile_click / vqv | 0 / 0 | [L20](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L20) |
| share / share_via_dm / share_via_copy_link | 2 / 5 / 20 | [L27](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L27) |
| dwell / quote / quoted_click / quoted_vqv | .05 / 5 / .05 / 0 | [L40](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L40) |
| follow_author / post_unexplored | 4 / .02 | [L84](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L84) |
| cont_dwell_time / cont_click_dwell_time | .004 / .4 | [L54](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L54) |
| video_continuation / user_video_continuation / profile_visit_secs | 0 / 0 / 0 | [L66](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L66) |
| not_interested / block_author / mute_author / report / not_dwelled | -47.52 / -31.2 / -58.8 / -234 / -.02 | [L102](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L102) |

不是所有候选都使用所有项：vqv 和 quoted_vqv 有资格判断；post_unexplored 在外圈默认不启用。部分连续项是 (p_{\text{打开视频}}\times c_{\text{后续观看秒数}}) 或 (p_{\text{主页点击}}\times c_{\text{主页访问秒数}})，不是独立计数。[scoring.rs L75](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L75)、[L114](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L114)

这些系数不能换算“一赞等于多少举报”。隐藏概率、事件基准频率和个性化预测不同；源码也明确指出计数换算错误。[scoring.rs L32](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L32)

## 官方：负向分数经过分段变换

令 (N=\text{negative\_sum})，(T=\text{positive\_sum}+N)，\(\varepsilon=.001\)。代码定义：

$$\phi(q)=\begin{cases}\max(q,0),&T=0\\ \varepsilon(q+N)/T,&T\ne0\text{ 且 }q<0\\ q+\varepsilon,&T\ne0\text{ 且 }q\ge0\end{cases}$$

`positive_sum` 只累计源码列出的 18 个正向权重；`negative_sum` 是五个负向权重和的相反数。它们不是所有权重绝对值之和，连续预测项系数没有加入 `positive_sum`。按上表未覆盖、未扰动的默认权重，正向和为 43.24、(N=371.54)、(T=414.78)。互关回复加成用于候选的回复项，不自动加进这个归一化和。[weights.rs L49](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/weights.rs#L49)、[L70](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/weights.rs#L70)、[scoring.rs L160](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L160)

这是代码中的分段缩放，不是“举报达到某数量就封顶”的规则。参数覆盖或权重扰动会改变和；`WeightPerturbationSigma` 默认 0，但开启后可以按观看者扰动系数。[weights.rs L100](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/weights.rs#L100)、[params L151](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L151)

## 官方：关系条件与同候选池作者因子

互关加成资格为：

$$I_i=\mathbf1(\text{互关}\land\neg\text{回复}\land\neg\text{转贴})$$
$$w_{\text{reply}}(i)=w_{\text{reply}}+\beta I_i$$

公开默认 (w_{\text{reply}}=5,\beta=15)，符合资格时为 20；驻留互关加成默认 0。代码使用这些字段判断资格，不能扩写成“所有原创形式都得到曝光加成”。[inputs.rs L20](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/inputs.rs#L20)、[weights.rs L82](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/weights.rs#L82)、[params L139](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L139)

作者多样性因子：

$$D_i=(1-f)d^{k_i}+f$$

公开默认启用，(d=.5,f=.25)，所以 (k=0,1,2) 时为 (1,.625,.4375)。(k_i) 是**本次候选池按排序分数降序时**此前同作者候选数量，不是发布时间顺序或当天发帖数。[scoring.rs L182](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L182)、[params L163](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L163)

外圈因子 (O_i) 对 `in_network=Some(false)` 适用；公开默认还对部分内圈回复、转贴适用；未知网络状态不触发此条件。通常默认 .75，话题请求 .5；观看者新用户分支有额外条件，年龄阈值公开默认 0 秒。[scoring.rs L205](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L205)、[context L117](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/value_model.rs#L117)、[params L181](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L181)

评分顺序也有开关。设 (W_i) 为已缓存分数，或无缓存时的 \(\phi(q_i)\)；(b_i) 为探索加成，(A) 为冷启动等调整函数。默认 `MultiplierPreOffset=false` 路径是：

$$B_i=\phi(\phi^{-1}(W_i)+b_i),\quad Y=A(B),\quad s_i=D_i(Y)O_iY_i$$

其中 \(\phi^{-1}\) 是便于阅读的记号，指源码 `unoffset_score`，不声称在所有配置下都是数学逆函数（例如 `T=0` 分支不能恢复被截断的负值）；(b_i=0) 时直接保留 (W_i)。另一条前乘路径先得到 (n_i=\phi^{-1}(W_i)+b_i)，若 (n_i\ge0) 才乘 (D_i(W)O_i)，负净值保持不变，然后做 \(\phi\) 与 (A)。因此不能在所有路径都使用同一个简化乘法公式。[scoring.rs L171](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L171)、[L262](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L262)、[L290](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L290)、[L329](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L329)

## 官方：DPP 选择与双门条件

DPP 先取有评分候选中排名前 `max_selected_rank` 的池。转贴使用原帖的向量 ID；缺失向量会使用随机单位向量，不能据文字直接还原内容相似度。[dpp_model.rs L43](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/dpp_model.rs#L43)、[L60](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/dpp_model.rs#L60)

对入池候选，令 (s_{\max}=\max_i s_i)、(\epsilon=10^{-6})，并把 \(\theta\) 截到 \([0,1-\epsilon]\)：

$$\alpha=\frac{\theta}{2(1-\theta)},\qquad a_i=\exp\left(\alpha\frac{s_i}{\max(s_{\max},\epsilon)}\right)$$
$$L_{ii}=a_i^2,\qquad L_{ij}=a_ia_j\cos(e_i,e_j)$$

向量范数乘积不超过 \(\epsilon\) 时，代码把该非对角相似度设为 0；可选 seed 候选采用归一化质量 1 并可先固定入选。[dpp.rs L92](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/dpp.rs#L92)、[L119](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/dpp.rs#L119)

代码按最大的剩余条件体积增量逐步选取，采用 Cholesky 更新；增量不超过 \(\epsilon\) 时提前停止，或达到数量上限。这是贪心选择，不是证明得到全局最优。入选帖子保留原分数，未入选候选输出 0；不能把指数函数解释成曝光量指数增长。[dpp.rs L223](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/dpp.rs#L223)、[L269](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/dpp.rs#L269)、[输出 L196](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/dpp_model.rs#L196)

公开 feature-switch 默认 `DppEnabled=true`、\(\theta=.65\)、`max_selected_rank=150`；但进程 CLI 默认 `dpp_enabled=false`、\(\theta=.5\)、`max_selected_rank=100`、`top_k=50`。启动开启才建立 DPP 上下文，且请求的功能开关允许时才执行；参数解析存在时又可覆盖部分启动值。线上启动、配置、向量和实际候选池未知。[params L229](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L229)、[args L15](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/args.rs#L15)、[main L29](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/main.rs#L29)、[入口 L35](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/mod.rs#L35)

## RISE：用真实观测验证增长假设

**这一节不是 X 官方推荐公式。** 账号分析通常给出实际事件计数，例如展示、主页访问、详情展开、链接点击和关注变化，不提供每位观看者的隐藏预测 (p_{ui,h})。不能把事件比率代入上述公式冒充官方离线评分。

完整、同期、稳定 ID 的粉丝名单支持：

$$\Delta F=N_{\text{新关注}}-N_{\text{离开}}$$
$$\Delta B=N_{\text{新增蓝V}}-N_{\text{离开蓝V}}+N_{\text{升级蓝V}}-N_{\text{失去蓝V}}$$

设确证新增蓝 V 为 (N)，已判高质量为 (H)，质量未知为 (U)，则完整分类前的质量比例范围为：

$$Q\in[H/N,(H+U)/N]$$

(N=0) 时比例不定义；部分名单或只有 handle 时，只报告“新增观察”，不冒充确证新增。该区间是分类上下界，不是统计置信区间。

可以提出一个待验证的条件概率路径：对固定一组去重、尚未关注的观看者，有

$$E[H_{\text{新增}}]=\sum_u P(E_u)P(B_u\mid E_u)P(F_u\mid E_u,B_u)P(H_u\mid E_u,B_u,F_u)$$

其中 (E) 是在规定窗口被曝光，(B) 是蓝 V，(F) 是随后新增关注，(H) 是符合公开质量标准。这只是条件概率展开；还需一致的归因窗口与观看者连接数据，才可用于估计，不证明曝光造成关注。

公开或 owner analytics 展示量可能重复，主页访问、详情展开、链接点击未必去重、也不是同一批人的逐级嵌套漏斗。**不能直接把“主页访问/展示 × 点击/主页访问 × 新增粉丝/点击”当转粉概率。** 多帖之间也可能有重叠观看者和并行账号活动。

实际可记录 `每千次新增展示对应的同期新增蓝 V`，但必须标成观察比率，而非个体转粉率、官方评分或因果效果。分母缺失或为 0 时留空，不写 0%。对比实验保持质量定义和观察窗口一致，每轮改变一个主要内容因素；同时报告新增蓝 V、质量比例范围、操作成本及归因限制。
