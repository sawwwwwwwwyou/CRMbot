"""AI parsing module using OpenAI."""
import json
from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Ты анализируешь сообщения о рекламном сотрудничестве. Извлеки информацию:

- brand: Название компании/бренда
- request: Что хотят (1 короткое предложение на русском)
- contact: Имя контактного лица
- dates: Упомянутые даты/дедлайны

Верни ТОЛЬКО валидный JSON без markdown:
{"brand": "...", "request": "...", "contact": "...", "dates": "..."}

Если что-то не найдено, используй null."""


async def parse_messages(combined_text: str) -> dict:
    """Parse combined messages and extract lead info."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": combined_text}
            ],
            temperature=0.1,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)

        return {
            "brand": result.get("brand"),
            "request": result.get("request"),
            "contact": result.get("contact"),
            "dates": result.get("dates")
        }

    except json.JSONDecodeError:
        return {"brand": None, "request": None, "contact": None, "dates": None}
    except Exception as e:
        print(f"AI parsing error: {e}")
        return {"brand": None, "request": None, "contact": None, "dates": None}
