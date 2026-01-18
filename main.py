import os
import requests
import logging
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
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

# Deduplication and Scheduler Setup
processed_ids = set()
db_url = os.getenv("DATABASE_URL", "sqlite:///adjnt_vault.db")
jobstores = {'default': SQLAlchemyJobStore(url=db_url)}
scheduler = BackgroundScheduler(jobstores=jobstores)

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
        analysis = await brain.decide(text)
        intent = analysis.get('intent', 'CHAT')
        data = analysis.get('data', {})

        with Session(engine) as session:
            # 1. TASK: Add unique item
            if intent == "TASK":
                item = data.get('item', text).strip()
                existing = session.exec(select(Task).where(Task.group_id == recipient_id, Task.description.ilike(item))).first()
                if existing:
                    send_wa(recipient_id, f"💡 '{item}' is already in your list.")
                else:
                    session.add(Task(description=item, group_id=recipient_id))
                    session.commit()
                    send_wa(recipient_id, f"✅ Vaulted: {item}")

            # 2. DELETE: Remove specific item
            elif intent == "DELETE_TASK":
                item = data.get('item', "").strip()
                task = session.exec(select(Task).where(Task.group_id == recipient_id, Task.description.ilike(item))).first()
                if task:
                    session.delete(task)
                    session.commit()
                    send_wa(recipient_id, f"🗑️ Removed: {task.description}")
                else:
                    send_wa(recipient_id, f"❓ Couldn't find '{item}' in your list.")

            # 3. LIST: Show items
            elif intent == "LIST":
                tasks = session.exec(select(Task).where(Task.group_id == recipient_id)).all()
                reply = "📋 *Your Vault:*\n" + "\n".join([f"- {t.description}" for t in tasks]) if tasks else "Your list is empty."
                send_wa(recipient_id, reply)

            # 4. CLEAR: Wipe list
            elif intent == "CLEAR_TASKS":
                session.exec(delete(Task).where(Task.group_id == recipient_id))
                session.commit()
                send_wa(recipient_id, "🧹 Vault cleared!")

            # 5. REMIND: Set or Update reminder
            elif intent == "REMIND":
                item = data.get('item', 'Reminder')
                mins = data.get('minutes', 5)
                job_id = f"remind_{recipient_id}_{item.replace(' ', '_')}"
                run_time = datetime.now() + timedelta(minutes=mins)
                scheduler.add_job(send_wa, 'date', run_date=run_time, args=[recipient_id, f"⏰ REMINDER: {item}"], id=job_id, replace_existing=True)
                send_wa(recipient_id, f"⏰ Set for '{item}' in {mins} minutes.")

            # 6. REMOVE REMINDER
            elif intent == "REMOVE_REMINDER":
                item = data.get('item', '')
                job_id = f"remind_{recipient_id}_{item.replace(' ', '_')}"
                try:
                    scheduler.remove_job(job_id)
                    send_wa(recipient_id, f"🚫 Cancelled reminder: {item}")
                except:
                    send_wa(recipient_id, "❓ Reminder not found.")

            # 7. CHAT
            else:
                send_wa(recipient_id, data.get('answer', "I'm here to help with your list and reminders."))

    except Exception as e:
        logger.error(f"❌ Process Error: {e}")

@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    try:
        data = await request.json()
        payload = data.get('payload', {})
        msg_id = payload.get('id')

        # Deduplication Logic
        if msg_id in processed_ids:
            return {"status": "duplicate_ignored"}
        
        if not payload.get('fromMe') and payload.get('body'):
            processed_ids.add(msg_id)
            if len(processed_ids) > 200: processed_ids.pop()
            bg.add_task(process_adjnt, payload.get('body'), payload.get('from'))
            
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})