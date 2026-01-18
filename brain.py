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
        self.model = os.getenv("MODEL_NAME", "llama3-8b-8192")
        self.client = Groq(api_key=self.api_key)

    # 🚀 FIX: Added 'current_now' as the second positional argument
    async def decide(self, text: str, current_now: str):
        # 🚀 Instant Keyword Short-Circuits
        clean_text = text.lower().strip()
        if clean_text in ["onboard", "help", "guide", "how to use"]:
            return {"intent": "ONBOARD", "data": {}}
        if clean_text in ["list", "show vault", "show list"]:
            return {"intent": "LIST", "data": {}}

        system_prompt = (
            f"SYSTEM: You are a backend logic parser. Current time is {current_now}. "
            "You MUST output a valid JSON object. No preambles.\n\n"
            "ALLOWED INTENTS:\n"
            "- TASK: {'intent': 'TASK', 'data': {'item': 'str'}}\n"
            "- DELETE: {'intent': 'DELETE', 'data': {'item': 'str', 'mode': 'SINGLE'|'ALL'}}\n"
            "   * If user says 'clear list' or 'wipe everything', item is 'EVERYTHING'.\n"
            "- LIST: {'intent': 'LIST', 'data': {}}\n"
            "- REMIND: {'intent': 'REMIND', 'data': {'item': 'str', 'minutes': int}}\n"
            "- CHAT: {'intent': 'CHAT', 'data': {'answer': 'str'}}\n"
            "- ONBOARD: User asks for help.\n"
            "- UNKNOWN: If the request is nonsensical."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            raw_content = response.choices[0].message.content
            logger.info(f"🧠 BRAIN RAW OUTPUT: {raw_content}")
            return json.loads(raw_content)

        except Exception as e:
            logger.error(f"💥 BRAIN ERROR: {str(e)}")
            return {"intent": "UNKNOWN", "data": {}}