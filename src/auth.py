"""
From https://sanic.dev/en/guide/how-to/authentication.html#auth.py
"""
from functools import wraps

import jwt
from sanic import text
import sanic


def check_token(request: sanic.Request):
    """
    Check a token.
    TODO figure out how it does that
    """

    token = request.cookies.get(".CHECKMATESECRET")
    if not token:
        return False

    try:
        jwt.decode(
            token, request.app.config.SECRET, algorithms=["HS256"]
        )
    except jwt.exceptions.InvalidTokenError:
        return False
    else:
        return True


def protected(wrapped):
    """
    Ensures all requests to anything wrapped with this decorator are authenticated.
    """
    def decorator(func):
        @wraps(func)
        async def decorated_function(request, *args, **kwargs):
            is_authenticated = check_token(request)

            if is_authenticated:
                response = await func(request, *args, **kwargs)
                return response
            else:
                return text("You are unauthorized.", 401)

        return decorated_function

    return decorator(wrapped)
