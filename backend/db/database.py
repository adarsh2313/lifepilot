from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from backend.config import get_config

import os


class Base(DeclarativeBase):
    pass


def _get_engine():
    config = get_config()
    db_path = os.path.expanduser(config["db_path"])
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def get_engine():
    return _get_engine()


def create_tables():
    engine = _get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session_factory():
    engine = _get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
