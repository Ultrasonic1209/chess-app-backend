"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets

import jwt
import httpx

from sanic import Blueprint, json
from sanic.log import logger
from sanic_ext import validate, openapi

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result

from auth import is_logged_in, get_hostname, has_session
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
@validate(json=dataclass(LoginBody))
@has_session()
async def do_login(request: Request, body: LoginBody, user: models.User, session: models.Session):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    if session.user:
        return json({
            "accept": False,
            "userFacingMessage": "You are already logged in!"
        })

    given_solution = body.frcCaptchaSolution

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

    session: AsyncSession = request.ctx.session

    username = body.username
    password = body.password

    stmt = select(models.User).where(
        models.User.username == username
    )

    async with session.begin():
        resp: Result = await session.execute(stmt)

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

        usertoken = secrets.token_hex(32)

        usersession = models.Session()
        usersession.session = usertoken

        user.sessions.append(usersession)

    expires = (datetime.now() + timedelta(weeks=4)).timestamp() if body.rememberMe else None

    payload = {
        'user_id': user.user_id,
        'session': usertoken,
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
    response.cookies[".CHECKMATESECRET"]["secure"] = True
    response.cookies[".CHECKMATESECRET"]["samesite"] = "Lax"
    response.cookies[".CHECKMATESECRET"]["domain"] = get_hostname(request.headers.get("host", ""))
    response.cookies[".CHECKMATESECRET"]["comment"] = "I'm in so much pain"

    if body.rememberMe:
        response.cookies[".CHECKMATESECRET"]["expires"] = datetime.fromtimestamp(expires)

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
