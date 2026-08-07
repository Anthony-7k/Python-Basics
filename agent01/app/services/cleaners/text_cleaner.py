import re


def clean_text(text: str) -> str:
    """
    文本清洗:
    1. 删除不可见字符
    2. 合并多余空格
    3. 合并多余换行
    """

    # 删除零宽字符
    text = re.sub(r"\u200b", "", text)

    # 删除每行首尾空格
    text = "\n".join(
        line.strip()
        for line in text.splitlines()
    )

    # 合并连续空格和 tab
    text = re.sub(r"[ \t]+", " ", text)

    # 合并多余换行
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()