"""
Represents the database as a bunch of Python objects.
"""
from sqlalchemy import BOOLEAN, INTEGER, TIMESTAMP, Column, ForeignKey, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class BaseModel(Base):
    """
    Base Model
    """
    __abstract__ = True


class User(BaseModel):
    """
    Each Checkmate user account has this.
    """
    __tablename__ = "User"

    user_id = Column(INTEGER(), primary_key=True)

    username = Column(String(50))
    password = Column(String(64))
    email = Column(String(100), nullable=True)
    time_created = Column(TIMESTAMP())

    def to_dict(self):
        """
        Converts the user from an SQL object to a Python dictionary.
        """
        return {"name": self.username, "email": self.email, "timeCreated": self.timeCreated}


class Player(BaseModel):
    """
    Each chess game has two players.
    """
    __tablename__ = "Player"

    user_id = Column(ForeignKey("Person.user_id"), primary_key=True)
    game_id = Column(ForeignKey("Game.game_id"), primary_key=True)

    is_white = Column(BOOLEAN())

class Game(BaseModel):
    """
    Each chess game has one game. (lol)
    """
    __tablename__ = "Game"

    game_id = Column(INTEGER(), primary_key=True)

    moves = Column(String(90), nullable=True)
    time_started = Column(TIMESTAMP())
    time_ended = Column(TIMESTAMP(), nullable=True)
    white_won = Column(BOOLEAN(), nullable=True)
