from openai import APITimeoutError, OpenAI, OpenAIError

from app.core.exceptions import (
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.core.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)



client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=LLM_TIMEOUT_SECONDS,
)


def generate_answer(
    system_prompt: str,
    user_prompt: str,
):
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.2,
        )
    except APITimeoutError as exc:
        raise UpstreamTimeoutError(
            "LLM request timed out"
        ) from exc
    except OpenAIError as exc:
        raise UpstreamServiceError(
            "LLM request failed"
        ) from exc

    return response.choices[0].message.content