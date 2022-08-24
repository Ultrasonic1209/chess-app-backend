"""
From https://sanic.dev/en/guide/how-to/authentication.html#auth.py
"""
from datetime import datetime
from functools import wraps
from typing import Optional
import secrets

import jwt

from sanic import text, json
import sanic
#from sanic.log import logger

from sqlalchemy import select
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Session
from classes import Request, Token

from login import get_hostname

def check_token(request: sanic.Request) -> Optional[Token]:
    """
    Check a token.
    TODO figure out how it does that
    """

    token = request.cookies.get(".CHECKMATESECRET")
    if not token:
        return None

    try:
        return jwt.decode(
            jwt=token,
            key=request.app.config.SECRET,
            algorithms=["HS256"]
        )
    except jwt.exceptions.InvalidTokenError:
        return None

async def authenticate_request(request: Request):
    """
    Retrieves a session and corresponding user from a request.
    TODO: move expiration to the server
    """
    token: Optional[Token] = check_token(request)

    if token:
        if expiretimestamp := token["expires"]:
            expiretime = datetime.fromtimestamp(expiretimestamp)

            if expiretime <= datetime.now():
                return None, None

        session: AsyncSession = request.ctx.session

        stmt = select(Session).where(
            Session.session == token["session"]
        ).with_hint(Session, "USE INDEX (ix_Session_session)")

        async with session.begin():
            user_session_result: Result = await session.execute(stmt)

            user_session_row = user_session_result.first()

            if not user_session_row:
                return None, None

            user_session: Session = user_session_row["Session"]

            user: Optional[User] = user_session.user

        return user, user_session
    else:
        return None, None

def is_logged_in(silent: bool = False):
    """
    Ensures all requests to anything wrapped with this decorator are authenticated.
    """
    def decorator(func):
        @wraps(func)
        async def decorated_function(request: Request, *args, **kwargs):
            user, session = await authenticate_request(request=request)

            if user:
                response = await func(request, *args, **kwargs, profile=user, session=session)
                return response
            else:
                if silent:
                    return json({})
                else:
                    return text("You are not logged in.", 401)

        return decorated_function

    return decorator

def has_session(create: bool = True):
    """
    Ensures all requests to anything wrapped with this decorator has a session, creating one if necessary.
    Passes a user as well,
    """
    def decorator(func):
        @wraps(func)
        async def decorated_function(request: Request, *args, **kwargs):
            user, session = await authenticate_request(request=request)

            if session is None:
                if not create:
                    return text("No session?", status=401)

                query_session: AsyncSession = request.ctx.session

                async with query_session.begin():
                    session = Session()
                    session.session = secrets.token_hex(32)
                    query_session.add(session)

                response: sanic.HTTPResponse = await func(request, *args, **kwargs, profile=user, session=session)

                payload = {
                    'user_id': None,
                    'session': session.session,
                    'expires': None
                }

                token = jwt.encode(payload, request.app.config.SECRET)

                response.cookies[".CHECKMATESECRET"] = token
                response.cookies[".CHECKMATESECRET"]["secure"] = True
                response.cookies[".CHECKMATESECRET"]["samesite"] = "Lax"
                response.cookies[".CHECKMATESECRET"]["domain"] = get_hostname(request.headers.get("host", ""))
                response.cookies[".CHECKMATESECRET"]["comment"] = "I'm in so much pain"

                return response
            else:
                response = await func(request, *args, **kwargs, profile=user, session=session)
                return response

        return decorated_function

    return decorator
