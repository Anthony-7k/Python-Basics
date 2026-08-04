from openai import OpenAI
from dotenv import load_dotenv
import os


# 加载 .env 文件
load_dotenv()


def main():
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL")
    )

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=[
            {
                "role": "user",
                "content": "你好，请简单介绍一下你自己"
            }
        ],
        temperature=0.7,
        max_tokens=500
    )

    print("DeepSeek回复：")
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()