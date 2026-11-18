"""List every model id available on your Groq account.

Loads .env, builds a Groq client with GROQ_API_KEY, and prints the id of every
model returned by client.models.list().data. Use this to pick a valid value for
the GROQ_VISION_MODEL env var used by the waste scanner.

Run:  python list_models.py
"""
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("GROQ_API_KEY is missing in your .env file.")
    raise SystemExit(1)

client = Groq(api_key=api_key)

models = client.models.list().data
for m in models:
    print(m.id)

print(f"\n{len(models)} model(s) available.")
