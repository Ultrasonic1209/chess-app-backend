"""
From https://sanic.dev/en/guide/how-to/authentication.html#auth.py
"""
from datetime import datetime
from functools import wraps
from typing import Optional

import jwt

from sanic import text, json
import sanic

from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from classes import Request, Token

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

def protected(wrapped, silent: bool = False):
    """
    Ensures all requests to anything wrapped with this decorator are authenticated.
    """
    def decorator(func):
        @wraps(func)
        async def decorated_function(request: Request, *args, **kwargs):
            token: Optional[Token] = check_token(request)

            if token:
                if expiretimestamp := token["expires"]:
                    expiretime = datetime.fromtimestamp(expiretimestamp)

                    if expiretime <= datetime.now():
                        if silent:
                            return json({})
                        else:
                            return text("Authorisation has expired.", 401)

                session: AsyncSession = request.ctx.session

                async with session.begin():
                    user: User = await session.get(User, token["user_id"])

                response = await func(request, *args, **kwargs, profile=user, token=token)
                return response
            else:
                if silent:
                    return json({})
                else:
                    return text("You are unauthorized.", 401)

        return decorated_function

    return decorator(wrapped)
