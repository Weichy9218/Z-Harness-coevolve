# Daily Compressed Plan

原 weekly 路线压缩成 daily checkpoint。每一天都要有可运行 artifact，不允许只写故事。

## Day 1：MiniLang no-training scaffold headroom

Done when：

- MiniLang generator / verifier 可重复生成 episode。
- API runner 能跑 `no_scaffold,k_spec,k_gen,k_spec_k_gen`。
- 每个 run 保存 JSONL records 和 summary。
- 至少完成 8 episode API smoke，得到 scaffold headroom 表。

核心命令：

```bash
python -m pytest
python scripts/check_llm.py --client gpt_sub2api --model gpt-5.4
python -m zharness.eval.run_headroom --episodes 8 --client gpt_sub2api --model gpt-5.4
```

## Day 2：Counterfactual leakage eval

Done when：

- 加 `renamed_vocab`、`order_swap`、`hidden_rule_permutation` eval。
- 比较 raw source rulebook vs target scaffold。
- 生成 parse/generate 分拆表。

必须回答：

- raw K_spec 在 renamed/order swap 后是否崩。
- parse 和 generate 是否暴露不同 leakage。

## Day 3：Raw / stripped trace dataset

Done when：

- 每个 successful episode 输出 raw trace 和 stripped trace。
- stripped trace 不含 token mapping、当前 word order、答案。
- 自动检查 banned token / concept leakage。

先不训练，只检查数据质量。

## Day 4：API-only prompt distillation proxy

Done when：

- 用 raw trace / stripped trace 作为 in-context memory 做 no-weight proxy。
- 在 held-out/counterfactual 上比较 raw vs stripped。
- 若 proxy 无差异，先修 abstraction，不上 LoRA。

## Day 5：Offline adoption signal

Done when：

- 构造 skill library：good K_gen、K_spec leak、description trap、redundant。
- 限制 top-k skill invocation。
- 跑 removal ablation。
- 算 adoption score 和 removal delta 相关性。

## Day 6：MiniAPI v0

Done when：

- 500 行以内 simulator。
- 支持 hidden API constraints 和 deterministic verifier。
- 复用 scaffold headroom runner。

## Day 7：Paper-facing first result pack

Done when：

- 一张 scaffold headroom 表。
- 一张 leakage transform 表。
- 一张 adoption-vs-removal 图或表。
- 一页 kill-condition 结论：继续 / 改环境 / 改 abstraction。

