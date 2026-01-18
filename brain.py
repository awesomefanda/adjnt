import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Adjnt.Brain")

class AdjntBrain:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
        self.client = Groq(api_key=self.api_key)

    async def decide(self, text: str):
        # 🚀 STRONGER PROMPT: Explicitly forbids conversational filler
        system_prompt = (
            "SYSTEM: You are a backend logic parser. You MUST output a valid JSON object. "
            "Never include preambles, notes, or explanations. "
            "ALLOWED INTENTS: TASK, DELETE_TASK, LIST, CLEAR_TASKS, REMIND, REMOVE_REMINDER, CHAT. "
            "SCHEMA RULES:\n"
            "- TASK: {'intent': 'TASK', 'data': {'item': 'description'}}\n"
            "- DELETE_TASK: {'intent': 'DELETE_TASK', 'data': {'item': 'description'}}\n"
            "- LIST: {'intent': 'LIST', 'data': {}}\n"
            "- REMIND: {'intent': 'REMIND', 'data': {'item': 'description', 'minutes': int}}\n"
            "- CHAT: {'intent': 'CHAT', 'data': {'answer': 'your text response'}}\n"
            "If the user asks for their list, use intent 'LIST'."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                # 🚀 FORCED JSON MODE
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            logger.info(f"🧠 BRAIN RAW OUTPUT: {raw_content}") # See exactly what the AI said
            return json.loads(raw_content)

        except Exception as e:
            logger.error(f"💥 BRAIN ERROR: {str(e)}")
            # Improved Fallback: includes the error in the chat so you know it broke
            return {"intent": "CHAT", "data": {"answer": f"Glitch in my brain: {str(e)}"}}