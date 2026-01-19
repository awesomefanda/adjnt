import os
import pytest
import asyncio

# 🚀 Force test database environment
os.environ["DATABASE_URL"] = "sqlite:///test_adjnt.db"

from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, select, func, SQLModel
from database import engine
from main import app, scheduler, processed_ids
from models import Task

@pytest.fixture(autouse=True)
def setup_db():
    """Wipes everything for a clean test run."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    processed_ids.clear()
    scheduler.remove_all_jobs()
    yield
    if os.path.exists("test_adjnt.db"):
        os.remove("test_adjnt.db")

@pytest.mark.asyncio
async def test_complete_feature_suite():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        uid = "test_user@c.us"

        # --- 1. STORE & MATH TEST ---
        # Add 1 apple to General, then 2 more to Safeway
        await ac.post("/webhook", json={"payload": {"id": "t1", "from": uid, "body": "add 1 apple", "fromMe": False}})
        await asyncio.sleep(2) 
        await ac.post("/webhook", json={"payload": {"id": "t2", "from": uid, "body": "add 2 more apples to Safeway", "fromMe": False}})
        await asyncio.sleep(2)

        # --- 2. DUPLICATE GUARD TEST ---
        # Resending t2 (should be ignored)
        await ac.post("/webhook", json={"payload": {"id": "t2", "from": uid, "body": "add 2 more apples to Safeway", "fromMe": False}})
        await asyncio.sleep(1)

        # --- 3. DELETE TEST ---
        # Removing the 1 apple from General
        await ac.post("/webhook", json={"payload": {"id": "t3", "from": uid, "body": "delete 1 apple", "fromMe": False}})
        await asyncio.sleep(2)

        # --- 4. REMINDER TEST ---
        await ac.post("/webhook", json={"payload": {"id": "t4", "from": uid, "body": "remind me in 10 mins to buy milk", "fromMe": False}})

        # --- VERIFICATION POLLING ---
        print("\n🔍 Verifying all features...")
        for i in range(15):
            await asyncio.sleep(1)
            with Session(engine) as s:
                # We expect 0 apples in General (added 1, deleted 1)
                # We expect 2 apples in Safeway
                total_apples = s.exec(select(func.count(Task.id)).where(Task.description == "apple")).one()
                safeway_apples = s.exec(select(func.count(Task.id)).where(Task.description == "apple", Task.store == "Safeway")).one()
                
            jobs = scheduler.get_jobs()
            reminder_ok = any("buy milk" in str(j.args) for j in jobs)

            print(f"Attempt {i+1}: Total Apples: {total_apples}, Safeway: {safeway_apples}, Reminder: {reminder_ok}")

            if total_apples == 2 and safeway_apples == 2 and reminder_ok:
                break
            
            if total_apples > 3:
                pytest.fail(f"❌ MATH ERROR: Found {total_apples} apples. Logic is doubling counts.")

        assert total_apples == 2, f"Expected 2 apples total, found {total_apples}"
        assert safeway_apples == 2, "Store assignment failed. Safeway should have 2 apples."
        assert reminder_ok, "Reminder scheduling failed."
        print("✅ ALL FEATURES PASSED: Store, Math, Duplicates, Deletion, and Reminders.")