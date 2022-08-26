"""
Holds shared classes that don't fit into `models.py`
"""

from types import SimpleNamespace
from typing import List, Optional, TypedDict
from sanic import Sanic
from sanic import Request as SanicRequest
from sanic_ext import Config

from sqlalchemy.ext.asyncio import AsyncSession

class AppConfig(Config):
    """
    Holds custom config variables for the app.
    """
    FC_SECRET: str
    SECRET: str

class App(Sanic):
    """
    This is to allow typechecking of custom config variables.
    """
    config: AppConfig

class Context(SimpleNamespace):
    """
    This is to allow typechecking of custom app context.
    """
    session: AsyncSession

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

class LoginResponse:
    """
    Classes the response from /login
    """
    accept: bool
    userFacingMessage: str
    profile: Optional[User]

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

    userId: Optional[int]
    isWhite: bool

class PublicChessGame(TypedDict):
    """
    what everyone gets to know about any chess game
    """

    game_id: int
    time_started: str
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

class NewChessGameOptions:
    """
    Options that can be given for how the game should be created
    """

    creatorStartsWhite: bool
    countingDown: bool
    timeLimit: Optional[int]

class ChessEntry:
    """
    Options that can be given for how you wish to enter a chess game
    """

    wantsWhite: Optional[bool]

class NewChessMove:
    """
    So people can make moves on chess games!
    """

    san: str
