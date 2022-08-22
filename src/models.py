"""
Represents the database as a bunch of Python objects.
"""
from typing import List, Optional
from sqlalchemy import BOOLEAN, INTEGER, TIMESTAMP, Column, ForeignKey, String
from sqlalchemy.orm import declarative_base, relationship

from sqlalchemy import MetaData

from sqlalchemy_utils import PasswordType, EmailType, force_auto_coercion

force_auto_coercion()

metadata_obj = MetaData()

__all__ = ["Base", "User", "Player", "Game", "Session"]

Base = declarative_base()


class BaseModel(Base):
    """
    Base Model
    """

    __abstract__ = True

    def to_dict(self):
        """
        Converts the user from an SQL object to a Python dictionary.
        """
        return {}


class User(BaseModel):
    """
    Each Checkmate user account has this.
    """

    __tablename__ = "User"

    user_id = Column(
        INTEGER(),
        primary_key=True
    )

    username = Column(
        String(50),
        nullable=False,
        unique=True

    )
    password = Column(
        PasswordType(schemes=["pbkdf2_sha512"]),
        nullable=False
    )

    email = Column(
        EmailType(length=100),
        nullable=True
    )

    time_created = Column(
        TIMESTAMP(),
        nullable=False
    )

    players = relationship(
        "Player",
        back_populates="user"
    )

    sessions = relationship(
        "Session",
        back_populates="user"
    )

    def to_dict(self):
        return {
            "name": self.username,
            "email": self.email,
            "timeCreated": self.time_created.isoformat(),
        }


class Player(BaseModel):
    """
    Each chess game has two players.
    """

    __tablename__ = "Player"

    game_id = Column(
        ForeignKey("Game.game_id"),
        nullable=False,
        primary_key=True
    )

    is_white = Column(
        BOOLEAN(),
        nullable=False,
        primary_key=True
    )

    user_id = Column(
        ForeignKey("User.user_id"),
        nullable=True
    )

    session_id = Column(
        ForeignKey("Session.user_id"),
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="players",
        uselist=False
    )

    game = relationship(
        "Game",
        back_populates="players",
        uselist=False
    )

    session = relationship(
        "Session",
        uselist=False
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "game_id": self.game_id,
            "is_white": self.is_white
        }


class Game(BaseModel):
    """
    Each chess game has one game. (lol)
    """

    __tablename__ = "Game"

    game_id = Column(
        INTEGER(),
        primary_key=True
    )

    moves = Column(
        String(1024),
        nullable=True
    )

    time_started = Column(
        TIMESTAMP(),
        nullable=False
    )

    time_ended = Column(
        TIMESTAMP(),
        nullable=True
    )

    white_won = Column(
        BOOLEAN(),
        nullable=True
    )

    players: List[Player] = relationship(
        "Player",
        back_populates="game"
    )

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "time_started": self.time_started.isoformat(),
            "time_ended": self.time_ended.isoformat(),
            "white_won": self.white_won,
        }

class Session(Base):
    """
    For unregistered players to be able to play online games.
    """

    __tablename__ = "Session"

    session_id = Column(
        INTEGER(),
        nullable=False,
        primary_key=True
    )

    session = Column(
        String(256),
        primary_key=False,
        nullable=False,
        unique=True, 
        index=True
    )

    user_id = Column(
        ForeignKey("User.user_id"),
        nullable=True
    )

    user: User = relationship(
        "User",
        back_populates="sessions",
        uselist=False
    )
