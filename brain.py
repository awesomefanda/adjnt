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
            f"SYSTEM: You are a backend logic parser. Current time: {current_now}. "
            "You MUST output ONLY a valid JSON object. No preambles or explanations.\n\n"
            "INTENT SCHEMA & RULES:\n"
            "- TASK: {'intent': 'TASK', 'data': {'items': ['item1', 'item2']}}\n"
            "  * RULE: Extract the specific items to be added. If a user says 'add one more milk', the items list should be ['milk'].\n"
            "  * RULE: Never repeat the same item in the 'items' array unless they have different adjectives (e.g., ['green apple', 'red apple']).\n"
            "  * RULE: Map verbs like 'stash', 'pick up', 'get', 'need' to TASK.\n"
            "- DELETE: {'intent': 'DELETE', 'data': {'items': ['item1'], 'mode': 'SINGLE'|'ALL'}}\n"
            "  * RULE: 'SINGLE' removes one instance. 'ALL' removes every instance of that name.\n"
            "  * RULE: If the user wants to wipe the whole list, set items to ['EVERYTHING'].\n"
            "- LIST: {'intent': 'LIST', 'data': {}}\n"
            "  * RULE: Use for 'what's in my vault', 'show list', or 'check my items'.\n"
            "- REMIND: {'intent': 'REMIND', 'data': {'item': 'str', 'minutes': int}}\n"
            "  * RULE: Calculate minutes relative to the current time if the user provides a specific time.\n"
            "- CHAT: {'intent': 'CHAT', 'data': {'answer': 'str'}}\n"
            "  * RULE: Use for general questions, advice, or greetings.\n"
            "- ONBOARD: {'intent': 'ONBOARD', 'data': {}}\n"
            "  * RULE: Use when user asks for 'help', 'instructions', or 'how to use'.\n"
            "- UNKNOWN: {'intent': 'UNKNOWN', 'data': {}}\n"
            "  * RULE: Use if the input is nonsensical or no other intent fits."
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