# 先冻结预测，再读取结果

这是一轮真实的前瞻基线实验。**目标是帖子发布后 60 分钟，不是从预测时刻再等一小时。** 写作时目标结果仍待观察；结果只能写入独立 evaluation 文件，不能补进已冻结预测。

## 已冻结的案例

原帖：[2108064574675247167](https://x.com/LIghtJUNction_x/status/2108064574675247167)。[冻结文件](../public/forecasts/rise-2108064574675247167-60m.json)只预测该帖累计 `public_views`，不是独立观看人数、verified Home 曝光或粉丝数。

| 项目 | UTC / 数值 |
| --- | --- |
| 实际发布 | 2026-10-08 05:18:55 |
| 初核 | 05:19:44.193，views=null，不能当 0 |
| 第一个数值点 | 05:33:06.364，6 views |
| 第二个数值点 | 14 views；采集从 05:49:55.368 到 05:49:55.484，以完成时刻作保守可得锚点 |
| 实际冻结 | 05:52:29.751596 |
| 目标 | 06:18:55，帖子年龄 3,600 秒 |
| 起点年龄 / 预测跨度 | 1,860.484 秒（31.008 分钟）/ 1,739.516 秒（28.992 分钟）|
| 恒定 / 最近增速预测 | 14 / 27.79035991755193 views |

最近增速基线是 `14 + (14−6)/1009.12 × 1739.516`。只有两个真实同源数值点，没有补造发布时的零值；误差计算保留冻结文件中的完整精度。两个基线都没有训练。旧 PyTorch 参数是逐旧帖拟合，不能直接迁移；Torch 和 verified Home 预测在本例均为 null。

公开证明：[提交 e792e377](https://github.com/LIghtJUNction/x-quality-growth/commit/e792e3771668e3f4945a0b90f257eb84a5a44bfa)对应的 [CI 37734667646](https://github.com/LIghtJUNction/x-quality-growth/actions/runs/37734667646)于 05:53:29Z 创建，05:53:39Z 更新为完成且成功，均早于目标。冻结文件 SHA256：

```text
cce55596ad1674e503e5f92f38a163c55b2ef5d6e47a8695669e64a9fe5579ab
```

## 采集与评价

预先固定的迟到预算为 **0–300 秒**：06:18:55Z 至 06:23:55Z。这是工作预算，不是 X 算法参数。选择目标后首个成功的同源数值读取，保留失败或缺计数的读取记录。采集开始早于目标、跨越目标或结束超过预算，都不进入主要同窗比较；脚本仍保留数值及诊断误差。迟到读取要注明实际年龄和迟到秒数，仅作窗口近似值，`exact_target_actual` 仍为 null。

下面是**待采集模板，不是真实目标结果**；`observations=[]` 表示尚无结果，不能填猜测数值。保存到私有工作路径，例如 `runs/quality-followup-20261008/actual.json`：

```json
{
  "contract_version": "rise-prospective-actual-1",
  "forecast_id": "rise-2108064574675247167-60m",
  "post_url": "https://x.com/LIghtJUNction_x/status/2108064574675247167",
  "version": "published_version_no_edit_evidence",
  "source": "public_views",
  "metric": "views",
  "first_successful_numeric_read_at_or_after_target": false,
  "observations": []
}
```

真实采集后，每条 observation 必须记录 `actual`（非负整数或 null）、`observation_started_at`、`observation_completed_at` 和 `observed_at`，且 `observed_at` 等于完成时刻。只有确实记录了首个成功读取，才把上述声明改为 true；也可声明 `observation_history_complete_since_target=true` 并提供完整范围。**脚本只能校验提供的记录；首读和完整性仍是操作者声明，不能证明未遗漏读取或时间未被补填。** 不要混入 owner impressions 或编辑版本计数。

```bash
sha256sum public/forecasts/rise-2108064574675247167-60m.json
python scripts/evaluate_forecast.py \
  public/forecasts/rise-2108064574675247167-60m.json \
  runs/quality-followup-20261008/actual.json \
  --forecast-sha256 cce55596ad1674e503e5f92f38a163c55b2ef5d6e47a8695669e64a9fe5579ab \
  --output runs/quality-followup-20261008/evaluation.json
```

[评价器](../scripts/evaluate_forecast.py)核验冻结文件与输入快照的指纹，不训练、不覆盖预测；输出文件已存在也拒绝覆盖。模板只能产生 pending，不代表完成观察。

误差为 `预测−实际`、其绝对值和平方；sMAPE 为 `200×|预测−实际|/(|预测|+|实际|)`，两者均为 0 时定义为 0。缺实际值不算误差。后读计数低于 14 时保留诊断误差并标记疑似修订，主要比较排除，先核对，不把负增量截成 0。单次结果 `n=1` 只能提供描述性误差，不能证明模型稳定优越、校准有效或导致涨粉；操作者打开帖子也可能贡献浏览。
