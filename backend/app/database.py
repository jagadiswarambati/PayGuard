import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import Engine
from .config import get_settings

logger = logging.getLogger("payguard.database")
settings = get_settings()

db_url = settings.database_url
connect_args = {}

try:
    if db_url.startswith("postgresql"):
        # Test connecting with a short timeout
        test_engine = create_engine(db_url, connect_args={"connect_timeout": 2})
        with test_engine.connect() as conn:
            pass
        engine = create_engine(db_url, pool_pre_ping=True)
        logger.info(f"Connected to PostgreSQL database: {db_url}")
    else:
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        engine = create_engine(db_url, connect_args=connect_args)
except Exception as e:
    logger.warning(f"PostgreSQL connection to {db_url} failed ({e}). Falling back to local SQLite database: sqlite:///./payguard.db")
    db_url = "sqlite:///./payguard.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in db_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

