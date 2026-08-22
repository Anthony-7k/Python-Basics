import math
import re
from collections import Counter


TOKEN_PATTERN = re.compile(
    r"[a-z0-9]+|[\u4e00-\u9fff]+",
    re.IGNORECASE,
)


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/ASCII policy text without extra packages."""
    tokens: list[str] = []

    for match in TOKEN_PATTERN.finditer(text.lower()):
        value = match.group(0)

        if "\u4e00" <= value[0] <= "\u9fff":
            if len(value) == 1:
                tokens.append(value)
            else:
                tokens.extend(
                    value[index:index + 2]
                    for index in range(len(value) - 1)
                )
        else:
            tokens.append(value)

    return tokens


def bm25_scores(
    query_text: str,
    items: list[dict],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    if not items:
        return []

    tokenized_documents = [
        tokenize(item.get("content", ""))
        for item in items
    ]
    query_tokens = set(tokenize(query_text))

    if not query_tokens:
        return [0.0] * len(items)

    document_count = len(tokenized_documents)
    average_length = (
        sum(len(tokens) for tokens in tokenized_documents)
        / document_count
    ) or 1.0
    document_frequency = Counter()

    for tokens in tokenized_documents:
        document_frequency.update(set(tokens))

    scores: list[float] = []

    for tokens in tokenized_documents:
        frequencies = Counter(tokens)
        document_length = len(tokens)
        score = 0.0

        for token in query_tokens:
            frequency = frequencies.get(token, 0)

            if frequency == 0:
                continue

            frequency_in_documents = document_frequency[token]
            inverse_document_frequency = math.log(
                1
                + (
                    document_count
                    - frequency_in_documents
                    + 0.5
                )
                / (frequency_in_documents + 0.5)
            )
            denominator = frequency + k1 * (
                1
                - b
                + b * document_length / average_length
            )
            score += inverse_document_frequency * (
                frequency * (k1 + 1) / denominator
            )

        scores.append(score)

    return scores


def retrieve_keywords(
    query_text: str,
    items: list[dict],
    *,
    limit: int,
    min_score: float = 0.0,
) -> list[dict]:
    scored_items = []

    for item, score in zip(
        items,
        bm25_scores(query_text, items),
    ):
        if score <= min_score:
            continue

        result = dict(item)
        result["keyword_score"] = float(score)
        result.setdefault("distance", None)
        scored_items.append(result)

    scored_items.sort(
        key=lambda item: (
            -item["keyword_score"],
            item["chunk_id"],
        )
    )

    return scored_items[:limit]
