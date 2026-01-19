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

    async def decide(self, text: str, current_now: str):
        clean_text = text.lower().strip()
        
        # Fast-track for simple commands
        if clean_text in ["onboard", "help", "guide"]:
            return {"intent": "ONBOARD", "data": {}}
        if clean_text in ["list", "show vault", "show list"]:
            return {"intent": "LIST", "data": {"store": "All"}}

        system_prompt = (
            f"SYSTEM: You are a logic parser. Current time: {current_now}. "
            "Output ONLY valid JSON. The word 'json' is required.\n\n"
            "--- GENERAL RULES ---\n"
            "1. ALWAYS return top-level keys 'intent' and 'data'.\n"
            "2. Always singularize item names (apples -> apple, eggs -> egg).\n\n"
            "--- INTENT-SPECIFIC RULES ---\n"
            "1. TASK: Extract ONLY NEW items. NEVER calculate totals. Default store: 'General'.\n"
            "   * 'add 2 more' -> count: 2. 'I need 5 apples' -> count: 5.\n"
            "2. DELETE: Use mode 'SINGLE' for specific counts or 'ALL' to wipe an item.\n"
            "3. REMIND: Extract the task description and relative minutes from now.\n"
            "4. LIST: Default store: 'All'. Use specific name ONLY if mentioned.\n"
            "5. MOVE: Use when moving an item from one store to another. Extract 'item', 'from_store', and 'to_store'.\n\n"
            "--- SCHEMA EXAMPLES ---\n"
            "- {'intent': 'TASK', 'data': {'items': [{'name': 'apple', 'count': 2, 'store': 'General'}]}}\n"
            "- {'intent': 'DELETE', 'data': {'items': [{'name': 'apple', 'count': 1}], 'mode': 'SINGLE'}}\n"
            "- {'intent': 'REMIND', 'data': {'item': 'check oven', 'minutes': 10}}\n"
            "- {'intent': 'LIST', 'data': {'store': 'All'}}\n"
            "- {'intent': 'MOVE', 'data': {'item': 'apple', 'from_store': 'General', 'to_store': 'Safeway'}}\n"
            "- {'intent': 'CHAT', 'data': {'answer': 'Hi there!'}}"
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