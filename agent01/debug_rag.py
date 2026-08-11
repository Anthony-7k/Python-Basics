from app.services.rag.rag_service import answer_question


def main():

    question = "员工每年有多少天年假？"

    result = answer_question(
        question=question,
        top_k=3,
    )

    print("答案:")
    print(result.answer)

    print("\n引用:")

    for source in result.sources:
        print(source)


if __name__ == "__main__":
    main()