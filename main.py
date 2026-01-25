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
import pytz

load_dotenv()
processed_ids = set()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Adjnt")

# Timezone configuration
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")  # Default to PST/PDT
tz = pytz.timezone(TIMEZONE)

db_url = os.getenv("DATABASE_URL", "sqlite:///adjnt_vault.db")
scheduler = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=db_url)})
brain = AdjntBrain()

def get_guide():
    tz_name = TIMEZONE.replace("_", " ")  # Make timezone readable
    return ("🤖 *Adjnt Guide*\n\n"
            "📦 *SHOPPING LIST*\n"
            "✅ Add: 'Add 3 apples to Costco'\n"
            "📋 List: 'Show vault' or 'List Safeway'\n"
            "🚚 Move: 'Move apple to Safeway'\n"
            "🗑️ Delete: 'Remove 2 milk' or 'Clear Safeway'\n\n"
            "⏰ *REMINDERS*\n"
            "🔔 One-time: 'Lunch tomorrow 12:30 PM'\n"
            "🔁 Daily: 'Standup every day at 9am'\n"
            "🔁 Weekly: 'Meeting every Monday at 2pm'\n"
            "🔁 Monthly: 'Pay rent every month'\n"
            "📅 View: 'Reminders for today' or 'Plans tomorrow'\n"
            "🔄 Update: 'Change dentist to 3pm'\n"
            "🗑️ Delete: 'Delete meeting reminder'\n\n"
            "🕐 *OTHER*\n"
            "⏱️ Time: 'What time is it?'\n"
            f"🌍 Timezone: {tz_name}")

def send_wa(to, text):
    url = f"{os.getenv('WAHA_URL', 'http://waha:3000')}/api/sendText"
    try:
        requests.post(url, json={"chatId": to, "text": text, "session": "default"})
    except Exception as e:
        logger.error(f"❌ Send failed: {e}")

async def process_adjnt(text, recipient_id):
    logger.info(f"🔥 PROCESS_ADJNT STARTED: text='{text}', id='{recipient_id}'") # <--- ADD THIS
    try:
        # 🛡️ Normalize ID
        recipient_id = str(recipient_id).strip()
        
        # Get current time in configured timezone
        now = datetime.now(tz)
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
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
                date_filter = data.get('date_filter')
                
                # Parse date filter
                filter_date = None
                if date_filter:
                    if date_filter == 'today':
                        filter_date = now.date()
                    elif date_filter == 'tomorrow':
                        filter_date = (now + timedelta(days=1)).date()
                    elif date_filter == 'this_week':
                        # Show reminders for the rest of this week
                        filter_date = 'week'
                    elif date_filter in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                        # Find next occurrence of this day
                        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        target_idx = days.index(date_filter)
                        current_idx = now.weekday()
                        days_ahead = (target_idx - current_idx) % 7
                        if days_ahead == 0:
                            days_ahead = 7
                        filter_date = (now + timedelta(days=days_ahead)).date()
                    else:
                        # Try parsing as date string (e.g., "2026-01-25")
                        try:
                            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
                        except:
                            pass
                
                rem_list = []
                for j in jobs:
                    if j.id.startswith(f"rem_{recipient_id}"):
                        # Convert to timezone-aware time
                        next_run = j.next_run_time
                        if next_run.tzinfo is None:
                            next_run = tz.localize(next_run)
                        else:
                            next_run = next_run.astimezone(tz)
                        
                        # Apply date filter
                        if filter_date:
                            if filter_date == 'week':
                                # Check if within this week
                                week_end = now + timedelta(days=(6 - now.weekday()))
                                if next_run.date() > week_end.date():
                                    continue
                            elif next_run.date() != filter_date:
                                continue
                        
                        time_str = next_run.strftime("%a %b %d, %I:%M %p %Z")
                        msg = j.args[1].replace("⏰ *REMINDER:* ", "")
                        
                        # Check if recurring
                        if hasattr(j.trigger, 'interval'):
                            rem_list.append(f"🔁 {msg} ({time_str}) - Recurring")
                        else:
                            rem_list.append(f"🔔 {msg} ({time_str})")
                
                if date_filter:
                    filter_text = date_filter.replace('_', ' ').title()
                    response_msg = f"🗓️ *Reminders for {filter_text}:*\n\n" + "\n".join(rem_list) if rem_list else f"No reminders for {filter_text}."
                else:
                    response_msg = "🗓️ *Upcoming Reminders:*\n\n" + "\n".join(rem_list) if rem_list else "No active reminders."

            # --- 4. DELETE ---
            elif intent == "DELETE":
                mode = data.get('mode', 'SINGLE')
                items = data.get('items', [])
                if not items and data.get('item'):
                    items = [{'name': data.get('item'), 'count': data.get('count', 1), 'store': data.get('store')}]
                
                if mode == "CLEAR_ALL":
                    all_tasks = session.exec(select(Task).where(Task.group_id == recipient_id)).all()
                    for t in all_tasks: session.delete(t)
                    session.commit()
                    response_msg = "🧹 Vault cleared."
                elif mode == "CLEAR_STORE":
                    # Clear specific store only
                    store_to_clear = data.get('store', '').capitalize()
                    store_tasks = session.exec(
                        select(Task).where(
                            Task.group_id == recipient_id,
                            Task.store.ilike(store_to_clear)
                        )
                    ).all()
                    for t in store_tasks: session.delete(t)
                    session.commit()
                    response_msg = f"🧹 Cleared all items from {store_to_clear}."
                else:
                    removed = []
                    for item in items:
                        name = item.get('name', '').lower().strip()
                        stmt = select(Task).where(Task.group_id == recipient_id, Task.description == name)
                        if item.get('store'): 
                            stmt = stmt.where(Task.store.ilike(item.get('store')))
                        
                        tasks = session.exec(stmt.limit(int(item.get('count', 1))) if mode == 'SINGLE' else stmt).all()
                        for t in tasks: session.delete(t)
                        if tasks: removed.append(f"{name} (x{len(tasks)})")
                    session.commit()
                    response_msg = f"🗑️ Removed: {', '.join(removed)}" if removed else "❓ Not found in vault."

            # --- 5. DELETE_REMINDERS ---
            elif intent == "DELETE_REMINDERS":
                item_to_remove = data.get('item', '').lower()
                jobs = scheduler.get_jobs()
                removed_count = 0
                removed_names = []
                
                for job in jobs:
                    if job.id.startswith(f"rem_{recipient_id}"):
                        job_msg = job.args[1].replace("⏰ *REMINDER:* ", "").lower()
                        # Match if item_to_remove is substring or no filter specified
                        if not item_to_remove or item_to_remove in job_msg:
                            removed_names.append(job.args[1].replace("⏰ *REMINDER:* ", ""))
                            scheduler.remove_job(job.id)
                            removed_count += 1
                
                if removed_count > 0:
                    response_msg = f"🗑️ Deleted {removed_count} reminder(s): {', '.join(removed_names[:3])}"
                else:
                    response_msg = f"❓ No reminders found matching '{item_to_remove}'"

            # --- 6. REMIND ---
            elif intent == "REMIND":
                item = data.get('item', 'Reminder')
                ts, mins = data.get('timestamp'), data.get('minutes')
                recurrence = data.get('recurrence')
                day_of_week = data.get('day_of_week')
                interval = data.get('interval', 1)
                
                # Calculate run time in timezone
                if ts:
                    run_time = tz.localize(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))
                else:
                    run_time = now + timedelta(minutes=int(mins or 5))
                
                # Handle recurring reminders
                if recurrence:
                    job_id = f"rem_{recipient_id}_{item.replace(' ', '_')}_{run_time.timestamp()}"
                    
                    if recurrence == 'daily':
                        scheduler.add_job(
                            send_wa,
                            'interval',
                            days=1,
                            start_date=run_time,
                            args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                            id=job_id
                        )
                        response_msg = f"🔁 Recurring reminder set: '{item}' daily at {run_time.strftime('%I:%M %p %Z')}."
                    
                    elif recurrence == 'weekly':
                        if day_of_week:
                            # Specific day of week
                            days_map = {'Monday': 'mon', 'Tuesday': 'tue', 'Wednesday': 'wed', 
                                       'Thursday': 'thu', 'Friday': 'fri', 'Saturday': 'sat', 'Sunday': 'sun'}
                            scheduler.add_job(
                                send_wa,
                                'cron',
                                day_of_week=days_map.get(day_of_week, 'mon'),
                                hour=run_time.hour,
                                minute=run_time.minute,
                                timezone=tz,  # Important: specify timezone for cron jobs
                                args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                                id=job_id
                            )
                            response_msg = f"🔁 Recurring reminder set: '{item}' every {day_of_week} at {run_time.strftime('%I:%M %p %Z')}."
                        else:
                            # Just weekly
                            scheduler.add_job(
                                send_wa,
                                'interval',
                                weeks=1,
                                start_date=run_time,
                                args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                                id=job_id
                            )
                            response_msg = f"🔁 Recurring reminder set: '{item}' weekly starting {run_time.strftime('%a %b %d, %I:%M %p %Z')}."
                    
                    elif recurrence == 'weekdays':
                        scheduler.add_job(
                            send_wa,
                            'cron',
                            day_of_week='mon-fri',
                            hour=run_time.hour,
                            minute=run_time.minute,
                            timezone=tz,  # Important: specify timezone for cron jobs
                            args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                            id=job_id
                        )
                        response_msg = f"🔁 Recurring reminder set: '{item}' every weekday at {run_time.strftime('%I:%M %p %Z')}."
                    
                    elif recurrence == 'weekend':
                        scheduler.add_job(
                            send_wa,
                            'cron',
                            day_of_week='sat,sun',
                            hour=run_time.hour,
                            minute=run_time.minute,
                            timezone=tz,  # Important: specify timezone for cron jobs
                            args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                            id=job_id
                        )
                        response_msg = f"🔁 Recurring reminder set: '{item}' every weekend at {run_time.strftime('%I:%M %p %Z')}."
                    
                    elif recurrence == 'monthly':
                        scheduler.add_job(
                            send_wa,
                            'interval',
                            months=interval,
                            start_date=run_time,
                            args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                            id=job_id
                        )
                        freq_text = "monthly" if interval == 1 else f"every {interval} months"
                        response_msg = f"🔁 Recurring reminder set: '{item}' {freq_text} starting {run_time.strftime('%a %b %d, %I:%M %p %Z')}."
                    
                    elif recurrence == 'yearly':
                        scheduler.add_job(
                            send_wa,
                            'interval',
                            years=1,
                            start_date=run_time,
                            args=[recipient_id, f"⏰ *REMINDER:* {item}"],
                            id=job_id
                        )
                        response_msg = f"🔁 Recurring reminder set: '{item}' yearly on {run_time.strftime('%b %d at %I:%M %p %Z')}."
                
                else:
                    # One-time reminder
                    scheduler.add_job(
                        send_wa, 
                        'date', 
                        run_date=run_time, 
                        args=[recipient_id, f"⏰ *REMINDER:* {item}"], 
                        id=f"rem_{recipient_id}_{run_time.timestamp()}"
                    )
                    
                    # Format time nicely with timezone
                    time_str = run_time.strftime('%a %b %d, %I:%M %p')
                    tz_abbr = run_time.strftime('%Z')  # e.g., PST, PDT
                    response_msg = f"🗓️ Scheduled: '{item}' for {time_str} {tz_abbr}."

            # --- 7. UPDATE_REMINDER (NEW) ---
            elif intent == "UPDATE_REMINDER":
                item_search = data.get('item', '').lower()
                new_timestamp = data.get('new_timestamp')
                
                if not new_timestamp:
                    response_msg = "❌ No new time specified."
                else:
                    try:
                        new_time = tz.localize(datetime.strptime(new_timestamp, "%Y-%m-%d %H:%M:%S"))
                        jobs = scheduler.get_jobs()
                        updated = False
                        
                        for job in jobs:
                            if job.id.startswith(f"rem_{recipient_id}"):
                                job_msg = job.args[1].replace("⏰ *REMINDER:* ", "")
                                if item_search in job_msg.lower():
                                    # Remove old job and create new one
                                    scheduler.remove_job(job.id)
                                    scheduler.add_job(
                                        send_wa,
                                        'date',
                                        run_date=new_time,
                                        args=[recipient_id, f"⏰ *REMINDER:* {job_msg}"],
                                        id=f"rem_{recipient_id}_{new_time.timestamp()}"
                                    )
                                    time_str = new_time.strftime('%a %b %d, %I:%M %p')
                                    tz_abbr = new_time.strftime('%Z')
                                    response_msg = f"🔄 Updated '{job_msg}' to {time_str} {tz_abbr}."
                                    updated = True
                                    break
                        
                        if not updated:
                            response_msg = f"❓ No reminder found matching '{item_search}'"
                    
                    except ValueError:
                        response_msg = "❌ Invalid time format."

            # --- 8. MOVE ---
            elif intent == "MOVE":
                item_name = data.get('item', '').lower()
                f_s = data.get('from_store', 'General')
                t_s = data.get('to_store', 'General')
                move_all = data.get('move_all', True)  # Default to moving all
                
                tasks = session.exec(
                    select(Task).where(
                        Task.group_id == recipient_id, 
                        Task.description == item_name, 
                        Task.store.ilike(f_s)
                    )
                ).all()
                
                if tasks:
                    moved_count = len(tasks)
                    for task in tasks:
                        task.store = t_s
                        session.add(task)
                    session.commit()
                    response_msg = f"🚚 Moved {moved_count} {item_name}(s) from {f_s} to {t_s}."
                else:
                    response_msg = f"❓ No {item_name} found in {f_s}."

            # --- 9. CHAT ---
            elif intent == "CHAT": 
                response_msg = data.get('answer', "I'm here to help! Try 'help' for commands.")
            
            # --- 10. ONBOARD ---
            elif intent == "ONBOARD": 
                response_msg = get_guide()
            
            # --- 11. UNKNOWN ---
            else:
                response_msg = "🤔 I didn't understand that. Try 'help' for guidance."

        if response_msg: 
            send_wa(recipient_id, response_msg)
            logger.info(f"✅ Response sent to {recipient_id}: {response_msg}")
    
    except Exception as e:
        logger.error(f"❌ Process Error: {e}", exc_info=True)
        send_wa(recipient_id, "❌ Sorry, something went wrong. Please try again.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    logger.info("🚀 Adjnt started successfully")
    yield
    scheduler.shutdown()
    logger.info("🛑 Adjnt shutdown")

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks):
    data = await request.json()
    payload = data.get('payload', {})
    msg_id = payload.get('id')
    
    if msg_id in processed_ids: 
        return {"status": "duplicate_ignored"}
    
    if not payload.get('fromMe') and payload.get('body'):
        processed_ids.add(msg_id)
        clean_id = str(payload.get('from', '')).strip()
        bg.add_task(process_adjnt, payload.get('body'), clean_id)
    
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "reminders": len(scheduler.get_jobs())}