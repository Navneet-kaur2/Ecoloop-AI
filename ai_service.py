import os
import base64
import logging
import mimetypes
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Groq vision model used for waste image analysis.
# Read from the GROQ_VISION_MODEL env var so it can be swapped without a code
# change (Groq retires preview models over time). Run list_models.py to see
# which model ids are currently available on your account.
VISION_MODEL = os.environ.get("GROQ_VISION_MODEL") or "qwen/qwen3.8-27b"

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def _get_groq_api_key() -> str:
    """Return the configured Groq API key.

    Prefers GROQ_API_KEY but falls back to the legacy GEMINI_API_KEY env var so
    existing deployments keep working without touching their .env file.
    """
    return (os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY", "")).strip()


def analyze_waste_image(image_path: str, fallback_category: str = "Plastic") -> str:
    """Analyze a waste image with Groq's vision model.

    Returns the model's analysis on success. On any failure (missing package,
    missing/bad API key, or an API error) returns an error string starting with
    "⚠️" and logs the full traceback. Never returns fabricated data.
    """
    api_key = _get_groq_api_key()

    if not GROQ_AVAILABLE:
        return (
            "⚠️ Image analysis failed: the `groq` Python package is not installed. "
            "Run `pip install -r requirements.txt` and restart the app."
        )

    if not api_key:
        return (
            "⚠️ Image analysis failed: GROQ_API_KEY is missing in your .env file. "
            "Add a Groq key that starts with 'gsk_'."
        )

    if not api_key.startswith("gsk_"):
        return (
            "⚠️ Image analysis failed: the API key does not look like a Groq key. "
            "GROQ_API_KEY must start with 'gsk_' (it currently does not)."
        )

    try:
        client = Groq(api_key=api_key)

        # Detect the real MIME type instead of hardcoding image/jpeg.
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        chat_completion = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this waste image. Identify all distinct items and materials visible. For each item, provide: 1. Item Name, 2. Material Type, 3. Best Circular Economy Action (Recycle, Upcycle, Compost, or Reuse), 4. Estimated EcoPoints earned. Format clearly as itemized bullet points."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_string}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.exception("Groq vision analysis failed")
        return f"⚠️ Image analysis failed: {e}"


def ask_sustainability_ai(messages_history) -> str:
    """Answer user sustainability questions using Groq's text model.

    Accepts either a list of chat messages or a plain question string. Returns
    the model's answer on success. On any failure returns an error string
    starting with "⚠️" and logs the full traceback. Never returns fabricated data.
    """
    # Normalize input: accept either a list of messages or a plain question string.
    if isinstance(messages_history, str):
        messages_history = [{"role": "user", "content": messages_history}]

    api_key = _get_groq_api_key()

    if not GROQ_AVAILABLE:
        return (
            "⚠️ The `groq` Python package is not installed. "
            "Run `pip install -r requirements.txt` and restart the app."
        )

    if not api_key:
        return "⚠️ GROQ_API_KEY is missing in your .env file."

    if not api_key.startswith("gsk_"):
        return "⚠️ GROQ_API_KEY does not look like a Groq key (it must start with 'gsk_')."

    try:
        client = Groq(api_key=api_key)

        # Prepend the system instructions to the chat history array
        formatted_messages = [
            {
                "role": "system",
                "content": "You are EcoLoop AI's expert Sustainability Assistant. Provide clear, practical, and structured guidance with bullet points."
            }
        ] + messages_history

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=formatted_messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.exception("Groq text completion failed")
        return f"⚠️ Sustainability assistant failed: {e}"
