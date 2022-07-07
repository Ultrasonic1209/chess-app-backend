"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
"""
import random
import jwt
from sanic import Blueprint, Request, text, json
from auth import protected

login = Blueprint("login", url_prefix="/login")

@login.post("/")
async def do_login(request: Request):
    """
    Assigns JSON Web Token
    """

    payload = {
        'user_id': random.randint(666,1337)
    }

    token = jwt.encode(payload, request.app.config.SECRET)
    return text(token)

@login.get("/identify")
@protected
async def identify(request: Request):
    """
    Returns the profile you are authenticating as.
    """
    profile = jwt.decode(
        request.token, request.app.config.SECRET, algorithms=["HS256"]
    )

    return json({"payload": profile})
    