import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import Engine
from .config import get_settings

logger = logging.getLogger("payguard.database")
settings = get_settings()

db_url = settings.database_url

# SQLite needs check_same_thread=False for FastAPI's async context
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args, echo=False)
logger.info(f"Database engine created: {db_url}")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite connections."""
    if db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they do not yet exist.
    Called automatically at application startup.
    """
    # Import all models so SQLAlchemy registers them with Base.metadata
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")
