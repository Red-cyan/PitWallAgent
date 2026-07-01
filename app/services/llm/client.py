from openai import OpenAI

from app.config.settings import settings


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for chat generation.")

        self.model = model or settings.llm_model
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
