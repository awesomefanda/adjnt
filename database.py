from sqlmodel import create_engine, SQLModel, Session
import os

sqlite_url = "sqlite:///adjnt_vault.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session