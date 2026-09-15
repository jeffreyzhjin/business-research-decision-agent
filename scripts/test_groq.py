import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY was not found. Check the .env file."
    )

client = Groq(api_key=api_key)

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a business research assistant. "
                "Answer clearly and concisely."
            ),
        },
        {
            "role": "user",
            "content": (
                "In one sentence, explain why evidence matters "
                "in business decision-making."
            ),
        },
    ],
)

print(response.choices[0].message.content)