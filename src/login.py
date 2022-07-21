"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from dataclasses import dataclass
import random
import jwt
import httpx

from sanic import Blueprint, Request, text, json
from sanic.log import logger
from sanic_ext import validate

from auth import protected

HTTPX_CLIENT = httpx.AsyncClient()

login = Blueprint("login", url_prefix="/login")

@dataclass
class LoginBody:
    """
    Validates /login for frcCaptchaSolution in a JSON dict.
    """
    # pylint: disable=invalid-name
    frcCaptchaSolution: str


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
            "accept": resp_body["success"]
        }
        
        if "errorCode" in resp_body.keys():
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
@validate(json=LoginBody)
async def do_login(request: Request, body: LoginBody):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    given_solution = body.frcCaptchaSolution

    captcha_resp = await verify_captcha(given_solution, request.app.config.FC_SECRET)

    logger.info(captcha_resp)

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
    