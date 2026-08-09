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
