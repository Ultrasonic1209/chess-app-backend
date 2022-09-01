"""
Represents the database as a bunch of Python objects.
"""
from typing import List, Optional

import arrow

from sqlalchemy import BOOLEAN, INTEGER, Column, ForeignKey, String, func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import MetaData

from sqlalchemy_utils import PasswordType, EmailType, ArrowType, force_auto_coercion

import classes

force_auto_coercion()

metadata_obj = MetaData()

__all__ = ["Base", "User", "Player", "Game", "Session"]

Base = declarative_base()

_LAZYMETHOD = "selectin"

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
        String(63),
        nullable=False,
        unique=True

    )
    password = Column(
        PasswordType(schemes=["pbkdf2_sha512"]),
        nullable=False
    )

    email = Column(
        EmailType(length=127),
        nullable=True
    )

    time_created: arrow.Arrow = Column(
        ArrowType,
        nullable=False,
        server_default=func.now()
    )

    players = relationship(
        "Player",
        back_populates="user",
        lazy=_LAZYMETHOD
    )

    sessions = relationship(
        "Session",
        back_populates="user",
        lazy=_LAZYMETHOD
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
        ForeignKey("Session.session_id"),
        nullable=True
    )

    user: Optional[User] = relationship(
        "User",
        back_populates="players",
        uselist=False,
        lazy=_LAZYMETHOD
    )

    game = relationship(
        "Game",
        back_populates="players",
        uselist=False,
        lazy=_LAZYMETHOD,
    )

    session = relationship(
        "Session",
        uselist=False,
        lazy=_LAZYMETHOD
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "game_id": self.game_id,
            "is_white": self.is_white
        }

class GameTimer(BaseModel):
    """
    Timer type for chess games!
    types: Countup (1), Countdown (2)
    """

    __tablename__ = "GameTimer"

    timer_id = Column(
        INTEGER(),
        primary_key=True
    )

    timer_name = Column(
        String(15)
    )
class Game(BaseModel):
    """
    Each chess game has one game. (lol)
    """

    __tablename__ = "Game"

    game_id = Column(
        INTEGER(),
        primary_key=True
    )

    game = Column(
        String(2047),
        nullable=True
    )

    time_started: Optional[arrow.Arrow] = Column(
        ArrowType,
        nullable=True
    )

    time_ended: Optional[arrow.Arrow] = Column(
        ArrowType,
        nullable=True
    )

    white_won = Column(
        BOOLEAN(),
        nullable=True
    )

    timer_id = Column(
        ForeignKey("GameTimer.timer_id"),
        nullable=False
    )

    timeLimit: int = Column(
        INTEGER(),
        nullable=True
    )

    timer: GameTimer = relationship(
        "GameTimer",
        uselist=False,
        lazy=_LAZYMETHOD
        )

    players: List[Player] = relationship(
        "Player",
        back_populates="game",
        lazy=_LAZYMETHOD
    )

    def to_dict(self) -> classes.PublicChessGame:
        return {
            "game_id": self.game_id,
            "time_started": self.time_started.isoformat() if self.time_started else None,
            "time_ended": self.time_ended.isoformat() if self.time_ended else None,
            "white_won": self.white_won,
            "players": [{"username": player.user.username if player.user else None, "userId": player.user.user_id if player.user else None, "isWhite": player.is_white} for player in self.players],
            "timer": self.timer.timer_name,
            "time_limit": self.timeLimit,
            "game": self.game
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
        String(255),
        primary_key=False,
        nullable=False,
        unique=True,
        index=True
    )

    user_id = Column(
        ForeignKey("User.user_id"),
        nullable=True
    )

    user: Optional[User] = relationship(
        "User",
        back_populates="sessions",
        uselist=False,
        lazy=_LAZYMETHOD
    )
