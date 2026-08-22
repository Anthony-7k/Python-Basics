# Day16 检索质量对比报告

运行时间：2026-08-22T01:03:20.851196+00:00

评测后端：`configured-live-embedding`。

固定数据集：25 个问题，其中 5 个可回答问题、20 个信息不足问题。
参数：Top-K=1，向量距离上限=1.1，Redis 检索缓存未参与。

## 汇总

| 模式 | Recall@K | 信息不足准确率 | 平均检索耗时 | P95 检索耗时 | 平均重排候选数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| vector | 60.00% | 40.00% | 189.44 ms | 287.43 ms | 0.00 |
| hybrid | 80.00% | 20.00% | 169.90 ms | 248.77 ms | 0.00 |
| rerank | 80.00% | 20.00% | 174.65 ms | 289.31 ms | 2.76 |

## 固定失败/风险分类

| ID | 分类 | 问题 | Vector | Hybrid | Rerank |
| --- | --- | --- | --- | --- | --- |
| filter-free-gym | 过滤 | 公司给员工提供免费健身房吗？ | 失败 | 失败 | 失败 |
| filter-housing-subsidy | 过滤 | 员工可以领取住房补贴吗？ | 命中 | 失败 | 失败 |
| filter-free-lunch | 过滤 | 公司每天提供免费午餐吗？ | 命中 | 失败 | 失败 |
| filter-stock-options | 过滤 | 员工股票期权如何行权？ | 命中 | 命中 | 命中 |
| filter-remote-work | 过滤 | 员工每周可以居家办公几天？ | 失败 | 失败 | 失败 |
| filter-annual-bonus | 过滤 | 年终奖按照几个月工资计算？ | 失败 | 失败 | 失败 |
| filter-promotion | 过滤 | 员工晋升每年评审几次？ | 失败 | 失败 | 失败 |
| filter-shuttle-bus | 过滤 | 公司班车早上几点发车？ | 命中 | 命中 | 命中 |
| filter-birthday-leave | 过滤 | 员工生日当天可以休假吗？ | 失败 | 失败 | 失败 |
| filter-marriage-leave | 过滤 | 结婚可以申请多少天婚假？ | 命中 | 失败 | 失败 |
| filter-maternity-leave | 过滤 | 产假可以休多少天？ | 失败 | 失败 | 失败 |
| filter-medical-insurance | 过滤 | 公司商业医疗保险报销比例是多少？ | 命中 | 失败 | 失败 |
| filter-parking | 过滤 | 员工停车位每月收费多少？ | 失败 | 失败 | 失败 |
| filter-cafeteria-hours | 过滤 | 公司食堂晚餐供应到几点？ | 命中 | 命中 | 命中 |
| filter-equity-vesting | 过滤 | 限制性股票分几年归属？ | 命中 | 命中 | 命中 |
| ranking-login-alert | 排序 | 发现公司账号异常登录应该找谁处理？ | 失败 | 失败 | 命中 |
| ranking-attendance-three | 排序 | 一个月迟到早退累计达到三次会如何处理？ | 失败 | 命中 | 命中 |
| ranking-probation-resign | 排序 | 试用期员工辞职需要提前三十天吗？ | 命中 | 命中 | 失败 |
| ranking-leave-twenty | 排序 | 工作刚满20年应当按10天还是15天年假执行？ | 命中 | 命中 | 命中 |
| expression-overtime | 表达 | 我没走流程但主动留下干活算加班吗？ | 命中 | 命中 | 命中 |
| filter-phone-subsidy | 过滤 | 公司每月发多少通讯补贴？ | 失败 | 失败 | 失败 |
| filter-meal-overtime | 过滤 | 加班到几点可以领取餐补？ | 失败 | 失败 | 失败 |
| filter-seniority-award | 过滤 | 入职满五年有多少工龄奖金？ | 失败 | 失败 | 失败 |
| filter-quarterly-bonus | 过滤 | 季度绩效奖金什么时候发放？ | 失败 | 失败 | 失败 |
| filter-transport-subsidy | 过滤 | 员工上下班交通补贴标准是多少？ | 失败 | 失败 | 失败 |

## 结论

- Hybrid 相比 Vector 新增命中：ranking-attendance-three。
- Hybrid 相比 Vector 退化：filter-housing-subsidy, filter-free-lunch, filter-marriage-leave, filter-medical-insurance。
- 当前关键词分支直接读取指定 knowledge_base_id 的 Chroma Chunk，避免维护第二套索引；代价是知识库变大后全量 BM25 扫描会增加延迟与内存开销。
- rerank 使用本地 lexical-v1，并非外部 cross-encoder；它没有模型费用，但只能强化词面匹配。只有固定集数据支持时，才应把默认模式从 vector 改为 hybrid 或 rerank。
- 本次三种模式按顺序调用同一远程 Embedding 服务；13 问样本较小，预热和网络抖动会影响平均/P95，因此不能据此断言 Hybrid 比 Vector 更快。
- Rerank 未比 Hybrid 增加命中，当前不值得设为默认模式。
