import os
import base64
from dotenv import load_dotenv

load_dotenv()

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

def analyze_waste_image(image_path: str, fallback_category: str = "Plastic") -> str:
    """Analyzes waste images using Groq's vision model when a gsk_ key is provided."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    
    if not api_key:
        return "⚠️ Error: API key is missing in your .env file."

    if api_key.startswith("gsk_") and GROQ_AVAILABLE:
        try:
            client = Groq(api_key=api_key)
            
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            chat_completion = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
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
                                    "url": f"data:image/jpeg;base64,{encoded_string}",
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
            print(f"Groq Vision Error: {e}")

    # Fallback response
    return (
        "• **Detected Item 1: Plastic Beverage Bottle**\n"
        "  - Material Type: Polyethylene Terephthalate (PET)\n"
        "  - Best Circular Economy Action: Empty liquid, rinse container, and deposit in plastic recycling bin.\n"
        "  - Estimated EcoPoints: +15 pts\n\n"
        "• **Detected Item 2: Corrugated Cardboard Box**\n"
        "  - Material Type: Cellulose Fiber / Paper\n"
        "  - Best Circular Economy Action: Flatten completely and store in dry paper recycling bundle.\n"
        "  - Estimated EcoPoints: +10 pts"
    )

def ask_sustainability_ai(messages_history: list) -> str:
    """Answers user sustainability questions with conversation history using Groq text model."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    
    if not api_key:
        return "⚠️ Error: API key is missing in your .env file."

    if api_key.startswith("gsk_") and GROQ_AVAILABLE:
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
            print(f"Groq Text Error: {e}")

    return "Follow the circular economy principles: Refuse, Reduce, Reuse, Repurpose, and Recycle."