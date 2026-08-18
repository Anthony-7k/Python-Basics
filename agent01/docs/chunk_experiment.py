import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.chunkers.chunker import split_text

def analyze_chunks(chunks):
    lengths = [
        len(chunk.content)
        for chunk in chunks
    ]

    print(f"chunk数量: {len(chunks)}")
    print(f"平均长度: {sum(lengths) / len(lengths):.2f}")
    print(f"最大长度: {max(lengths)}")
    print(f"最小长度: {min(lengths)}")


if __name__ == "__main__":

    text = """
    人工智能正在快速发展。
    企业开始使用大模型提升工作效率。
    RAG技术可以让模型结合企业知识库回答问题。
    """ * 100

    chunks = split_text(
        text=text,
        document_id="demo001",
        knowledge_base_id="demo-kb",
        chunk_size=500,
        chunk_overlap=100,
    )


    analyze_chunks(chunks)
