import os, requests, logging, json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from collections import Counter
from fastapi import FastAPI, Request, BackgroundTasks
from sqlmodel import Session, select, delete
from database import init_db, engine
from models import Task, Group
from brain import AdjntBrain
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dotenv import load_dotenv

load_dotenv()
processed_ids = set()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Adjnt")

db_url = os.getenv("DATABASE_URL", "sqlite:///adjnt_vault.db")
scheduler = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=db_url)})
brain = AdjntBrain()

def get_guide():
    return ("🤖 *Adjnt Guide*\n\n"
            "✅ *Add:* 'Add 3 apples'\n"
            "📋 *List:* 'Show vault' or 'List reminders'\n"
            "🚚 *Move:* 'Move apple to Safeway'\n"
            "⏰ *Remind:* 'Neha Lunch Jan 24th 10:30 AM'\n"
            "🗑️ *Delete:* 'Remove 1 apple' or 'Clear list'")

def send_wa(to, text):
    url = f"{os.getenv('WAHA_URL', 'http://waha:3000')}/api/sendText"
    try:
        requests.post(url, json={"chatId": to, "text": text, "session": "default"})
    except Exception as e:
        logger.error(f"❌ Send failed: {e}")

async def process_adjnt(text, recipient_id):
    try:
        # 🛡️ Normalize ID
        recipient_id = str(recipient_id).strip()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        analysis = await brain.decide(text, now_str)
        
        intent = analysis.get('intent', 'UNKNOWN')
        data = analysis.get('data', {})
        response_msg = ""

        with Session(engine) as session:
            if not session.get(Group, recipient_id):
                session.add(Group(id=recipient_id, admin_id=recipient_id))
                session.commit()

            # --- 1. TASK (ADD) ---
            if intent == "TASK":
                items = data.get('items', [])
                if not items and data.get('item'):
                    items = [{'name': data.get('item'), 'count': data.get('count', 1), 'store': data.get('store', 'General')}]
                
                added_log = []
                for item in items:
                    name = item.get('name', '').lower().strip()
                    count = int(item.get('count', item.get('quantity', 1)))
                    store = item.get('store', 'General')

                    # Auto-Location
                    if store == "General":
                        ex = session.exec(select(Task).where(Task.group_id == recipient_id, Task.description == name)).first()
                        if ex: store = ex.store

                    for _ in range(count):
                        session.add(Task(description=name, group_id=recipient_id, store=store))
                    added_log.append(f"{name} (x{count})")
                
                session.commit()
                response_msg = f"✅ *Vaulted:* {', '.join(added_log)}."

            # --- 2. LIST VAULT ---
            elif intent == "LIST":
                target_store = data.get('store', 'All')
                statement = select(Task).where(Task.group_id == recipient_id)
                if target_store.lower() != "all":
                    statement = statement.where(Task.store.ilike(target_store))
                
                tasks = session.exec(statement).all()
                if not tasks:
                    response_msg = f"Vault is empty for *{target_store}*."
                else:
                    grouped = {}
                    for t in tasks:
                        s_name = t.store.capitalize()
                        if s_name not in grouped: grouped[s_name] = Counter()
                        grouped[s_name][t.description] += 1
                    
                    response_msg = f"📋 *Vault ({target_store}):*"
                    for s_name, counts in grouped.items():
                        response_msg += f"\n\n📍 *{s_name}*\n" + "\n".join([f"- {k} (x{v})" if v>1 else f"- {k}" for k,v in counts.items()])

            # --- 3. LIST REMINDERS ---
            elif intent == "LIST_REMINDERS":
                jobs = scheduler.get_jobs()
                rem_list = []
                for j in jobs:
                    if j.id.startswith(f"rem_{recipient_id}"):
                        time_str = j.next_run_time.strftime("%a %b %d, %I:%M %p")
                        # Extract text from job args: f"⏰ *REMINDER:* {item}"
                        msg = j.args[1].replace("⏰ *REMINDER:* ", "")
                        rem_list.append(f"🔔 {msg} ({time_str})")
                
                response_msg = "🗓️ *Upcoming Reminders:*\n\n" + "\n".join(rem_list) if rem_list else "No active reminders."

            # --- 4. DELETE / CLEAR ---
            # --- UPDATED DELETE BLOCK ---
            elif intent == "DELETE":
                mode = data.get('mode', 'SINGLE')
                # 🛡️ Defense: Handle both 'items' list and singular 'item'
                items = data.get('items', [])
                if not items and data.get('item'):
                    items = [{'name': data.get('item'), 'count': data.get('count', 1), 'store': data.get('store')}]

                # 🚀 SPECIAL CASE: If user tries to "delete" a reminder via DELETE intent
                if items and any("meet" in i.get('name', '').lower() for i in items):
                    intent = "DELETE_REMINDERS" # Re-route to scheduler logic
                
                if mode == "CLEAR_ALL":
                    all_tasks = session.exec(select(Task).where(Task.group_id == recipient_id)).all()
                    for t in all_tasks: session.delete(t)
                    session.commit()
                    response_msg = "🧹 Vault cleared."
                elif intent == "DELETE": # Proceed if not re-routed
                    removed = []
                    for item in items:
                        name = item.get('name', '').lower().strip()
                        stmt = select(Task).where(Task.group_id == recipient_id, Task.description == name)
                        # Filter by store if specified
                        if item.get('store'): stmt = stmt.where(Task.store.ilike(item.get('store')))
                        
                        tasks = session.exec(stmt.limit(int(item.get('count', 1))) if mode == 'SINGLE' else stmt).all()
                        for t in tasks: session.delete(t)
                        if tasks: removed.append(f"{name} (x{len(tasks)})")
                    session.commit()
                    response_msg = f"🗑️ Removed: {', '.join(removed)}" if removed else "❓ Not found in vault."

            # --- UPDATED DELETE_REMINDERS BLOCK ---
            if intent == "DELETE_REMINDERS":
                item_to_remove = data.get('item', '').lower()
                jobs = scheduler.get_jobs()
                removed_count = 0
                for job in jobs:
                    # Match by recipient AND search for the task name in the message
                    if job.id.startswith(f"rem_{recipient_id}"):
                        if not item_to_remove or item_to_remove in job.args[1].lower():
                            scheduler.remove_job(job.id)
                            removed_count += 1
                response_msg = f"🗑️ Deleted {removed_count} reminders."
            # --- 5. REMIND ---
            elif intent == "REMIND":
                item = data.get('item', 'Reminder')
                ts, mins = data.get('timestamp'), data.get('minutes')
                run_time = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") if ts else datetime.now() + timedelta(minutes=int(mins or 5))
                
                scheduler.add_job(send_wa, 'date', run_date=run_time, args=[recipient_id, f"⏰ *REMINDER:* {item}"], 
                                  id=f"rem_{recipient_id}_{run_time.timestamp()}")
                response_msg = f"🗓️ Scheduled: '{item}' for {run_time.strftime('%a %I:%M %p')}."

            elif intent == "MOVE":
                item_name, f_s, t_s = data.get('item', '').lower(), data.get('from_store', 'General'), data.get('to_store', 'General')
                task = session.exec(select(Task).where(Task.group_id==recipient_id, Task.description==item_name, Task.store.ilike(f_s))).first()
                if task:
                    task.store = t_s
                    session.add(task); session.commit()
                    response_msg = f"🚚 Moved *{item_name}* to {t_s}."

            elif intent == "CHAT": response_msg = data.get('answer')
            elif intent == "ONBOARD": response_msg = get_guide()

        if response_msg: send_wa(recipient_id, response_msg)
    except Exception as e:
        logger.error(f"❌ Process Error: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    data = await request.json()
    payload = data.get('payload', {})
    msg_id = payload.get('id')
    if msg_id in processed_ids: return {"status": "duplicate_ignored"}
    
    if not payload.get('fromMe') and payload.get('body'):
        processed_ids.add(msg_id)
        # Keep consistent ID normalization
        clean_id = str(payload.get('from', '')).strip()
        bg.add_task(process_adjnt, payload.get('body'), clean_id)
    
    return {"status": "ok"}