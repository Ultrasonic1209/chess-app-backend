"""
From https://sanic.dev/en/guide/how-to/authentication.html#auth.py
"""
from datetime import datetime
from functools import wraps
from typing import TypedDict, Optional

import jwt
from sanic import text
from sanic.log import logger
import sanic
class Profile(TypedDict):
    """
    The format that the JWTs are generated in
    """
    user_id: int
    expires: Optional[float]

def check_token(request: sanic.Request) -> Optional[Profile]:
    """
    Check a token.
    TODO figure out how it does that
    """

    token = request.cookies.get(".CHECKMATESECRET")
    if not token:
        return None

    logger.info(token)

    try:
        return jwt.decode(
            jwt=token,
            key=request.app.config.SECRET,
            algorithms=["HS256"]
        )
    except jwt.exceptions.InvalidTokenError:
        return None


def protected(wrapped):
    """
    Ensures all requests to anything wrapped with this decorator are authenticated.
    """
    def decorator(func):
        @wraps(func)
        async def decorated_function(request, *args, **kwargs):
            profile: Profile = check_token(request)

            if profile:
                if expiretimestamp := profile["expires"]:
                    expiretime = datetime.fromtimestamp(expiretimestamp)

                    if expiretime <= datetime.now():
                        return text("Authorisation has expired.", 401)

                response = await func(request, *args, **kwargs, profile=profile)
                return response
            else:
                return text("You are unauthorized.", 401)

        return decorated_function

    return decorator(wrapped)
