import os, json, logging
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
        if clean_text in ["onboard", "help", "guide"]: return {"intent": "ONBOARD", "data": {}}
        if clean_text in ["list", "show vault", "show list"]: return {"intent": "LIST", "data": {"store": "All"}}

        system_prompt = (
            f"SYSTEM: You are a logic parser for 'Adjnt'. Current time: {current_now}. "
            "Output ONLY valid JSON. The word 'json' is required.\n\n"
            "--- GENERAL RULES ---\n"
            "1. ALWAYS return top-level keys 'intent' and 'data'.\n"
            "2. Always singularize item names (apples -> apple).\n"
            "3. Use plural 'items' list for ALL vault actions (TASK, DELETE).\n\n"
            "--- INTENT-SPECIFIC RULES ---\n"
            "1. TASK: Add items to vault. Each must have 'name', 'count', 'store'. Default store: 'General'.\n"
            "2. DELETE: For vault items (groceries/objects).\n"
            "   - To clear a specific store: mode: 'ALL', store: 'StoreName', items: [].\n"
            "   - To clear everything: mode: 'CLEAR_ALL'.\n"
            "   - To remove specific count: mode: 'SINGLE', items: [{'name': 'apple', 'count': 3}].\n"
            "3. DELETE_REMINDERS: Use this ONLY when user wants to remove a scheduled reminder or appointment (e.g., 'remove meet neha'). Provide 'item' name.\n"
            "4. REMIND: For relative time, use 'minutes'. For specific dates, use 'timestamp': 'YYYY-MM-DD HH:MM:SS'.\n"
            "5. LIST: Use 'LIST' for vault items. Use 'LIST_REMINDERS' for schedules/reminders.\n"
            "6. MOVE: Extract 'item', 'from_store', 'to_store'.\n\n"
            "--- SCHEMA EXAMPLES ---\n"
            "- {'intent': 'DELETE', 'data': {'mode': 'ALL', 'store': 'Safeway', 'items': []}}\n"
            "- {'intent': 'DELETE_REMINDERS', 'data': {'item': 'meet neha'}}\n"
            "- {'intent': 'REMIND', 'data': {'item': 'neha Lunch', 'timestamp': '2026-01-24 10:30:00'}}\n"
            "- {'intent': 'LIST_REMINDERS', 'data': {}}\n"
            "- {'intent': 'TASK', 'data': {'items': [{'name': 'apple', 'count': 3, 'store': 'General'}]}}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            raw = response.choices[0].message.content
            logger.info(f"🧠 BRAIN RAW: {raw}")
            return json.loads(raw)
        except Exception as e:
            logger.error(f"💥 BRAIN ERROR: {e}")
            return {"intent": "UNKNOWN", "data": {}}