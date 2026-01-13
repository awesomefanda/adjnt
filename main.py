import os
import requests
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from sqlmodel import Session
from database import init_db, engine
from models import Task
from brain import AdjntBrain
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dotenv import load_dotenv

# --- Advanced Diagnostic Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Adjnt")
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Use environment variable for DB path to ensure persistence
    db_path = os.getenv("DATABASE_URL", "sqlite:///adjnt_vault.db")
    jobstores = {'default': SQLAlchemyJobStore(url=db_path)}
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start()
    logger.info("🚀 ADJNT SYSTEM ONLINE - Waiting for messages...")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
brain = AdjntBrain()

# --- WAHA Send Function ---
def send_wa(to, text):
    # 'waha' is the service name defined in docker-compose
    waha_host = os.getenv('WAHA_URL', 'http://waha:3000')
    url = f"{waha_host}/api/sendText"
    
    payload = {
        "chatId": to,
        "text": text,
        "session": os.getenv("SESSION_NAME", "default")
    }
    try:
        logger.info(f"📤 REPLIER: Sending to {to} via {url}")
        response = requests.post(url, json=payload)
        logger.info(f"📤 REPLIER status: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ REPLIER failed: {e}")

# --- AI Logic ---
async def process_adjnt(text, recipient_id):
    try:
        analysis = await brain.decide(text)
        intent = analysis.get('intent', 'CHAT')
        data = analysis.get('data', {})
        
        if intent == "TASK":
            item = data.get('item', text)
            with Session(engine) as session:
                task = Task(description=item, group_id=recipient_id)
                session.add(task)
                session.commit()
            send_wa(recipient_id, f"✅ Vaulted: {item}")
        elif intent == "PRIVACY":
            send_wa(recipient_id, "🔐 Local storage only.")
        else:
            reply = data.get('answer', "Checking...")
            send_wa(recipient_id, reply)
    except Exception as e:
        logger.error(f"❌ Brain Error: {e}")

# --- WEBHOOK ENDPOINT ---
@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    logger.info(f"🚩 WEBHOOK: Connection received from {request.client.host}")
    try:
        raw_body = await request.body()
        data = json.loads(raw_body)
        
        event_type = data.get("event")
        payload = data.get('payload', {})

        if event_type not in ["message", "message.any"]:
            return {"status": "ignored"}

        if payload.get('fromMe'):
            logger.info("⏭️ Skipping self-message")
            return {"status": "ignored_self"}

        recipient_id = payload.get('from')
        text = payload.get('body')

        if text and recipient_id:
            logger.info(f"📩 SUCCESS: '{text}' from {recipient_id}")
            bg.add_task(process_adjnt, text, recipient_id)

        return {"status": "received"}

    except Exception as e:
        logger.error(f"❌ CRITICAL WEBHOOK ERROR: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})