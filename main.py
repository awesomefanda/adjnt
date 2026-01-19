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
            "✅ *Add:* 'Add 3 apples to Pantry'\n"
            "📋 *List:* 'Show my vault'\n"
            "🚚 *Move:* 'Move apple from General to Safeway'\n"
            "⏰ *Remind:* 'Remind me in 10 mins to check oven'\n"
            "🗑️ *Delete:* 'Delete 1 apple' or 'Clear all'")

def send_wa(to, text):
    url = f"{os.getenv('WAHA_URL', 'http://waha:3000')}/api/sendText"
    try:
        requests.post(url, json={"chatId": to, "text": text, "session": "default"})
    except Exception as e:
        logger.error(f"❌ Send failed: {e}")

async def process_adjnt(text, recipient_id):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        analysis = await brain.decide(text, now_str)
        
        # Robust intent/data parsing
        intent = analysis.get('intent', 'UNKNOWN')
        data = analysis.get('data', analysis if 'items' in analysis else {})
        response_msg = ""

        with Session(engine) as session:
            # Commit Group first for Foreign Key safety
            if not session.get(Group, recipient_id):
                session.add(Group(id=recipient_id, admin_id=recipient_id))
                session.commit()

            if intent == "TASK":
                items = data.get('items', [])
                logger.info(f"💾 LLM DECIDED TO ADD: {items}")
                added_log = []
                for item in items:
                    name, count, store = item.get('name', '').lower(), int(item.get('count', 1)), item.get('store', 'General')
                    for _ in range(count):
                        session.add(Task(description=name, group_id=recipient_id, store=store))
                    added_log.append(f"{name} (x{count})")
                session.commit()
                response_msg = f"✅ *Vaulted:* {', '.join(added_log)}."
            elif intent == "LIST":
                # 1. Get the target store, default to 'All'
                target_store = data.get('store', 'All')
                
                # 2. Start the query for this specific user/group
                statement = select(Task).where(Task.group_id == recipient_id)
                
                # 3. Apply store filter if not "All"
                if target_store.lower() != "all":
                    statement = statement.where(Task.store.ilike(target_store))
                
                tasks = session.exec(statement).all()
                
                if not tasks:
                    response_msg = f"Your vault is empty for *{target_store}*." if target_store.lower() != "all" else "Your vault is empty."
                else:
                    # Grouping items by store for display
                    grouped = {}
                    for t in tasks:
                        s_name = t.store.capitalize() if t.store else "General"
                        if s_name not in grouped:
                            grouped[s_name] = Counter()
                        grouped[s_name][t.description] += 1
                    
                    response_msg = f"📋 *Vault ({target_store}):*"
                    for s_name, counts in grouped.items():
                        response_msg += f"\n\n📍 *{s_name}*"
                        # Fixed display: - item (x2) or - item
                        items_list = [f"- {name} (x{c})" if c > 1 else f"- {name}" for name, c in counts.items()]
                        response_msg += "\n" + "\n".join(items_list)

            # elif intent == "LIST":
            #     tasks = session.exec(select(Task).where(Task.group_id == recipient_id)).all()
            #     if not tasks:
            #         response_msg = "Vault is empty."
            #     else:
            #         grouped = {}
            #         for t in tasks:
            #             s = t.store.capitalize()
            #             if s not in grouped: grouped[s] = Counter()
            #             grouped[s][t.description] += 1
            #         response_msg = "📋 *Vault:*"
            #         for s, items in grouped.items():
            #             response_msg += f"\n\n📍 *{s}*\n" + "\n".join([f"- {k} (x{v})" if v>1 else f"- {k}" for k,v in items.items()])

            elif intent == "MOVE":
                item, f_s, t_s = data.get('item', '').lower(), data.get('from_store'), data.get('to_store')
                task = session.exec(select(Task).where(Task.group_id==recipient_id, Task.description==item, Task.store.ilike(f_s))).first()
                if task:
                    task.store = t_s
                    session.add(task)
                    session.commit()
                    response_msg = f"🚚 Moved *{item}* to {t_s}."
                else: response_msg = f"❓ No {item} in {f_s}."

            elif intent == "DELETE":
                items = data.get('items', [])
                # Some LLMs put 'mode' inside 'items', others at top of 'data'
                mode = data.get('mode', items[0].get('mode', 'SINGLE') if items else 'SINGLE')
                removed_log = []

                for item in items:
                    name = item.get('name', '').lower().strip()
                    count = int(item.get('count', 1))

                    if mode == "ALL":
                        # Delete every instance of this item for this group
                        statement = delete(Task).where(Task.group_id == recipient_id, Task.description == name)
                        session.exec(statement)
                        removed_log.append(f"all {name}s")
                    else:
                        # Delete specific number of items (limit to the count provided)
                        # We fetch the IDs first to ensure we only delete the requested amount
                        tasks = session.exec(
                            select(Task)
                            .where(Task.group_id == recipient_id, Task.description == name)
                            .limit(count)
                        ).all()
                        
                        for t in tasks:
                            session.delete(t)
                        
                        if tasks:
                            removed_log.append(f"{len(tasks)}x {name}")

                session.commit()
                if removed_log:
                    response_msg = f"🗑️ *Removed:* {', '.join(removed_log)}."
                else:
                    response_msg = "❓ I couldn't find those items in your vault."
            
            elif intent == "REMIND":
                txt, mins = data.get('item', 'Reminder'), int(data.get('minutes', 5))
                scheduler.add_job(send_wa, 'date', run_date=datetime.now()+timedelta(minutes=mins), 
                                  args=[recipient_id, f"⏰ *REMINDER:* {txt}"], id=f"rem_{os.urandom(4).hex()}")
                response_msg = f"⏰ Set for {mins} mins."

            elif intent == "CHAT": response_msg = data.get('answer', "How can I help?")
            elif intent == "ONBOARD": response_msg = get_guide()
            else: response_msg = "🤔 Not sure what you mean. Try 'Add milk' or 'Help'."

        if response_msg:
            send_wa(recipient_id, response_msg)
    except Exception as e:
        logger.error(f"❌ Process Error: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    data = await request.json()
    payload = data.get('payload', {})
    msg_id = payload.get('id')

    # 🛡️ FIX: Ignore if we already processed this exact message ID
    if msg_id in processed_ids:
        return {"status": "duplicate_ignored"}

    if not payload.get('fromMe') and payload.get('body'):
        processed_ids.add(msg_id)
        # Keep the tracker from growing forever
        if len(processed_ids) > 500:
            processed_ids.clear() 
            
        bg.add_task(process_adjnt, payload.get('body'), payload.get('from'))
    
    return {"status": "ok"}