"""
Holds shared classes that don't fit into `models.py`
"""

from typing import Optional, TypedDict
from sanic import Sanic
from sanic import Request as SanicRequest
from sanic_ext import Config

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

class Request(SanicRequest):
    """
    This is to allow typechecking of the custom App.
    """
    app: App

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
