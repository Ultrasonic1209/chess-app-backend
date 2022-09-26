"""
Represents the database as a bunch of Python objects.
"""
from typing import List, Optional, Union
from email.headerregistry import Address
import hashlib

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

def censor_email(email: Optional[str] = None):
    """
    Takes an email and censors all but the domain and the first few digits of the name.
    """
    if str is None:
        return ""

    address = Address(addr_spec=email)

    username = address.username

    exposedlength = min(3, len(username)-1)

    username = username[:exposedlength] + ("*" * (len(username) - exposedlength))

    return str(Address(username=username, domain=address.domain))

ANONYMOUS_IMG = "https://dev.chessapp.ultras-playroom.xyz/maskable_icon.png"

def hash_email(email: Union[str, None]):
    """
    Takes an email and returns a hash for use for Gravatar
    """
    if email is None:
        email = ""
    email = email.strip().lower().encode("utf-8")
    return hashlib.md5(email).hexdigest()

class BaseModel(Base):
    """
    Base Model
    """

    __abstract__ = True

    def to_dict(self):
        """
        Converts the model from an SQL object to a Python dictionary.
        """
        return {}

class User(BaseModel):
    """
    Each Checkmate user account has this.
    """

    __tablename__ = "User"

    def get_avatar_hash(self):
        """
        Returns the Gravatar hash for the user.
        """
        if self.email:
            return hash_email(self.email)

    user_id: int = Column(
        INTEGER(),
        primary_key=True
    )

    username: str = Column(
        String(63),
        nullable=False,
        unique=True

    )
    password = Column(
        PasswordType(schemes=["pbkdf2_sha512"]),
        nullable=False
    )

    score = Column(
        INTEGER(),
        nullable=False,
        default=400
    )

    email: str = Column(
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
            "email": censor_email(self.email),
            "avatar_hash": self.get_avatar_hash(),
            "rank": self.score,
            "timeCreated": self.time_created.isoformat(),
        }


class Player(BaseModel):
    """
    Each chess game has two players.
    """

    __tablename__ = "Player"


    def get_avatar_hash(self):
        """
        Returns the Gravatar hash for the player.
        """
        return self.user.get_avatar_hash() if self.user else ""

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

    def to_dict(self) -> classes.PublicChessPlayer:
        return {
            "userId": self.user_id,
            "username": self.user.username if self.user else None,
            "game_id": self.game_id,
            "is_white": self.is_white,
            "rank": self.user.score if self.user else None,
            "avatar_hash": self.get_avatar_hash()
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
            "players": [player.to_dict() for player in self.players],
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
