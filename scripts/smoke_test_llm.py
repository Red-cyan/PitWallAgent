import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.llm.client import LLMClient


def main() -> None:
    client = LLMClient()
    response = client.chat(
        messages=[
            {"role": "system", "content": "You are a concise Formula 1 assistant."},
            {"role": "user", "content": "Reply with exactly: DeepSeek connection ok."},
        ],
        temperature=0,
    )
    print(response)


if __name__ == "__main__":
    main()
