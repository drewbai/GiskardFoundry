"""SQLAlchemy engine and session utilities."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def get_engine(url: str) -> Engine:
    """Create and return a SQLAlchemy engine for the given URL."""
    return create_engine(url)


SessionLocal = sessionmaker(autocommit=False, autoflush=False)
