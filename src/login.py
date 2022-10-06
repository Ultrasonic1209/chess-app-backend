"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from datetime import datetime, timedelta

import jwt

from sanic import Blueprint, json
from sanic_ext import validate, openapi

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result
from sqlalchemy import exc

from auth import is_logged_in, has_session
from captcha import validate_request_captcha
from classes import Request, LoginBody, LoginResponse, SignupBody, SignupResponse

import models

login = Blueprint("login", url_prefix="/login")

@login.post("/")
@openapi.body(LoginBody)
@openapi.response(status=200, content={"application/json": LoginResponse}, description="When a valid login attempt is made")
@validate(json=LoginBody, body_argument="params")
@validate_request_captcha(success_facing_message="Signed you in! Redirecting...")
@has_session()
async def do_login(request: Request, params: LoginBody, user_facing_message: str, user: models.User, session: models.Session):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    if session.user:
        return json({
            "accept": False,
            "message": "You are already logged in!"
        })

    query_session: AsyncSession = request.ctx.session

    username = params.username
    password = params.password

    stmt = select(models.User).where(
        models.User.username == username
    )

    async with query_session.begin():
        resp: Result = await query_session.execute(stmt)

        row = resp.first()

        if row is None:
            # account not found
            return json(
                {
                    "accept": False,
                    "message": "Invalid username or password."
                }
            )

        user: models.User = row["User"]

        if user.password != password:
            # password incorrect
            return json(
                {
                    "accept": False,
                    "message": "Invalid username or password."
                }
            )

        # user is authenticated

        user.sessions.append(session)

    expires = (datetime.now() + timedelta(weeks=4)).timestamp() if params.rememberMe else None

    payload = {
        'user_id': user.user_id,
        'session': session.session,
        'expires': expires
    }


    response = json(
        {
            "accept": True,
            "message": user_facing_message,
            "profile": user.to_dict()
        }
    )

    token = jwt.encode(payload, request.app.config.SECRET)

    response.cookies[".CHECKMATESECRET"] = token

    if params.rememberMe:
        response.cookies[".CHECKMATESECRET"]["expires"] = datetime.fromtimestamp(expires)

    # the rest of the cookie params are set by the has_session() decorator

    return response

@login.delete("/logout")
@is_logged_in(silent=True)
async def do_logout(request: Request, user: models.User, session: models.Session):
    """
    Removes JSON Web Token and destroys the session.
    """
    query_session: AsyncSession = request.ctx.session

    if len(session.players) == 0:

        async with query_session.begin():
            await query_session.delete(session)

        response = json({"success": True})
        del response.cookies[".CHECKMATESECRET"]
    else:

        async with query_session.begin():
            session.user = None

        response = json({"success": True})

    return response

@login.get("/identify")
@is_logged_in(silent=True)
async def identify(request: Request, user: models.User, session: models.Session):
    """
    Returns the profile you are authenticating as.
    """

    return json(user.to_dict())

@login.post("/signup")
@openapi.body(SignupBody)
@openapi.response(status=200, content={"application/json": SignupResponse}, description="When an account is made")
@validate(json=SignupBody, body_argument="params")
@validate_request_captcha(success_facing_message="Please log into your new account.")
@has_session()
async def new_user(request: Request, params: SignupBody, user: models.User, session: models.Session, user_facing_message: str):
    """
    Creates a new user.
    Uses the same captcha as /login
    """

    if session.user:
        return json({
            "accept": False,
            "message": "Sign out before creating a new account."
        })

    query_session: AsyncSession = request.ctx.session
    try:
        async with query_session.begin():
            user = models.User()

            user.username = params.username
            user.password = params.password
            user.email = params.email if params.email != "" else None

            query_session.add(user)
    except exc.IntegrityError:
        return json({
            "accept": False,
            "message": "An account with this username already exists or you have provided invalid information."
        }, status=400)

    await query_session.refresh(user)

    #session.user = user

    return json({
        "accept": True,
        "message": user_facing_message
    })
