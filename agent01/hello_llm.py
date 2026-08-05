from openai import OpenAI
from dotenv import load_dotenv
import os


load_dotenv()


def main():

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL")
    )


    while True:

        question = input(
            "请输入问题:"
        )


        if question == "exit":
            break


        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {
                    "role":"user",
                    "content":question
                }
            ],
            temperature=0.7,
            max_tokens=500
        )


        print(
            "AI:",
            response.choices[0].message.content
        )


if __name__ == "__main__":
    main()