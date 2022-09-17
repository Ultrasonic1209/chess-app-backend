"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from datetime import datetime, timedelta

import jwt
import httpx

from sanic import Blueprint, json, text
from sanic.log import logger
from sanic_ext import validate, openapi

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result

from auth import is_logged_in, has_session
from classes import Request, LoginBody, LoginResponse

import models

HTTPX_CLIENT = httpx.AsyncClient()

login = Blueprint("login", url_prefix="/login")

async def verify_captcha(given_solution: str, fc_secret: str):
    """
    Takes FC solution and validates it
    """

    resp = await HTTPX_CLIENT.post(
        "https://api.friendlycaptcha.com/api/v1/siteverify",
        json={
            "solution": given_solution,
            "secret": fc_secret,
            "sitekey": "FCMM6JV285I5GS1J"
        }
    )

    resp_body: dict = resp.json()

    if resp.status_code == 200:

        toreturn = {
            "accept": bool(resp_body["success"]),
            "errorCode": False
        }
        if "errors" in resp_body.keys():
            toreturn["errorCode"] = resp_body["errors"][0]

        return toreturn
    elif resp.status_code in [400, 401]:
        logger.error(
            "Could not verify Friendly Captcha solution due to client error:\n%s",
            resp_body
        )
        return {
            "accept": True,
            "errorCode": resp_body["errors"][0]
        }
    else:
        logger.error(
            "Could not verify Friendly Captcha solution due to external issue:\n%s",
            resp_body
        )
        return {
            "accept": True,
            "errorCode": "unknown_error"
        }

@login.post("/")
@openapi.body(LoginBody)
@openapi.response(status=200, content={"application/json": LoginResponse}, description="When a valid login attempt is made")
@validate(json=LoginBody, body_argument="params")
@has_session()
async def do_login(request: Request, params: LoginBody, user: models.User, session: models.Session):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    if session.user:
        return json({
            "accept": False,
            "userFacingMessage": "You are already logged in!"
        })

    given_solution = params.frcCaptchaSolution

    captcha_resp = await verify_captcha(given_solution, request.app.config.FC_SECRET)

    user_facing_message = "Signed you in! Redirecting..." # the toast people will see after they're redirected to homepage (sign-in complete)

    if bool(captcha_resp.get("accept", False)) is False:

        accept = True

        match captcha_resp["errorCode"]:
            case "secret_missing":
                user_facing_message = "Non-critical internal server fault with CAPTCHA validation."
            case "secret_invalid":
                user_facing_message = "Non-critical internal server fault with CAPTCHA validation."
            case "solution_missing":
                user_facing_message = "Non-critical internal server fault with CAPTCHA validation."
            case "bad_request":
                user_facing_message = "Non-critical internal server fault with CAPTCHA validation."
            case "solution_invalid":
                user_facing_message = "Invalid captcha solution."
                accept = False
            case "solution_timeout_or_duplicate":
                user_facing_message = "Expired captcha solution. Please refresh the page."
                accept = False
            case _:
                user_facing_message = captcha_resp["errorCode"]

        if not accept:
            return json({
                "accept": False,
                "userFacingMessage": user_facing_message
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
                    "userFacingMessage": "Invalid username or password."
                }
            )

        user: models.User = row["User"]

        if user.password != password:
            # password incorrect
            return json(
                {
                    "accept": False,
                    "userFacingMessage": "Invalid username or password."
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
            "userFacingMessage": user_facing_message,
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

    async with query_session.begin():
        await query_session.delete(session)

    response = json({"success": True})
    del response.cookies[".CHECKMATESECRET"]

    return response

@login.get("/identify")
@is_logged_in(silent=True)
async def identify(request: Request, user: models.User, session: models.Session):
    """
    Returns the profile you are authenticating as.
    """

    return json(user.to_dict())

@login.post("/signup")
@has_session()
async def new_user(request: Request, user: models.User, session: models.Session):
    """
    
    Creates a new user. **Temporary**

    openapi:
    ---
    parameters:
      - name: x-admin-key
        in: header
        description: This needs to be correct.
        required: true
      - name: x-username
        in: header
        description: Username
        required: true
      - name: x-password
        in: header
        description: Password.
        required: true
      - name: x-email
        in: header
        description: Email.
        required: false
    """

    auth = request.headers.get("x-admin-key")

    if auth != "***REMOVED***":
        return text("hint: first name, capital S", status=401)

    if user:
        return text("You are already logged into an account!", status=400)

    session: AsyncSession = request.ctx.session
    async with session.begin():
        user = models.User()

        user.username = request.headers.get("x-username")
        user.password = request.headers.get("x-password")
        user.email = request.headers.get("x-email")

        session.add(user)

