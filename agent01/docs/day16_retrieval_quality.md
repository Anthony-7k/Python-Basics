# Day16 检索质量对比报告

运行时间：2026-08-22T01:04:27.839201+00:00

评测后端：`configured-live-embedding`。

固定数据集：13 个问题，其中 12 个可回答问题、1 个信息不足问题。
参数：Top-K=3，向量距离上限=1.1，Redis 检索缓存未参与。

## 汇总

| 模式 | Recall@K | 信息不足准确率 | 平均检索耗时 | P95 检索耗时 | 平均重排候选数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| vector | 91.67% | 100.00% | 179.96 ms | 525.17 ms | 0.00 |
| hybrid | 100.00% | 100.00% | 139.16 ms | 213.15 ms | 0.00 |
| rerank | 100.00% | 100.00% | 202.91 ms | 512.93 ms | 3.46 |

## 固定失败/风险分类

| ID | 分类 | 问题 | Vector | Hybrid | Rerank |
| --- | --- | --- | --- | --- | --- |
| work-hours-synonym | 表达 | 员工每天几点打卡上班？ | 命中 | 命中 | 命中 |
| attendance-third-event | 排序 | 一个月第三次迟到会怎样？ | 失败 | 命中 | 命中 |
| probation-synonym | 表达 | 新人转正观察期通常多久？ | 命中 | 命中 | 命中 |
| annual-leave-mid-band | 排序 | 工龄十五年的员工每年休假额度是多少？ | 命中 | 命中 | 命中 |
| annual-leave-high-band | 排序 | 二十年工龄对应多少天年假？ | 命中 | 命中 | 命中 |
| sick-leave-proof | 切分 | 病假第二天开始需要交什么材料？ | 命中 | 命中 | 命中 |
| unapproved-overtime | 表达 | 没审批自己留下来加班算有效加班吗？ | 命中 | 命中 | 命中 |
| salary-day | 排序 | 上个月工资通常几号到账？ | 命中 | 命中 | 命中 |
| expense-extra-approval | 排序 | 一张1200元的费用单需要谁额外审批？ | 命中 | 命中 | 命中 |
| external-training | 切分 | 公司出钱的外部课程要经过哪些人批准？ | 命中 | 命中 | 命中 |
| lost-laptop | 表达 | 公司电脑丢了应该联系谁？ | 命中 | 命中 | 命中 |
| probation-resignation | 排序 | 试用期提出离职至少提前多久通知？ | 命中 | 命中 | 命中 |
| out-of-scope-stock-options | 过滤 | 员工股票期权如何行权？ | 命中 | 命中 | 命中 |

## 结论

- Hybrid 相比 Vector 新增命中：attendance-third-event。
- Hybrid 相比 Vector 退化：无。
- 当前关键词分支直接读取指定 knowledge_base_id 的 Chroma Chunk，避免维护第二套索引；代价是知识库变大后全量 BM25 扫描会增加延迟与内存开销。
- rerank 使用本地 lexical-v1，并非外部 cross-encoder；它没有模型费用，但只能强化词面匹配。只有固定集数据支持时，才应把默认模式从 vector 改为 hybrid 或 rerank。
- 本次三种模式按顺序调用同一远程 Embedding 服务；13 问样本较小，预热和网络抖动会影响平均/P95，因此不能据此断言 Hybrid 比 Vector 更快。
- 当前固定集支持保留 Hybrid 作为可选优化；默认仍为 Vector，待更大真实数据集确认后再切换生产默认值。
- Rerank 未比 Hybrid 增加命中，当前不值得设为默认模式。
