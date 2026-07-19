"""Declarative SQLAlchemy base class."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all persistent KiyoDesk models."""
