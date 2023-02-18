"""
Represents the database as a bunch of Python objects.
"""
import hashlib
from email.headerregistry import Address
from io import StringIO
from typing import List, Optional

import arrow
import chess
import chess.pgn
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.mysql.types import INTEGER
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import functions
from sqlalchemy_utils import ArrowType, EmailType, PasswordType, force_auto_coercion

import classes

force_auto_coercion()

__all__ = ["BaseModel", "User", "Player", "Game", "Session"]

_LAZYMETHOD = "selectin"


def censor_email(email: Optional[str] = None):
    """
    Takes an email and censors all but the domain and the first few digits of the name.
    """
    if str is None:
        return ""

    address = Address(addr_spec=email)

    username = address.username

    exposedlength = min(3, len(username) - 1)

    username = username[:exposedlength] + ("*" * (len(username) - exposedlength))

    return str(Address(username=username, domain=address.domain))


ANONYMOUS_IMG = "https://dev.chessapp.ultras-playroom.xyz/maskable_icon.png"


def hash_email(email: Optional[str]):
    """
    Takes an email and returns a hash for use for Gravatar
    """
    if email is None:
        email = ""
    email = email.strip().lower().encode("utf-8")
    return hashlib.md5(email).hexdigest()


class BaseModel(DeclarativeBase):
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

    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="User ID"
    )

    username: Mapped[str] = mapped_column(
        String(63), nullable=False, unique=True, comment="Username"
    )
    password: Mapped[str] = mapped_column(
        PasswordType(schemes=["pbkdf2_sha512"]), nullable=False, comment="Password"
    )

    score: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, default=400, comment="Player score"
    )

    email: Mapped[Optional[str]] = mapped_column(
        EmailType(length=127), nullable=True, comment="Email address"
    )

    time_created: Mapped[arrow.Arrow] = mapped_column(
        ArrowType,
        nullable=False,
        server_default=functions.now(),
        comment="Account creation timestamp",
    )

    players: Mapped[List["Player"]] = relationship(
        "Player", back_populates="user", lazy=_LAZYMETHOD
    )

    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="user", lazy=_LAZYMETHOD
    )

    def to_dict(self):
        return {
            "name": self.username,
            "email": censor_email(self.email),
            "avatar_hash": self.get_avatar_hash(),
            "rank": self.score,
            "timeCreated": self.time_created.isoformat(),
        }

    def public_to_dict(self) -> classes.PublicChessEntityDict:
        """
        Like `to_dict` but public!
        """
        return classes.PublicChessEntityDict(
            name=self.username,
            avatar_hash=self.get_avatar_hash(),
            rank=self.score,
            time_created=self.time_created.isoformat(),
        )


class Session(BaseModel):
    """
    For unregistered players to be able to play online games.
    """

    __tablename__ = "Session"

    session_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, primary_key=True, comment="Session ID"
    )

    session: Mapped[str] = mapped_column(
        String(255),
        primary_key=False,
        nullable=False,
        unique=True,
        index=True,
        comment="Session Token (Password for machines)",
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("User.user_id"), nullable=True, comment="Linked User ID"
    )

    user: Mapped[Optional[User]] = relationship(
        "User", back_populates="sessions", uselist=False, lazy=_LAZYMETHOD
    )

    players: Mapped[List["Player"]] = relationship(
        "Player", back_populates="session", lazy=_LAZYMETHOD
    )

    def public_to_dict(self) -> classes.PublicChessEntityDict:
        """
        Like `to_dict` but public!
        """
        return classes.PublicChessEntityDict(
            name=None, avatar_hash=None, rank=None, time_created=None
        )


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

    game_id: Mapped[int] = mapped_column(
        ForeignKey("Game.game_id"),
        nullable=False,
        primary_key=True,
        comment="Linked Game ID",
    )

    is_white: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        primary_key=True,
        comment="Flags the player's colour.",
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("User.user_id"), nullable=True, comment="Linked User ID"
    )

    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("Session.session_id"), nullable=True, comment="Linked Session ID"
    )

    user: Mapped[Optional[User]] = relationship(
        "User", back_populates="players", uselist=False, lazy=_LAZYMETHOD
    )

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="players",
        uselist=False,
        lazy=_LAZYMETHOD,
    )

    session: Mapped[Session] = relationship("Session", uselist=False, lazy=_LAZYMETHOD)

    def to_dict(self) -> classes.PublicChessPlayer:
        return {
            "userId": self.user_id,
            "username": self.user.username if self.user else None,
            "game_id": self.game_id,
            "is_white": self.is_white,
            "rank": self.user.score if self.user else None,
            "avatar_hash": self.get_avatar_hash(),
        }

    def to_dict_generalised(self):
        """
        like to_dict but returns something not related to a game!
        """
        return (
            self.user.public_to_dict() if self.user else self.session.public_to_dict()
        )


class GameTimer(BaseModel):
    """
    Timer type for chess games!
    types: Countup (1), Countdown (2)
    """

    __tablename__ = "GameTimer"

    timer_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="Timer ID"
    )

    timer_name: Mapped[str] = mapped_column(
        String(15), nullable=False, comment="Timer Name"
    )


class Game(BaseModel):
    """
    Each chess game has one game. (lol)
    """

    __tablename__ = "Game"

    game_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, comment="Game ID"
    )

    game: Mapped[str] = mapped_column(
        String(8192),
        nullable=True,
        comment="Holds game metadata and a list of moves made",
    )

    time_started: Mapped[Optional[arrow.Arrow]] = mapped_column(
        ArrowType, nullable=True, comment="Game start timestamp"
    )

    time_ended: Mapped[Optional[arrow.Arrow]] = mapped_column(
        ArrowType, nullable=True, comment="Game end timestamp"
    )

    white_won: Mapped[Optional[bool]] = mapped_column(
        Boolean(), nullable=True, comment="Whether the player playing white won or not"
    )

    timer_id: Mapped[int] = mapped_column(
        ForeignKey("GameTimer.timer_id"), nullable=False, comment="The game's timer ID"
    )

    timeLimit: Mapped[Optional[int]] = mapped_column(
        INTEGER(unsigned=True),
        nullable=True,
        comment="The amount of time each player gets",
    )

    timer: Mapped[GameTimer] = relationship(
        "GameTimer", uselist=False, lazy=_LAZYMETHOD
    )

    players: Mapped[List[Player]] = relationship(
        "Player", back_populates="game", lazy=_LAZYMETHOD
    )

    async def hospice(
        self, chessgame: Optional[chess.pgn.Game] = None, force_save: bool = False
    ):
        """
        If the game should end, make it end.
        """

        if not self.time_started:
            return

        game = chessgame or chess.pgn.read_game(StringIO(self.game))
        old_white_won = self.white_won

        if self.time_started:
            if outcome := game.end().board().outcome():
                game.headers["Result"] = outcome.result()
                game.headers["Termination"] = "normal"

                self.time_ended = arrow.now()
                self.white_won = outcome.winner
            elif (
                self.timer.timer_name == "Countdown"
            ):  # check if players are out of time
                seconds_since_start = (arrow.now() - self.time_started).total_seconds()

                times = [node.clock() - self.timeLimit for node in game.mainline()]

                white = 0
                black = 0

                is_white = True

                last_time = self.timeLimit

                for time in times:
                    if is_white:
                        white += last_time - time
                    elif not is_white:
                        black += last_time - time
                    last_time = time
                    is_white = not is_white

                time_moving = white + black

                white = self.timeLimit - white
                black = self.timeLimit - black

                if game.turn() == chess.WHITE:
                    white -= seconds_since_start - time_moving
                elif game.turn() == chess.BLACK:
                    black -= seconds_since_start - time_moving

                if white <= 0:
                    game.headers["Result"] = "0-1"
                    game.headers["Termination"] = "time forefit"

                    self.time_ended = arrow.now()
                    self.white_won = False
                elif black <= 0:
                    game.headers["Result"] = "1-0"
                    game.headers["Termination"] = "time forefit"

                    self.time_ended = arrow.now()
                    self.white_won = True

        if self.white_won != old_white_won:  # change the players' ranks!
            for player in self.players:
                if player.is_white:
                    white = player
                else:
                    black = player

            winner = white if self.white_won else black
            loser = black if self.white_won else white

            if winning_user := winner.user:
                winning_user.score += 1

            if losing_user := loser.user:
                losing_user.score -= 1

        if (game != chessgame) or force_save:
            exporter = chess.pgn.StringExporter(
                headers=True, variations=True, comments=True
            )

            pgn_string = game.accept(exporter)

            self.game = pgn_string

    def to_dict(self):
        # this is technically the more "correct" way to go around this it seems
        return classes.PublicChessGame(
            game_id=self.game_id,
            time_started=self.time_started.isoformat() if self.time_started else None,
            time_ended=self.time_ended.isoformat() if self.time_ended else None,
            white_won=self.white_won,
            players=[player.to_dict() for player in self.players],
            timer=self.timer.timer_name,
            time_limit=self.timeLimit,
            game=self.game,
        )
