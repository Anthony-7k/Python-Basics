# AI Agent Roadmap 开发问题记录

> 项目：agent01  
> 方向：企业知识库 Agent / RAG 最小闭环  
> 用途：记录开发过程中的问题、解决方案、技术总结  
>
> 持续更新中...


---

# Day2 文档解析与元数据标准化

## 今日目标

完成 PDF、DOCX、TXT 三种格式文档解析，并统一返回 DocumentRecord 数据结构。

实现：

- PDF Loader
- DOCX Loader
- TXT Loader

同时为每个文档保存基础元数据：

- source
- file_name
- document_id
- content_hash


---

# Day2 开发记录


## 1. python-docx 安装后无法导入


### 问题现象

执行：

```bash
python -m pip show python-docx
```

输出：

```text
WARNING: Package(s) not found: python-docx
```

但是执行：

```bash
python -m pip install python-docx
```

安装成功。


### 原因

项目使用虚拟环境：

```text
.venv
```

但是部分命令调用到了系统 Python。

导致：

- Python 环境不一致
- 第三方依赖安装位置不同
- 运行时无法找到对应包


### 解决方式

优先使用项目虚拟环境：

```bash
.\.venv\Scripts\python.exe
```

运行测试：

```bash
.\.venv\Scripts\python.exe -m pytest
```


### 总结

Python 项目开发中需要保持：

安装依赖环境

=

运行代码环境

=

测试环境


否则容易出现：

"明明安装成功，但是 Python 找不到"


---

## 2. Pydantic 模型字段缺失导致 ValidationError


### 问题现象

运行测试时出现：

```text
pydantic_core.ValidationError
```

提示：

```text
Field required
document_id
source
content_hash
```


### 原因

项目中定义了统一的数据模型：

```python
class DocumentRecord(BaseModel):
    document_id: str
    source: str
    content: str
    file_name: str
    content_hash: str
```

但是 Loader 返回的数据没有补充完整字段。


### 解决方式

修改 PDF、DOCX、TXT Loader。

创建 DocumentRecord 时补充：

```python
DocumentRecord(
    document_id=document_id,
    source=file_path,
    content=text,
    file_name=file_name,
    content_hash=content_hash
)
```


### 总结

使用 Pydantic 进行数据校验时：

模型字段发生变化后：

- 所有创建对象的位置都需要同步修改
- 测试可以帮助快速发现数据结构不一致


---

## 3. pytest 测试数量异常


### 问题现象

第一次运行：

```bash
pytest
```

发现：

```text
2 passed
```

但是预期应该有：

```text
3 passed
```


### 排查过程


查看测试收集：

```bash
pytest --collect-only
```


发现：

部分测试文件没有被 pytest 收集。


### 原因

pytest 默认识别规则：

测试文件：

```text
test_xxx.py
```

测试函数：

```python
def test_xxx():
```


如果文件名或者函数名不符合规则：

pytest 会跳过。


### 解决方式

检查：

- 测试文件名称
- 测试函数命名


最终：

```text
3 passed
```


---

# Day2 Git 提交


提交：

```text
feat: add docx loader and tests
```


包含：

- DOCX Loader
- 测试文件
- 文档解析能力


---


# Day3 文本清洗与 Chunk 切分


## 今日目标


完成 RAG 前处理流程：

原始文本

↓

文本清洗

↓

Chunk 切分

↓

生成 ChunkRecord


实现：

- text_cleaner
- chunker
- chunk 实验统计


---

# Day3 开发记录


## 1. ChunkRecord 数据模型设计


文件：

```text
app/schemas/chunk.py
```


作用：

保存文本切片后的结构化信息。


字段说明：


|字段|说明|
|-|-|
|chunk_id|文本块唯一ID|
|document_id|来源文档ID|
|content|切分后的文本内容|
|start_index|文本开始位置|
|end_index|文本结束位置|
|page|所在页码|
|content_hash|文本内容哈希|


---

## 2. Python 无法找到 app 模块


### 问题现象


运行：

```bash
python docs/chunk_experiment.py
```


出现：

```text
ModuleNotFoundError:
No module named 'app'
```


### 原因


Python 执行脚本时：

默认搜索当前脚本所在目录。

但是项目结构：

```text
agent01
|
├── app
|
├── docs
```


docs 和 app 是同级目录。


直接运行：

```text
docs/chunk_experiment.py
```

Python 不一定能够找到 app。


### 解决方式


使用项目虚拟环境运行：

```bash
.\.venv\Scripts\python.exe docs\chunk_experiment.py
```


### 总结


企业项目中：

推荐从项目根目录运行。

保持：

```text
项目根目录
|
├── app
├── tests
├── docs
```


---

## 3. 缺少 __init__.py 文件


### 问题


Python 3.11 部分情况下可以不需要：

```text
__init__.py
```


但是企业项目通常保留。


添加：

```text
app/services/chunkers/__init__.py

app/services/cleaners/__init__.py
```


### 作用


明确告诉 Python：

当前目录是一个 Python Package。


提高：

- 项目结构清晰度
- 模块导入稳定性


---

## 4. text_cleaner 测试失败


### 问题现象


测试：

```python
assert result == "Hello world\ntest"
```


实际输出：

```text
Hello world\n\n test
```


导致：

```text
AssertionError
```


### 原因


原始代码：

```python
re.sub(
    r"\n{3,}",
    "\n\n",
    text
)
```


只能处理三个以上连续换行。


但是测试数据：

```text
Hello world


test
```


实际包含两个换行。


### 解决方式


修改：

```python
text = re.sub(
    r"\n{2,}",
    "\n",
    text
)
```


让两个及以上换行统一处理。


### 总结


文本清洗需要根据真实数据调整规则。

不能只考虑理想输入。


---

# Chunk 参数实验记录


## chunk_size = 200


实验结果：

```text
chunk数量：46

平均长度：198.91

最大长度：200

最小长度：150
```


特点：

优点：

- 切分粒度更细
- 检索更加精准


缺点：

- chunk数量增加
- 上下文信息减少


---

## chunk_size = 500


实验结果：

```text
chunk数量：18

平均长度：477.78

最大长度：500

最小长度：100
```


特点：

优点：

- 保留更多上下文
- chunk数量减少


缺点：

- 可能包含无关信息
- 检索粒度下降


---

## 初步结论


chunk_size 不是越大越好。

需要结合：

- embedding效果
- 检索准确率
- 文档类型


后续 RAG 阶段继续优化。


---

# Day3 测试结果


执行：

```bash
.\.venv\Scripts\python.exe -m pytest
```


结果：

```text
5 passed
```


包含：

- test_chunker
- test_cleaner
- test_docx_loader
- test_pdf_loader
- test_txt_loader


---

# Day3 Git 提交


提交：

```text
feat: add text cleaning and chunking pipeline
```


包含：

- ChunkRecord 模型
- 文本清洗模块
- Chunk 切分模块
- 测试代码
- Chunk 实验记录


---

# 后续开发记录


## Day4
# Day 4 复盘｜Embedding 与 Chroma 入库

## 今日重点

今天完成了 RAG 前半段的核心链路：

文件 → Loader → Cleaner → Chunker → Embedding → Chroma

主要完成：

- 使用 `text-embedding-v4` 生成 1024 维向量
- 实现批量 Embedding
- 使用 Chroma 持久化向量
- 实现 `upsert / query / delete_by_document`
- 使用 `content_hash + embedding_model` 实现幂等入库
- 实现 TXT / PDF / DOCX 统一入库流程
- 新增 `ingest.py` 一键入库命令
- 完成真实语义检索
- 全量测试 `10 passed`

## 今日难点

### 1. Chat 模型和 Embedding 模型的区别

DeepSeek Chat 主要负责：

文本 → 文本

Embedding 模型负责：

文本 → 向量

所以最终使用：

- LLM：DeepSeek Chat
- Embedding：text-embedding-v4
- 向量维度：1024

### 2. 幂等入库

为了避免同一个 Chunk 重复生成向量，入库前检查：

`content_hash + embedding_model`

如果内容和模型都没有变化，就跳过 Embedding。

这样可以避免重复调用 API 和重复计算。

### 3. document_id 与 chunk_id 设计

一份 PDF 应该共享同一个 `document_id`，页码单独记录。

Chunk ID 最终设计为：

```text
TXT / DOCX：
document_id_0

PDF：
document_id_p1_0
document_id_p2_0
```

---

# Day 5｜语义检索与召回评估

## 今日目标

完成 RAG 的检索阶段，让用户问题能够从 Chroma 中召回正确的 Chunk。

整体流程：

```text
User Query
↓
Embedding
↓
Chroma
↓
Top-K
↓
Retriever
↓
Distance Filter
↓
Evidence
```

## 今日完成内容

- 实现 Retriever 检索服务
- 实现 Top-K 检索调试工具
- 创建正式测试文档 `employee_handbook.txt`
- 员工手册切分为 5 个 Chunk 并写入 Chroma
- 创建 20 道检索评测题
- 实现 Recall@K 自动评测
- 对比 Top-K = 3 / 5 / 8
- 实现 `max_distance` 低置信度过滤
- 完成不可回答问题测试
- 新增 Retriever 单元测试
- 全量测试达到 `12 passed`

---

## 1. Retriever 检索服务

新增：

```text
app/services/retrieval/retriever.py
```

主要流程：

```text
用户问题
↓
query_chunks()
↓
Query Embedding
↓
Chroma 相似度检索
↓
Top-K Chunk
↓
整理检索结果
```

Retriever 最终返回：

- `chunk_id`
- `content`
- `distance`
- `metadata`

其中：

```text
distance 越小
通常表示语义越相关
```

---

## 2. Top-K 与 Recall@K

Top-K 表示：

> 每次检索返回最相关的前 K 个 Chunk。

Recall@K 表示：

> 正确证据是否能够进入前 K 个检索结果。

本次实验结果：

| Top-K | 命中 | Recall |
|---|---:|---:|
| 3 | 18/18 | 100% |
| 5 | 18/18 | 100% |
| 8 | 18/18 | 100% |

当前测试集中：

```text
Top-K = 3
```

已经能够召回全部正确证据。

但当前正式知识库只有 5 个 Chunk，后续知识库扩大后需要重新评测 K 值。

---

## 3. 重难点：旧测试向量污染检索结果

测试问题：

```text
工作满12年的员工有多少天年假？
```

正确证据应该是：

```text
工作满10年但不满20年的员工，
每年享有10天带薪年假。
```

第一次测试时，正确证据只排在：

```text
Top 3
```

排查发现 Chroma 中还存在 Day 4 的旧测试向量和 `demo_doc`，导致旧数据参与相似度排序。

通过：

```python
delete_by_document()
```

删除旧测试数据后，正确证据提升到：

```text
Top 1
```

总结：

> 正式检索评测前必须保证向量数据库中的数据干净，否则历史测试数据会影响召回排序。

---

## 4. 同义改写检索

测试问题：

```text
正式员工辞职要提前多久？
```

知识库原文使用的是：

```text
离职
```

原文：

```text
正式员工主动提出离职，
原则上应至少提前30天提交书面离职申请。
```

最终正确证据：

```text
Top 1
distance ≈ 0.5518
```

说明 Embedding 可以进行一定程度的语义匹配，而不是只能匹配完全相同的关键词。

---

## 5. 检索评测集

新增：

```text
eval/datasets/retrieval_questions.jsonl
```

共准备：

```text
20 道问题
```

其中：

```text
18 道可回答题
2 道不可回答题
```

题型包括：

- `answerable`
- `paraphrase`
- `boundary`
- `unanswerable`

新增：

```text
eval/eval_retrieval.py
```

自动评测流程：

```text
读取问题
↓
Retriever
↓
Top-K
↓
检查 expected_keyword
↓
HIT / MISS
↓
计算 Recall@K
```

---

## 6. 重难点：不可回答问题

向量数据库不会主动判断：

```text
知识库里没有答案
```

例如问题：

```text
公司提供免费健身房吗？
```

虽然员工手册中完全没有相关信息，但 Chroma 仍然会从已有 Chunk 中返回几个“相对最像”的结果。

因此：

> 有 Top-K 结果，不代表知识库真的能够回答这个问题。

需要结合 `distance` 做低置信度过滤。

---

## 7. Distance 阈值实验

两个不可回答问题的 Top 1 distance：

```text
免费健身房：1.0420
住房补贴：1.0165
```

18 道可回答问题的 Top 1 distance：

```text
最小：0.5518
最大：0.9749
```

因此当前实验初步设置：

```text
max_distance = 1.0
```

规则：

```text
distance <= 1.0
→ 保留

distance > 1.0
→ 过滤
```

最终不可回答题测试：

```text
2/2 PASS
```

需要注意：

> `1.0` 只是当前文档、Embedding 模型和测试集下得到的基线阈值，不是固定万能阈值。

后续知识库扩大后需要重新评测。

---

## 8. Embedding 不等于逻辑推理

例如：

```text
工作满12年的员工有多少天年假？
```

Embedding 主要负责找到和以下内容语义相关的 Chunk：

```text
员工
工作年限
年假
多少天
```

Embedding 本身并不是先执行：

```text
12 >= 10
12 < 20
所以属于10～20年
```

真正的条件判断和最终回答，后续仍然需要交给 LLM。

因此：

> Retriever 的主要任务是找到证据，而不是完成所有推理。

---

## 9. Retriever 单元测试

新增：

```text
tests/test_retriever.py
```

新增两个测试：

```text
test_retrieve_returns_results
test_retrieve_filters_by_distance
```

测试中使用 `monkeypatch` 替换真实的：

```text
query_chunks()
```

避免单元测试依赖：

- Embedding API
- 网络
- Chroma 实际数据

Retriever 单独测试：

```text
2 passed
```

全量测试：

```text
12 passed
```

---

## 今日重难点总结

### 1. Retriever 与 Vector Store 的区别

Vector Store 负责：

```text
存储向量
查询向量
删除向量
```

Retriever 负责：

```text
接收用户问题
↓
调用 Vector Store
↓
整理 Top-K
↓
处理 distance
↓
返回证据
```

### 2. Top-K 不是越大越好

K 增大会提高候选数量，但同时也可能增加：

- 无关 Chunk
- LLM 上下文长度
- Token 消耗
- 噪声

因此应该通过 Recall 实验选择合适的 K。

### 3. 数据质量会直接影响检索质量

旧测试向量会参与相似度计算，从而影响正式检索结果。

因此 RAG 不只是模型问题，也包含数据治理问题。

### 4. Distance 阈值不能随便设置

应该先统计：

```text
可回答问题 distance 分布
+
不可回答问题 distance 分布
```

再根据实验结果选择阈值。

---

## Day 5 最终结果

```text
正式知识库：
5 Chunks

评测集：
20 Questions

可回答问题：
18

不可回答问题：
2

Recall@3：
18/18 = 100%

Recall@5：
18/18 = 100%

Recall@8：
18/18 = 100%

不可回答题：
2/2 PASS

max_distance：
1.0

pytest：
12 passed
```

Day 4 完成了：

```text
把知识存进去
```

Day 5 完成了：

```text
把正确知识找出来
```

目前项目已经形成：

```text
Document
↓
Loader
↓
Cleaner
↓
Chunker
↓
Embedding
↓
Chroma
```

以及：

```text
User Question
↓
Retriever
↓
Top-K Evidence
↓
Distance Filter
```

下一阶段进入：

```text
User Question
↓
Retriever
↓
Evidence
↓
RAG Service
↓
LLM
↓
Grounded Answer
↓
Citation
```

---


# Day6 RAG问答链路与LLM接入


## 今日目标

完成知识库 Agent 的 RAG 闭环：

- 接入 LLM
- 完成 RAG Service
- 实现 Prompt 拼接
- 实现结构化返回
- 增加拒答机制


---

# Day6 开发记录


## 1. LLM 服务封装

新增：

app/services/llm/llm_client.py

实现：

- OpenAI Client 初始化
- 环境变量读取
- generate_answer 方法

将模型调用从测试代码中独立出来。


---

## 2. RAG Service实现

新增：

app/services/rag/rag_service.py

实现流程：

用户问题
 ↓
Retriever检索
 ↓
构造Context
 ↓
Prompt拼接
 ↓
LLM生成答案


主要函数：

- build_context()
  - 添加来源编号[S1]

- retrieve_context()
  - 完成检索和上下文构造

- answer_question()
  - 完整执行RAG问答流程


---

## 3. Prompt模板

新增：

app/prompts/rag_prompt.py

实现：

- SYSTEM_PROMPT
- build_user_prompt()


约束模型：

- 根据知识库回答
- 禁止编造信息
- 信息不足时拒答
- 输出来源引用


---

## 4. 结构化返回

接入：

app/schemas/rag.py

返回：

RAGResponse

包含：

- answer
- sources
- used_chunk_ids
- request_id


方便后续追踪回答来源。


---

## 5. 拒答机制

问题：

无关问题可能召回低相关内容，导致模型产生幻觉。


解决：

增加：

max_distance

过滤低相关结果。


当没有有效知识时返回：

知识库中没有足够的信息回答这个问题。


---

## 6. 测试验证


测试命令：

```bash
.\.venv\Scripts\python.exe -m pytest
结果：
12 passed
真实问答测试：
问题：
员工每年有多少天年假？
结果：
成功根据知识库生成答案，并返回引用。
拒答测试：
问题：
公司的老板喜欢什么颜色？
结果：
知识库中没有足够的信息回答这个问题。
测试通过。
今日总结
Day6完成RAG最小闭环：
文档
 ↓
Chunk
 ↓
Embedding
 ↓
检索
 ↓
Prompt
 ↓
LLM回答
目前 Agent 已具备：
知识检索
基于知识回答
来源引用
无答案拒答

---

# Day7 RAG工程化完善与评估体系

## 今日目标

完善企业知识库 Agent 的 RAG 闭环。

主要完成：

- CLI问答入口完善
- RAG拒答机制优化
- 请求链路日志记录
- RAG自动化评估脚本
- 完善测试覆盖


---

# Day7 开发记录


## 1. 增加 CLI 命令行调用能力


### 实现内容

新增 CLI 入口：

支持：

- 文档导入 ingest
- 知识库问答 chat


可以直接通过命令行测试 RAG 流程：

```bash
.\.venv\Scripts\python.exe -m app.cli chat "问题"
```


实现效果：

用户输入问题后，可以完成：

用户问题

↓

向量检索

↓

上下文构建

↓

LLM生成回答

↓

返回答案和来源


---

## 2. 完善 RAG 拒答机制


### 问题

之前模型可能在没有相关知识库内容时继续生成答案。

例如：

问题：

```text
公司提供免费健身房吗？
```


如果知识库不存在相关信息，模型可能产生幻觉回答。


### 解决方式

增加检索结果判断：

当没有有效知识库上下文时：

直接返回：

```text
知识库中没有足够的信息回答这个问题。
```


避免：

- 编造答案
- 无来源回答
- 幻觉问题


测试：

```text
公司提供免费健身房吗？
```


结果：

```text
Answer:
知识库中没有足够的信息回答这个问题。

Sources:
No sources
```


---

## 3. 增加 RAG 请求链路日志


### 实现内容

新增统一 logging 配置。


记录内容：

- request_id
- retrieval耗时
- generation耗时
- total耗时
- 检索来源数量
- 请求状态


示例：

```text
rag retrieval completed

request_id=xxx

sources=3

retrieval_ms=xxx


rag request completed

status=answered

generation_ms=xxx

total_ms=xxx
```


同时记录拒答状态：

```text
status=refused
```


方便后续：

- 性能分析
- 问题定位
- 线上排查


---

## 4. 增加 RAG 自动化评估


### 新增文件

```text
eval/
 ├── datasets/
 │    └── retrieval_questions.jsonl
 │
 └── eval_rag.py
```


建立测试数据集：

共30条问题。


覆盖类型：

- answerable（可回答）
- paraphrase（语义改写）
- boundary（边界问题）
- unanswerable（不可回答）


例如：

可回答：

```text
工作满12年的员工有多少天年假？
```


不可回答：

```text
公司是否提供免费健身会员？
```


---

## 5. RAG评估结果


运行：

```bash
.\.venv\Scripts\python.exe eval\eval_rag.py
```


最终结果：

```text
Score: 27/30
```

引用来源测试：

```text
Citation Hit Rate:

26/26 (100%)
```


说明：

- 基础问答能力正常
- 来源引用完整
- 拒答机制有效


---

## 6. 测试结果


运行：

```bash
.\.venv\Scripts\python.exe -m pytest
```


结果：

```text
15 passed
```


已有测试：

- chunk切分测试
- 文档解析测试
- retriever测试
- vector store测试
- CLI测试


全部通过。


---

# 今日总结


Day7完成了企业知识库 Agent 从 Demo 到工程化版本的升级。


新增能力：

- CLI调用
- RAG拒答
- 请求日志追踪
- 自动化评估
- 来源引用验证


当前 RAG 流程：

用户问题

↓

Embedding检索

↓

召回知识片段

↓

构建上下文

↓

LLM回答

↓

来源追踪

↓

日志记录


项目已经具备一个基础企业知识库 Agent 的完整闭环。


---

# Git提交记录


Commit:

```text
feat: complete rag evaluation and logging
```


提交内容：

- CLI入口
- logging模块
- RAG服务优化
- Prompt优化
- RAG评估脚本
- CLI测试


---

---

# Day8 FastAPI 服务化与 API 工程化


## 今日目标

将已有 CLI 版本 RAG Agent 服务化，使用 FastAPI 提供 HTTP API。

完成：

- FastAPI 项目入口
- API 路由拆分
- Chat API
- 请求响应模型
- request_id 全链路追踪
- 统一异常处理
- API 自动化测试


## Day8 开发内容


### 1. FastAPI 服务搭建

新增 FastAPI 应用入口：

- app/main.py

实现：

- FastAPI 初始化
- 路由注册
- Swagger 文档


新增接口：

GET /health

返回服务健康状态。


GET /ready

返回服务就绪状态。


POST /api/v1/chat

提供 RAG 问答接口。


---

### 2. 请求与响应模型

新增：

- ChatRequest
- RAGResponse
- RAGSource


实现：

- 请求参数校验
- 响应结构统一


例如：

question：

- 最小长度 1
- 最大长度 2000


---

### 3. request_id 链路追踪


新增 middleware：

每个 HTTP 请求生成唯一 request_id。


实现：

请求：

HTTP Request
↓
middleware
↓
chat API
↓
rag_service


统一：

- 日志 request_id
- Response request_id
- Header X-Request-ID


方便后续线上问题定位。


---

### 4. 统一异常处理


新增全局异常处理：

异常返回：

{
    "error": "internal_server_error",
    "message": "服务内部异常",
    "request_id": "xxx"
}


保证异常情况下仍然返回统一格式。


---

### 5. API 自动化测试


新增：

tests/test_api.py


测试：

- health接口
- ready接口
- chat正常请求
- chat参数校验


测试结果：

4 passed


---

## 今日总结

Day8 完成 RAG Agent 从 CLI 到 Web API 服务化。

项目现在具备：

- HTTP API入口
- 参数校验
- 统一响应
- 请求追踪
- 异常处理
- 自动化测试


从单机脚本升级为具备后端服务基础能力的 Agent 应用。


# Day9 文档上传、入库任务与状态查询


## 今日目标

为 FastAPI RAG Agent 增加文档上传、后台入库和任务状态查询能力。


## 今日完成

### 1. 文档上传接口

新增：

- `POST /api/v1/documents`

实现：

- 上传 TXT、PDF、DOCX
- 生成 `document_id`
- 返回 `task_id`
- 初始状态为 `pending`


### 2. 文件安全校验

实现：

- 扩展名校验
- MIME 类型校验
- 空文件校验
- 10 MB 大小限制
- 文件保存到受控目录 `data/uploads`
- 不使用用户原始文件名，避免路径穿越


### 3. SHA-256 与幂等处理

将 TXT、PDF、DOCX Loader 的 MD5 统一升级为 SHA-256。

使用原始文件内容的 SHA-256 作为 `document_id`。

相同内容重复上传时：

- 返回相同 `document_id`
- 返回原有 `task_id`
- 不重复保存文件
- 不重复执行入库任务


### 4. 后台入库任务

使用 FastAPI `BackgroundTasks` 调用已有入库流程：

```text
读取文档
↓
文本清洗
↓
文档分块
↓
Embedding
↓
写入向量库
```

任务状态变化：

```text
pending → running → succeeded
                  ↘ failed
```


### 5. 状态查询接口

新增：

- `GET /api/v1/ingestion/{task_id}`

可以查询：

- `document_id`
- `task_id`
- 当前状态
- 失败错误信息


### 6. 配置与依赖

新增配置：

- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_BYTES`

新增依赖：

- `python-multipart`


### 7. 自动化测试

新增测试：

- 非法扩展名
- MIME 类型不匹配
- 超大文件
- 正常上传
- 状态查询
- 重复上传幂等
- 后台任务成功
- 后台任务失败

最终测试结果：

```text
26 passed
```


## 开发重难点

### 1. 上传文件安全

不能直接信任用户提供的文件名和 MIME 类型。

通过扩展名、MIME、文件大小和受控保存目录进行多层校验，并使用 `document_id` 作为保存文件名。


### 2. 后台任务状态管理

上传接口不能等待完整入库流程结束。

使用 `BackgroundTasks` 后台执行入库，并通过内存任务表维护：

- `pending`
- `running`
- `succeeded`
- `failed`


### 3. 重复内容幂等

文件名不同不代表内容不同。

通过 SHA-256 识别文件内容，使重复上传不会重复保存和重复入库。


## 今日收获

1. 学会了使用 FastAPI `UploadFile` 和 `BackgroundTasks` 实现文件上传与后台处理。

2. 理解了任务状态管理和状态查询接口在耗时业务中的作用。

3. 理解了 SHA-256、文件安全校验和幂等策略在企业级上传系统中的重要性。


## 今日总结

Day9 完成了从“只能问答”到“可以通过 API 上传并入库知识文档”的升级。

当前系统已经具备：

- 安全文档上传
- 受控文件保存
- 后台异步入库
- 任务状态查询
- 重复内容幂等
- 自动化测试保障

目前任务状态保存在内存中，服务重启后会清空，后续将迁移到数据库或 Redis。


---

# Day10 问答 API 契约与错误边界

## 今日目标

完善问答 API 契约，增加响应耗时、模型调用超时控制、上游异常映射和自动化测试。

## 完成内容

### 1. 问答 API 契约扩展

`ChatRequest` 新增：

- `conversation_id`
- `knowledge_base_id`

两个字段暂时为可选字段，为后续多轮会话和多知识库功能预留接口。

`RAGResponse` 新增：

- `latency_ms`

接口现在会返回真实的 RAG 问答耗时。

### 2. 参数校验

新增上下文字段校验：

- 字段可以不传
- 传入时不能为空字符串
- 最大长度为 100

### 3. 统一错误边界

新增自定义异常：

- `UpstreamTimeoutError`
- `UpstreamServiceError`

HTTP 错误映射：

- 上游服务超时：`504`
- 上游服务失败：`502`
- 未知内部异常：`500`

错误响应统一包含：

- `error`
- `message`
- `request_id`

客户端不会收到上游敏感错误、密钥、内部配置或 Python 堆栈信息。

### 4. LLM 超时控制

新增配置：

```text
LLM_TIMEOUT_SECONDS
```

默认超时时间为 30 秒。

OpenAI SDK 异常转换：

- `APITimeoutError` → `UpstreamTimeoutError`
- `OpenAIError` → `UpstreamServiceError`

通过异常链保留内部排查信息，同时避免向客户端泄露原始异常。

### 5. 自动化测试

新增和完善：

- 上下文字段空字符串校验
- `latency_ms` 响应校验
- HTTP 504 超时响应测试
- HTTP 502 上游失败测试
- 敏感错误信息不泄露测试
- LLM 超时异常转换测试
- LLM 普通异常转换测试

全量测试结果：

```text
31 passed
```

## SSE 说明

`/chat/stream` SSE 属于可选增强，本次暂不实现。

当前优先保证普通 `/chat` 接口稳定。真正的流式响应将在后续前端体验优化阶段单独开发。

## 今日总结

Day10 完成了问答 API 契约、真实耗时统计、明确的模型超时配置、安全错误映射和异常转换测试。

项目当前具备更稳定、更安全、更容易排查的企业级问答 API 基础。



# Day11：关系数据库持久化与会话历史

日期：2026-08-17

## 今日目标

将用户、知识库、文档、入库任务、会话和消息从临时内存状态迁移到关系数据库，并使用 Alembic 管理数据库结构变更。

## 1. SQLAlchemy 数据模型

新增 SQLAlchemy 2.0 数据模型：

- `users`
- `knowledge_bases`
- `documents`
- `ingestion_jobs`
- `conversations`
- `messages`

模型之间通过外键和 ORM Relationship 建立关联。

消息表增加了 `sequence_number` 字段，并使用以下组合唯一约束：

```text
(conversation_id, sequence_number)
```

该约束保证同一个会话中的消息顺序稳定且不会重复。

## 2. MySQL 与数据库 Session

新增数据库基础设施：

- SQLAlchemy Engine
- `SessionLocal`
- FastAPI `get_db`
- Repository 数据访问层
- Service 事务管理层

数据库连接通过 `.env` 文件中的 `DATABASE_URL` 配置，数据库密码不会直接写在代码中。

连接格式：

```text
mysql+pymysql://用户名:密码@127.0.0.1:3306/agent01?charset=utf8mb4
```

## 3. Alembic 数据库迁移

项目已经接入 Alembic，共创建两次迁移：

```text
3c1068922c5b  create initial relational tables
7af58a1df946  add message sequence number
```

当前数据库迁移版本：

```text
7af58a1df946 (head)
```

可以通过以下命令将空数据库迁移到最新版本：

```powershell
uv run alembic upgrade head
```

可以通过以下命令查看当前数据库版本：

```powershell
uv run alembic current
```

## 4. Repository 与事务边界

新增 Repository：

- `ConversationRepository`
- `DocumentRepository`

Repository 负责执行数据库查询和数据写入。

Service 层负责：

- 提交事务
- 出错时回滚事务
- 组合多个 Repository 操作
- 处理业务规则

这样可以避免把数据库事务逻辑散落在 API 路由中。

## 5. 会话与消息持久化

`POST /api/v1/chat` 现在会执行以下流程：

1. 获取或创建用户；
2. 获取或创建知识库；
3. 获取或创建会话；
4. 执行 RAG 问答；
5. 保存用户消息；
6. 保存助手消息；
7. 保存回答的来源摘要；
8. 返回 `conversation_id`。

用户消息和助手消息在同一个数据库事务中保存。

如果助手消息保存失败，用户消息也会一起回滚，避免数据库中出现不完整的问答记录。

消息按照 `sequence_number` 排序：

```text
1  user
2  assistant
3  user
4  assistant
```

## 6. 来源摘要持久化

助手消息会保存来源摘要，包括：

- `source_id`
- `chunk_id`
- 来源文件信息

数据库只保存必要的来源摘要，不重复保存完整 Chunk 内容。

示例：

```json
{
  "sources": [
    {
      "source_id": "S1",
      "chunk_id": "chunk-1"
    }
  ]
}
```

## 7. 会话历史 API

新增接口：

```text
GET /api/v1/conversations/{conversation_id}/messages
```

接口按照 `sequence_number` 返回会话消息。

每条消息包含：

- 消息 ID
- 消息顺序
- 消息角色
- 消息内容
- 来源摘要
- 创建时间

不存在的会话返回：

```text
HTTP 404
```

## 8. 文档与入库任务持久化

文档上传和后台入库任务已经从进程内存迁移到 MySQL。

数据库会保存：

- 文档 ID
- 知识库 ID
- 原始文件名
- 内容哈希
- 文档状态
- 入库任务状态
- 入库失败原因
- 创建时间
- 更新时间

文档状态包括：

```text
pending
ready
failed
deleted
```

入库任务状态包括：

```text
pending
running
succeeded
failed
```

相同文件内容重复上传时，会根据 SHA-256 内容哈希复用已有文档和入库任务，保证上传接口幂等。

旧的内存任务管理器：

```text
app/services/ingestion/task_manager.py
```

已经删除。

## 9. 后台入库任务

FastAPI 后台任务会创建独立的数据库 Session。

后台任务执行流程：

1. 将任务状态更新为 `running`；
2. 解析并切分文档；
3. 生成 Embedding；
4. 写入 Chroma；
5. 成功后将任务状态更新为 `succeeded`；
6. 将文档状态更新为 `ready`；
7. 失败后将任务和文档状态更新为 `failed`；
8. 记录安全的失败原因；
9. 关闭数据库 Session。

这样可以避免请求 Session 被后台任务继续使用。

## 10. 文档删除 API

新增接口：

```text
DELETE /api/v1/documents/{document_id}
```

接口成功后返回：

```json
{
  "document_id": "文档ID",
  "status": "deleted"
}
```

文档不存在时返回：

```text
HTTP 404
```

## 11. MySQL 与 Chroma 删除一致性

文档删除采用以下策略：

1. 查询 MySQL 中的文档记录；
2. 如果文档已经是 `deleted`，直接返回，保证接口幂等；
3. 先删除 Chroma 中属于该文档的向量；
4. Chroma 删除成功后，将 MySQL 文档状态更新为 `deleted`；
5. 提交 MySQL 事务；
6. 如果 Chroma 删除失败，则回滚数据库事务。

项目不会直接物理删除 MySQL 文档记录，而是使用软删除状态，便于审计、问题排查和故障恢复。

因为 Chroma 删除操作本身具有幂等性，如果数据库提交出现异常，可以重新调用删除接口完成最终一致性修复。

## 12. 自动化测试

新增和完善了以下测试：

- Repository 数据写入与查询
- 数据库事务回滚
- 默认用户创建
- 默认知识库创建
- 会话创建
- 用户消息保存
- 助手消息保存
- 消息顺序校验
- 来源摘要保存
- 问答消息事务提交
- 问答消息事务回滚
- 会话历史 API
- 会话不存在时返回 404
- 文档记录创建
- 入库任务创建
- 文档上传幂等
- 入库任务状态更新
- 后台任务成功状态
- 后台任务失败状态
- 文档删除成功
- Chroma 删除失败时数据库回滚
- 文档删除 API
- 删除不存在的文档返回 404

最终全量测试结果：

```text
48 passed, 1 warning
```

当前 warning 来自 FastAPI/Starlette TestClient 的依赖弃用提醒，不影响项目功能和测试结果。

## Day11 验收结果

- [x] SQLAlchemy 2.0 接入完成
- [x] MySQL 数据库连接完成
- [x] 六张核心业务表创建完成
- [x] Alembic 迁移完成
- [x] 数据库处于最新迁移版本
- [x] Repository 层完成
- [x] Service 事务边界完成
- [x] 问答消息持久化完成
- [x] 来源摘要持久化完成
- [x] 会话历史 API 完成
- [x] 文档和入库任务持久化完成
- [x] 上传幂等完成
- [x] 文档删除 API 完成
- [x] MySQL 与 Chroma 删除一致性策略完成
- [x] 旧内存任务管理器删除完成
- [x] 全量自动化测试通过

## 今日总结

Day11 完成了 SQLAlchemy 关系数据模型、MySQL 持久化、Alembic 数据库迁移、Repository 数据访问层、Service 事务边界、会话与消息历史、问答来源摘要、文档与入库任务持久化，以及 MySQL 与 Chroma 的文档删除一致性策略。

项目不再依赖进程内存保存核心业务状态。服务重启以后，用户、知识库、文档、入库任务、会话和消息数据仍然可以保留。

至此，Day11 开发任务完成。