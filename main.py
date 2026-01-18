import os
import requests
import logging
import json
import re
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from collections import Counter
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, delete
from database import init_db, engine
from models import Task
from brain import AdjntBrain
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Adjnt")

processed_ids = set()
db_url = os.getenv("DATABASE_URL", "sqlite:///adjnt_vault.db")
jobstores = {'default': SQLAlchemyJobStore(url=db_url)}
scheduler = BackgroundScheduler(jobstores=jobstores)

def get_guide():
    return (
        "🤖 *Adjnt Quick Start Guide*\n\n"
        "I'm your Alexa-style assistant. Try these:\n"
        "✅ *Add:* 'Add milk, eggs and bread'\n"
        "📋 *View:* 'Show my vault'\n"
        "⏰ *Remind:* 'Remind me to check the oven in 10 mins'\n"
        "🗑️ *Delete:* 'Delete milk' or 'Clear the entire list'\n"
        "💬 *Ask:* 'How do I fix a leaky faucet?'\n\n"
        "Type *ONBOARD* anytime to see this!"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    logger.info("🚀 ADJNT SYSTEM ONLINE")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
brain = AdjntBrain()

def send_wa(to, text):
    url = f"{os.getenv('WAHA_URL', 'http://waha:3000')}/api/sendText"
    payload = {"chatId": to, "text": text, "session": "default"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"❌ Send failed: {e}")

async def process_adjnt(text, recipient_id):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        analysis = await brain.decide(text, now_str)
        intent = analysis.get('intent', 'CHAT')
        data = analysis.get('data', {})

        with Session(engine) as session:
            # 1. TASK: Handles single or multiple items via AI-generated list
            if intent == "TASK":
                items_to_add = data.get('items', [])
                # This prevents the code from processing the same item twice in one message
                for item_name in set(items_to_add): 
                    session.add(Task(description=item_name.strip(), group_id=recipient_id))
                session.commit()
                send_wa(recipient_id, f"✅ Added {len(set(items_to_add))} items.")

            # 2. DELETE: Smart Removal
            elif intent == "DELETE" or intent == "DELETE_TASK":
                items_to_del = data.get('items', [])
                mode = data.get('mode', 'SINGLE')
                
                # Check if we are clearing the whole vault
                if any(x in [i.lower() for i in items_to_del] for x in ["everything", "the list", "all"]):
                    session.exec(delete(Task).where(Task.group_id == recipient_id))
                    msg = "🧹 Vault cleared!"
                else:
                    for item_name in items_to_del:
                        # Look for one instance to remove
                        statement = select(Task).where(Task.group_id == recipient_id, Task.description.ilike(item_name))
                        task = session.exec(statement).first()
                        if task:
                            session.delete(task)
                            msg = f"🗑️ Removed: {item_name}"
                        else:
                            msg = f"❓ Couldn't find '{item_name}'."
                
                session.commit()
                send_wa(recipient_id, msg)

            # 3. LIST: Show items with counts
            elif intent == "LIST":
                tasks = session.exec(select(Task).where(Task.group_id == recipient_id)).all()
                if not tasks:
                    send_wa(recipient_id, "Your vault is empty.")
                else:
                    counts = Counter([t.description for t in tasks])
                    task_str = "\n".join([f"- {k} (x{v})" if v > 1 else f"- {k}" for k, v in counts.items()])
                    send_wa(recipient_id, f"📋 *Your Vault:*\n{task_str}")

            # 4. REMIND
            elif intent == "REMIND":
                item = data.get('item', 'Reminder')
                mins = data.get('minutes', 5)
                run_time = datetime.now() + timedelta(minutes=int(mins))
                job_id = f"remind_{recipient_id}_{item.replace(' ', '_')}"
                scheduler.add_job(send_wa, 'date', run_date=run_time, args=[recipient_id, f"⏰ REMINDER: {item}"], id=job_id, replace_existing=True)
                send_wa(recipient_id, f"⏰ Set for '{item}' in {mins} mins.")

            # 5. ONBOARD / HELP
            elif intent == "ONBOARD":
                send_wa(recipient_id, get_guide())

            # 6. UNKNOWN / Fallback
            elif intent == "UNKNOWN":
                send_wa(recipient_id, "🤔 I'm not sure about that action. Here's a quick guide:")
                send_wa(recipient_id, get_guide())

            # 7. CHAT
            else:
                answer = data.get('answer', "I'm here to help with your vault and reminders.")
                send_wa(recipient_id, answer)

    except Exception as e:
        logger.error(f"❌ Process Error: {e}")

@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    data = await request.json()
    payload = data.get('payload', {})
    msg_id = payload.get('id')

    if msg_id in processed_ids:
        return {"status": "duplicate_ignored"}
    
    if not payload.get('fromMe') and payload.get('body'):
        processed_ids.add(msg_id)
        if len(processed_ids) > 200: 
            # Simple way to keep the set small
            list(processed_ids).pop(0) 
        
        bg.add_task(process_adjnt, payload.get('body'), payload.get('from'))
        
    return {"status": "ok"}