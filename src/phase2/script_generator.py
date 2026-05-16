"""
Generates a Hebrew TikTok script for a product using GPT-4o.
Saves to videos/{asin}/script_he.txt
Skips if file already exists.
"""

import os
from pathlib import Path
from openai import OpenAI


SYSTEM_PROMPT = "You are a Hebrew TikTok content creator who writes short, punchy product scripts for Israeli audiences."

USER_PROMPT_TEMPLATE = """Write a short Hebrew TikTok script for this Amazon product.

Product: {name}
Category: {category}
Price: ${price}
Tone: {tone}

Rules:
- 100-{max_words} words in Hebrew
- Conversational, enthusiastic, casual Israeli style
- End with a call to action to click the link in bio
- No emojis
- Output Hebrew text only, nothing else
"""


def generate_script(product: dict, output_dir: Path, config: dict) -> bool:
    """
    Generate Hebrew script and save to output_dir/{asin}/script_he.txt.
    Returns True on success, False on failure.
    """
    asin = product["asin"]
    dest_dir = output_dir / asin
    dest_file = dest_dir / "script_he.txt"

    if dest_file.exists():
        print(f"  [script] already exists, skipping")
        return True

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"  [script] OPENAI_API_KEY not set — skipping")
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    name = product.get("name") or asin
    category = product.get("category") or "general"
    price = product.get("price_usd") or 0
    max_words = config.get("script_max_words", 150)
    tone = config.get("script_tone", "enthusiastic, casual, Israeli TikTok style")

    prompt = USER_PROMPT_TEMPLATE.format(
        name=name, category=category, price=f"{price:.2f}",
        tone=tone, max_words=max_words
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=config.get("gpt_model", "gpt-4o"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.8,
        )
        script = response.choices[0].message.content.strip()
        dest_file.write_text(script, encoding="utf-8")
        print(f"  [script] generated ({len(script.split())} words)")
        return True
    except Exception as e:
        print(f"  [script] GPT error: {e}")
        return False
