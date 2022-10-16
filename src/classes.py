"""
Holds shared classes that don't fit into `models.py`
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import List, Optional, TypedDict

from sanic import Sanic
from sanic import Request as SanicRequest
from sanic_ext import Config

import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class AppConfig(Config):
    """
    Holds custom config variables for the app.
    """

    FC_SECRET: str
    SECRET: str


class Context(SimpleNamespace):
    """
    This is to allow typechecking of custom app context.
    """

    session: AsyncSession
    httpx: httpx.AsyncClient


class App(Sanic):
    """
    This is to allow typechecking of custom config variables.
    """

    config: AppConfig
    ctx: Context


class Request(SanicRequest):
    """
    This is to allow typechecking of the custom App.
    """

    app: App
    ctx: Context


class User(TypedDict):
    """
    Represents the OpenAPI representation of a Checkmate user.
    """

    name: str
    email: str
    timeCreated: str


class Token(TypedDict):
    """
    The format that the JWTs are generated in
    """

    user_id: int
    session: str
    expires: Optional[float]


class Message:
    """
    One field: message
    """

    message: str


class MessageWithAccept:
    """
    Message class but with Accept boolean.
    """

    accept: bool
    message: str


class LoginResponse:
    """
    Classes the response from /login
    """

    accept: bool
    message: str
    profile: Optional[User]


@dataclass
class LoginBody:
    """
    Validates /login for frcCaptchaSolution in a JSON dict.
    """

    username: str
    password: str
    # pylint: disable=invalid-name
    rememberMe: bool
    frcCaptchaSolution: str


class PublicChessPlayer(TypedDict):
    """
    what everyone gets to know about any chess player
    """

    username: Optional[str]
    userId: Optional[int]
    isWhite: bool
    rank: Optional[int]
    avatar_hash: str


class PublicChessGame(TypedDict):
    """
    what everyone gets to know about any chess game
    """

    game_id: int
    time_started: Optional[str]
    time_ended: Optional[str]
    white_won: Optional[bool]
    players: List[PublicChessPlayer]
    timer: str
    time_limit: Optional[int]
    game: Optional[str]


class PublicChessGameResponse(PublicChessGame):
    """
    PublicChessGame but it has more localised response
    """

    is_white: Optional[bool]


class NewChessGameResponse:
    """
    What you get when you create a game
    """

    gameid: int


@dataclass
class NewChessGameOptions:
    """
    Options that can be given for how the game should be created
    """

    creatorStartsWhite: bool
    countingDown: bool
    timeLimit: Optional[int]


@dataclass
class ChessEntry:
    """
    Options that can be given for how you wish to enter a chess game
    """

    wantsWhite: Optional[bool]


@dataclass
class NewChessMove:
    """
    So people can make moves on chess games!
    """

    san: str


@dataclass
class GetGameOptions:
    """
    So people can find out what online games they can view
    """

    my_games: bool
    page_size: int
    page: int


@dataclass
class SignupBody:
    """
    Options for when you make an account
    """

    username: str
    password: str
    email: str
    frcCaptchaSolution: str


class SignupResponse:
    """
    Responding to an account signup
    """

    accept: bool
    response: str


class PublicChessEntity:
    """
    Information about users/sessions that everyone is entitled to know!
    """

    name: Optional[str]
    avatar_hash: Optional[str]
    rank: Optional[int]
    time_created: Optional[str]


class PublicChessEntityDict(TypedDict):
    """
    Information about users/sessions that everyone is entitled to know!
    """

    name: Optional[str]
    avatar_hash: Optional[str]
    rank: Optional[int]
    time_created: Optional[str]


class StatsResponse:
    """
    Contains statistics about a given user/session.
    """

    games_played: int
    games_won: int
    percentage_of_playing_white: int
    favourite_opponent: PublicChessEntity


@dataclass
class UpdateBody:
    """
    Options that can be given for how you wish to update a user
    """

    old_password: str
    new_password: Optional[str]
    new_email: Optional[str]


class UpdateResponse:
    """
    What the user will get when they update their user
    """

    message: str
    profile: User
