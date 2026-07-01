# services/llm/client.py

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class LLMClient:
    def __init__(self, model="gpt-4.1-mini"):
        self.model = model

    def chat(self, messages, temperature=0.2):
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content