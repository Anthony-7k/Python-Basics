from app.services.rag.rag_service import answer_question
import os


def main():

    question = "员工每年有多少天年假？"

    result = answer_question(
        question=question,
        top_k=3,
        knowledge_base_id=os.environ[
            "KNOWLEDGE_BASE_ID"
        ],
    )

    print("答案:")
    print(result.answer)

    print("\n引用:")

    for source in result.sources:
        print(source)


if __name__ == "__main__":
    main()
