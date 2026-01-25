import os, json, logging, re
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
logger = logging.getLogger("Adjnt.Brain")

class AdjntBrain:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("MODEL_NAME", "llama3-8b-8192")
        self.client = Groq(api_key=self.api_key)

    async def decide(self, text: str, current_now: str):
        clean_text = text.lower().strip()
        
        # Quick returns for common patterns
        if clean_text in ["onboard", "help", "guide"]: 
            return {"intent": "ONBOARD", "data": {}}
        if clean_text in ["list", "show vault", "show list"]: 
            return {"intent": "LIST", "data": {"store": "All"}}
        if clean_text in ["list reminders", "show reminders", "my reminders"]:
            return {"intent": "LIST_REMINDERS", "data": {}}
        
        # Handle simple greetings/thanks (but not capability questions with context)
        # Avoid catching phrases like "what's on..." which should go to LLM
        simple_chat = ["how are you", "hello", "hi there", "hey there", "thanks", "thank you", "goodbye", "bye"]
        if clean_text in simple_chat or (clean_text.startswith(("hi", "hello", "hey")) and len(clean_text.split()) <= 2):
            return {"intent": "CHAT", "data": {"answer": "I'm Adjnt, your personal assistant! Type 'help' to see what I can do."}}

        system_prompt = (
            f"SYSTEM: You are a logic parser for 'Adjnt', a shopping list and reminder manager. "
            f"Current time: {current_now}. Output ONLY valid JSON.\n\n"
            
            "=== CORE RULES ===\n"
            "1. ALWAYS return JSON with 'intent' and 'data' keys.\n"
            "2. ALWAYS singularize item names: 'eggs' → 'egg', 'apples' → 'apple', 'tomatoes' → 'tomato', 'oranges' → 'orange'.\n"
            "3. ALWAYS capitalize store names: 'safeway' → 'Safeway', 'costco' → 'Costco'.\n"
            "4. Default store is 'General' if not specified.\n"
            "5. Use 'items' array for TASK and DELETE intents.\n\n"
            
            "=== INTENT DEFINITIONS ===\n\n"
            
            "** TASK (Add to Shopping List) **\n"
            "Triggers: 'add', 'get', 'buy', 'need', 'pick up', 'purchase'\n"
            "Structure: {'intent': 'TASK', 'data': {'items': [{'name': 'milk', 'count': 1, 'store': 'General'}]}}\n"
            "Examples:\n"
            "  - 'add milk' → {'intent': 'TASK', 'data': {'items': [{'name': 'milk', 'count': 1, 'store': 'General'}]}}\n"
            "  - 'add 3 eggs to Safeway' → {'intent': 'TASK', 'data': {'items': [{'name': 'egg', 'count': 3, 'store': 'Safeway'}]}}\n"
            "  - 'get 2 apples and 5 bananas from Costco' → {'intent': 'TASK', 'data': {'items': [{'name': 'apple', 'count': 2, 'store': 'Costco'}, {'name': 'banana', 'count': 5, 'store': 'Costco'}]}}\n\n"
            
            "** DELETE (Remove from Shopping List) **\n"
            "Triggers: 'remove', 'delete', 'take off', 'clear' (for physical items/groceries)\n"
            "Modes:\n"
            "  - SINGLE: Remove specific count from anywhere (when count is specified)\n"
            "  - ALL: Remove all occurrences from specific store OR everywhere\n"
            "  - CLEAR_STORE: Clear all items from a specific store (when 'clear [store]' is mentioned)\n"
            "Structure:\n"
            "  - Specific count: {'intent': 'DELETE', 'data': {'mode': 'SINGLE', 'items': [{'name': 'milk', 'count': 2}]}}\n"
            "  - From store: {'intent': 'DELETE', 'data': {'mode': 'ALL', 'items': [{'name': 'milk', 'store': 'Safeway'}]}}\n"
            "  - Clear specific store: {'intent': 'DELETE', 'data': {'mode': 'CLEAR_STORE', 'store': 'Safeway'}}\n"
            "  - Clear everything: {'intent': 'DELETE', 'data': {'mode': 'CLEAR_ALL'}}\n"
            "Examples:\n"
            "  - 'remove 2 milk' → {'intent': 'DELETE', 'data': {'mode': 'SINGLE', 'items': [{'name': 'milk', 'count': 2}]}}\n"
            "  - 'remove milk from Safeway' → {'intent': 'DELETE', 'data': {'mode': 'ALL', 'items': [{'name': 'milk', 'store': 'Safeway'}]}}\n"
            "  - 'delete all apples' → {'intent': 'DELETE', 'data': {'mode': 'ALL', 'items': [{'name': 'apple'}]}}\n"
            "  - 'clear safeway' → {'intent': 'DELETE', 'data': {'mode': 'CLEAR_STORE', 'store': 'Safeway'}}\n"
            "  - 'clear list' or 'clear vault' → {'intent': 'DELETE', 'data': {'mode': 'CLEAR_ALL'}}\n\n"
            
            "** MOVE (Transfer Between Stores) **\n"
            "Triggers: 'move', 'transfer', 'change store', 'switch'\n"
            "IMPORTANT: When user says 'move oranges' (plural), singularize to 'orange' and set move_all: true.\n"
            "Structure: {'intent': 'MOVE', 'data': {'item': 'bread', 'from_store': 'General', 'to_store': 'Costco', 'move_all': true}}\n"
            "Examples:\n"
            "  - 'move bread from General to Costco' → {'intent': 'MOVE', 'data': {'item': 'bread', 'from_store': 'General', 'to_store': 'Costco', 'move_all': true}}\n"
            "  - 'move oranges from Safeway to General' → {'intent': 'MOVE', 'data': {'item': 'orange', 'from_store': 'Safeway', 'to_store': 'General', 'move_all': true}}\n"
            "  - 'transfer eggs from Safeway to Target' → {'intent': 'MOVE', 'data': {'item': 'egg', 'from_store': 'Safeway', 'to_store': 'Target', 'move_all': true}}\n\n"
            
            "** REMIND (Set Time-Based Reminder) **\n"
            "Triggers: 'remind', 'reminder', 'alert', 'notify', 'schedule', 'meet', 'appointment'\n"
            "Time Parsing Rules:\n"
            "  - 'in X hours/minutes' → Use 'minutes' key\n"
            "  - 'tomorrow' → Calculate next day date with appropriate time\n"
            "  - 'on Saturday', 'Saturday', 'next Saturday' → Calculate the next Saturday from current date\n"
            "  - If no specific time mentioned for a date, use a reasonable default like 09:00:00 (9 AM), NOT midnight\n"
            "  - Current date/time is provided in the system message for calculations\n\n"
            "Recurrence Support:\n"
            "  - 'every day', 'daily' → {'recurrence': 'daily'}\n"
            "  - 'every week', 'weekly' → {'recurrence': 'weekly'}\n"
            "  - 'every Monday', 'every Tuesday', etc. → {'recurrence': 'weekly', 'day_of_week': 'Monday'}\n"
            "  - 'every month', 'monthly' → {'recurrence': 'monthly'}\n"
            "  - 'every year', 'yearly', 'annually' → {'recurrence': 'yearly'}\n"
            "  - 'every weekday', 'weekdays', 'Monday through Friday', 'Monday to Friday' → {'recurrence': 'weekdays'}\n"
            "  - 'every weekend', 'weekends' → {'recurrence': 'weekend'}\n\n"
            "CRITICAL DATE CALCULATION:\n"
            "  - Today's date is extracted from 'Current time' at the top of this prompt\n"
            "  - 'Saturday' or 'on Saturday' means the NEXT Saturday from today\n"
            "  - If today is Tuesday Jan 21, then 'Saturday' = Saturday Jan 25\n"
            "  - If no time specified, default to 9 AM (09:00:00), NOT midnight\n\n"
            "Structure:\n"
            "  - Relative: {'intent': 'REMIND', 'data': {'item': 'walk dog', 'minutes': 120}}\n"
            "  - Specific: {'intent': 'REMIND', 'data': {'item': 'Music class', 'timestamp': '2026-01-28 17:00:00'}}\n"
            "  - Recurring: {'intent': 'REMIND', 'data': {'item': 'standup meeting', 'timestamp': '2026-01-22 09:00:00', 'recurrence': 'daily'}}\n"
            "  - Weekly recurring: {'intent': 'REMIND', 'data': {'item': 'team meeting', 'timestamp': '2026-01-27 14:00:00', 'recurrence': 'weekly', 'day_of_week': 'Monday'}}\n"
            "Examples:\n"
            "  - 'remind me in 2 hours to walk dog' → {'intent': 'REMIND', 'data': {'item': 'walk dog', 'minutes': 120}}\n"
            "  - 'Music class next Wednesday 5pm' → {'intent': 'REMIND', 'data': {'item': 'Music class', 'timestamp': '2026-01-28 17:00:00'}}\n"
            "  - 'meet Jaideep on Saturday' → Calculate next Saturday + 09:00:00 (NOT midnight!)\n"
            "  - 'standup meeting every day at 9am' → {'intent': 'REMIND', 'data': {'item': 'standup meeting', 'timestamp': '[tomorrow] 09:00:00', 'recurrence': 'daily'}}\n"
            "  - 'team meeting every Monday at 2pm' → {'intent': 'REMIND', 'data': {'item': 'team meeting', 'timestamp': '[next Monday] 14:00:00', 'recurrence': 'weekly', 'day_of_week': 'Monday'}}\n"
            "  - 'gym every weekday at 6am' → {'intent': 'REMIND', 'data': {'item': 'gym', 'timestamp': '[tomorrow] 06:00:00', 'recurrence': 'weekdays'}}\n"
            "  - 'dentist every 6 months' → {'intent': 'REMIND', 'data': {'item': 'dentist appointment', 'timestamp': '[6 months from now]', 'recurrence': 'monthly', 'interval': 6}}\n\n"
            
            "** DELETE_REMINDERS (Remove Scheduled Reminders) **\n"
            "Triggers: 'delete/remove/cancel reminder', 'delete/cancel [appointment/meeting/class]'\n"
            "IMPORTANT: Use this ONLY for scheduled events/reminders, NOT physical items.\n"
            "Structure: {'intent': 'DELETE_REMINDERS', 'data': {'item': 'music class on Wednesday'}}\n"
            "Examples:\n"
            "  - 'delete music class on Wednesday' → {'intent': 'DELETE_REMINDERS', 'data': {'item': 'music class on Wednesday'}}\n"
            "  - 'delete all music class' → {'intent': 'DELETE_REMINDERS', 'data': {'item': 'music class'}}\n"
            "  - 'cancel dentist appointment' → {'intent': 'DELETE_REMINDERS', 'data': {'item': 'dentist'}}\n"
            "  - 'remove meet neha' → {'intent': 'DELETE_REMINDERS', 'data': {'item': 'meet neha'}}\n\n"
            
            "** UPDATE_REMINDER (Change Reminder Time) **\n"
            "Triggers: 'change', 'update', 'reschedule', 'move' (when referring to time/appointment)\n"
            "Structure: {'intent': 'UPDATE_REMINDER', 'data': {'item': 'music class', 'new_timestamp': '2026-01-28 18:00:00'}}\n"
            "Examples:\n"
            "  - 'change music class to 6pm' → {'intent': 'UPDATE_REMINDER', 'data': {'item': 'music class', 'new_timestamp': '2026-01-28 18:00:00'}}\n"
            "  - 'reschedule dentist to tomorrow 2pm' → Calculate tomorrow + 14:00\n"
            "  - 'move meeting to 4pm' → {'intent': 'UPDATE_REMINDER', 'data': {'item': 'meeting', 'new_timestamp': '[calculated timestamp]'}}\n\n"
            
            "** LIST (Show Shopping List) **\n"
            "Triggers: 'list', 'show vault', 'show list', 'what do I need'\n"
            "IMPORTANT: This is for SHOPPING LIST items (groceries, physical items), NOT reminders/appointments.\n"
            "Structure: {'intent': 'LIST', 'data': {'store': 'All'}} or specific store\n"
            "Examples:\n"
            "  - 'list' → {'intent': 'LIST', 'data': {'store': 'All'}}\n"
            "  - 'show vault' → {'intent': 'LIST', 'data': {'store': 'All'}}\n"
            "  - 'list Safeway' → {'intent': 'LIST', 'data': {'store': 'Safeway'}}\n\n"
            
            "** LIST_REMINDERS (Show Scheduled Reminders) **\n"
            "Triggers: 'list reminders', 'show reminders', 'my reminders', 'upcoming reminders', 'plans', 'schedule', 'calendar', 'what do I have', \"what's on\"\n"
            "IMPORTANT: This is for TIME-BASED reminders/appointments/meetings, NOT shopping items.\n"
            "Date Filtering:\n"
            "  - 'reminders for today' → {'date_filter': 'today'}\n"
            "  - 'reminders for tomorrow' → {'date_filter': 'tomorrow'}\n"
            "  - 'reminders for Saturday' or 'reminders on Saturday' → {'date_filter': 'Saturday'}\n"
            "  - 'reminders for January 25' or 'reminders on Jan 25' → {'date_filter': '2026-01-25'}\n"
            "  - 'my plans for this week' → {'date_filter': 'this_week'}\n"
            "  - 'what's my schedule today' → {'date_filter': 'today'}\n"
            "  - 'what do I have on Monday' → {'date_filter': 'Monday'}\n"
            "  - \"what's on my calendar this week\" → {'date_filter': 'this_week'}\n"
            "Structure: {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'today'}} or no filter for all\n"
            "Examples:\n"
            "  - 'list reminders' → {'intent': 'LIST_REMINDERS', 'data': {}}\n"
            "  - 'reminders for today' → {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'today'}}\n"
            "  - 'what are my plans tomorrow' → {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'tomorrow'}}\n"
            "  - 'show me Saturday's schedule' → {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'Saturday'}}\n"
            "  - 'what do I have on Monday' → {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'Monday'}}\n"
            "  - \"what's on my calendar this week\" → {'intent': 'LIST_REMINDERS', 'data': {'date_filter': 'this_week'}}\n\n"
            
            "** TIME (Show Current Time) **\n"
            "Triggers: 'what time', 'current time', 'time now', 'what's the time'\n"
            "Structure: {'intent': 'TIME', 'data': {}}\n\n"
            
            "** CHAT (General Conversation) **\n"
            "Any message that doesn't match above patterns.\n"
            "Triggers: greetings, questions about capabilities, thank you messages, general queries\n"
            "Structure: {'intent': 'CHAT', 'data': {'answer': 'Your helpful response'}}\n"
            "Examples:\n"
            "  - 'how are you?' → {'intent': 'CHAT', 'data': {'answer': 'I'm doing well! How can I help you?'}}\n"
            "  - 'what can you do?' → {'intent': 'CHAT', 'data': {'answer': 'I can help with shopping lists and reminders. Type help for more info.'}}\n"
            "  - 'hello' → {'intent': 'CHAT', 'data': {'answer': 'Hi! How can I assist you today?'}}\n\n"
            
            "=== DISAMBIGUATION RULES ===\n"
            "1. 'delete milk' → DELETE (vault item)\n"
            "2. 'delete music class' → DELETE_REMINDERS (scheduled event)\n"
            "3. 'clear safeway' → DELETE with mode CLEAR_STORE (clear specific store)\n"
            "4. 'clear list' → DELETE with mode CLEAR_ALL (clear everything)\n"
            "5. 'move milk to Costco' → MOVE (store transfer)\n"
            "6. 'move meeting to 3pm' → UPDATE_REMINDER (time change)\n"
            "7. 'list' or 'show vault' → LIST (shopping items)\n"
            "8. 'what do I have on Monday' → LIST_REMINDERS (schedule/appointments)\n"
            "9. 'my plans for Saturday' → LIST_REMINDERS (schedule/appointments)\n"
            "10. When unclear, ask yourself: Is this a physical item (LIST) or a scheduled event (LIST_REMINDERS)?\n\n"
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
            raw = response.choices[0].message.content
            logger.info(f"🧠 BRAIN RAW: {raw}")
            
            result = json.loads(raw)
            
            # Post-process to ensure data quality
            result = self._post_process(result, current_now)
            
            return result
            
        except Exception as e:
            logger.error(f"💥 BRAIN ERROR: {e}")
            return {"intent": "UNKNOWN", "data": {}}
    
    def _post_process(self, result, current_now):
        """Post-process LLM output for consistency."""
        intent = result.get("intent")
        data = result.get("data", {})
        
        # Parse current time for calculations
        now = datetime.strptime(current_now, "%Y-%m-%d %H:%M:%S")
        
        # Ensure items are singularized and stores are capitalized
        if intent == "TASK":
            for item in data.get("items", []):
                item["name"] = self._singularize(item.get("name", ""))
                item["store"] = item.get("store", "General").capitalize()
                item["count"] = int(item.get("count", 1))
        
        elif intent == "DELETE":
            if "mode" not in data:
                data["mode"] = "ALL" if any("store" in item for item in data.get("items", [])) else "SINGLE"
            
            for item in data.get("items", []):
                item["name"] = self._singularize(item.get("name", ""))
                if "store" in item:
                    item["store"] = item["store"].capitalize()
                if "count" in item:
                    item["count"] = int(item["count"])
        
        elif intent == "MOVE":
            data["item"] = self._singularize(data.get("item", ""))
            data["from_store"] = data.get("from_store", "General").capitalize()
            data["to_store"] = data.get("to_store", "General").capitalize()
            # Default to moving all if not specified
            if "move_all" not in data:
                data["move_all"] = True
        
        elif intent == "REMIND":
            # Validate and fix timestamp if present
            if "timestamp" in data:
                data["timestamp"] = self._calculate_timestamp(data["timestamp"], now)
        
        elif intent == "UPDATE_REMINDER":
            if "new_timestamp" in data:
                data["new_timestamp"] = self._calculate_timestamp(data["new_timestamp"], now)
        
        result["data"] = data
        return result
    
    def _calculate_timestamp(self, timestamp_str, now):
        """Calculate actual timestamp from LLM output, handling placeholders."""
        # If it's already a valid timestamp, just fix midnight
        if self._is_valid_timestamp(timestamp_str):
            return self._fix_timestamp(timestamp_str, "")
        
        # Handle placeholder patterns like "[next Saturday] 16:00:00"
        # Extract time from patterns like "[next Saturday] 16:00:00"
        time_match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})$', timestamp_str)
        if not time_match:
            # No time found, default to 9 AM
            hour, minute, second = 9, 0, 0
        else:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3))
        
        # Calculate date based on placeholder
        if 'tomorrow' in timestamp_str.lower():
            target_date = now + timedelta(days=1)
        elif 'today' in timestamp_str.lower():
            target_date = now
        elif 'monday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 0)  # Monday = 0
        elif 'tuesday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 1)
        elif 'wednesday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 2)
        elif 'thursday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 3)
        elif 'friday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 4)
        elif 'saturday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 5)
        elif 'sunday' in timestamp_str.lower():
            target_date = self._next_weekday(now, 6)
        else:
            # Default to tomorrow if can't parse
            target_date = now + timedelta(days=1)
        
        # Combine date and time
        result = target_date.replace(hour=hour, minute=minute, second=second)
        return result.strftime("%Y-%m-%d %H:%M:%S")
    
    def _next_weekday(self, current_date, target_weekday):
        """Calculate next occurrence of a weekday (0=Monday, 6=Sunday)."""
        days_ahead = target_weekday - current_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return current_date + timedelta(days=days_ahead)
    
    def _is_valid_timestamp(self, timestamp_str):
        """Check if string is a valid timestamp format."""
        try:
            datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return True
        except:
            return False
    
    def _fix_timestamp(self, timestamp_str, current_now):
        """Fix timestamp to avoid midnight defaults when no time specified."""
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            # If time is midnight (00:00:00), likely LLM didn't specify time
            # Change to 9 AM for better UX
            if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                dt = dt.replace(hour=9)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            # If parsing fails, return as-is and let _calculate_timestamp handle it
            return timestamp_str
    
    def _singularize(self, word):
        """Simple singularization."""
        word = word.lower().strip()
        
        irregulars = {
            "children": "child", "people": "person", "teeth": "tooth",
            "feet": "foot", "mice": "mouse", "geese": "goose"
        }
        
        if word in irregulars:
            return irregulars[word]
        
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        elif word.endswith("es") and len(word) > 3:
            if word.endswith(("shes", "ches", "sses", "xes", "zes")):
                return word[:-2]
            return word[:-1]
        elif word.endswith("s") and len(word) > 2:
            return word[:-1]
        
        return word