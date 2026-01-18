import os
import requests
import logging
import json
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
        "✅ *Add:* 'Add milk' or 'Stash my keys'\n"
        "📋 *View:* 'Show my vault'\n"
        "⏰ *Alerts:* 'Remind me to pick up cake in 10 mins'\n"
        "🗑️ *Delete:* 'Delete milk' (removes 1) or 'Clear the list' (wipes all)\n"
        "💬 *Ask:* 'How do I cook salmon?'\n\n"
        "Type *ONBOARD* for this menu!"
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
            # 1. TASK: Add item (Allows duplicates)
            if intent == "TASK":
                item = data.get('item', text).strip()
                session.add(Task(description=item, group_id=recipient_id))
                session.commit()
                send_wa(recipient_id, f"✅ Vaulted: {item}")

            # 2. DELETE: Smart Removal (One, All, or Everything)
            elif intent == "DELETE":
                item_name = data.get('item', "").lower().strip()
                mode = data.get('mode', 'SINGLE')
                
                # Logic for "Clear the list" or "the list"
                if "the list" in item_name or "everything" in item_name or item_name == "EVERYTHING":
                    session.exec(delete(Task).where(Task.group_id == recipient_id))
                    msg = "🧹 Vault cleared!"
                elif mode == "ALL":
                    session.exec(delete(Task).where(Task.group_id == recipient_id, Task.description.ilike(item_name)))
                    msg = f"🧹 Cleared all {item_name}."
                else:
                    # Remove only one instance (Reduce count)
                    task = session.exec(select(Task).where(Task.group_id == recipient_id, Task.description.ilike(item_name))).first()
                    if task:
                        session.delete(task)
                        msg = f"🗑️ Removed 1x {item_name}."
                    else:
                        msg = f"❓ Couldn't find '{item_name}'."
                session.commit()
                send_wa(recipient_id, msg)

            # 3. LIST: Show items with Count
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

            # 6. UNKNOWN (Fallback with examples)
            elif intent == "UNKNOWN":
                send_wa(recipient_id, "🤔 I'm not sure how to do that. Here is what I can understand:")
                send_wa(recipient_id, get_guide())

            # 7. CHAT
            else:
                send_wa(recipient_id, data.get('answer', "I'm here to help!"))

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
        if len(processed_ids) > 200: processed_ids.pop()
        bg.add_task(process_adjnt, payload.get('body'), payload.get('from'))
        
    return {"status": "ok"}