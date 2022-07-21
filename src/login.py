"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import jwt
import httpx

from sanic import Blueprint, Request, json
from sanic.log import logger
from sanic_ext import validate

from auth import protected

from urllib.parse import urlparse

def get_hostname(url, uri_type='netloc_only'):
    """Get the host name from the url"""
    parsed_uri = urlparse(url)
    if uri_type == 'both':
        return '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
    elif uri_type == 'netloc_only':
        return '{uri.netloc}'.format(uri=parsed_uri)

HTTPX_CLIENT = httpx.AsyncClient()

login = Blueprint("login", url_prefix="/login")

@dataclass
class LoginBody:
    """
    Validates /login for frcCaptchaSolution in a JSON dict.
    """
    username: str
    password: str
    # pylint: disable=invalid-name
    rememberMe: bool
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
@validate(json=LoginBody)
async def do_login(request: Request, body: LoginBody):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    given_solution = body.frcCaptchaSolution

    captcha_resp = await verify_captcha(given_solution, request.app.config.FC_SECRET)

    user_facing_message = "Signed you in! Redirecting..."

    if bool(captcha_resp.get("accept", False)) is False:

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
            case "solution_timeout_or_duplicate":
                user_facing_message = "Expired captcha solution. Please refresh the page."
            case _:
                user_facing_message = captcha_resp["errorCode"]

        return json({
            "accept": False,
            "userFacingMessage": user_facing_message
        })

    expires = (datetime.now() + timedelta(weeks=4)).timestamp() if body.rememberMe else None

    payload = {
        'user_id': random.randint(666,1337),
        'expires': expires
    }


    response = json(
        {
            "accept": True,
            "userFacingMessage": user_facing_message
        }
    )

    token = jwt.encode(payload, request.app.config.SECRET)

    response.cookies[".CHECKMATESECRET"] = token
    response.cookies[".CHECKMATESECRET"]["secure"] = True
    response.cookies[".CHECKMATESECRET"]["samesite"] = "None"
    response.cookies[".CHECKMATESECRET"]["domain"] = get_hostname(request.headers.get("origin", ""))
    response.cookies[".CHECKMATESECRET"]["comment"] = "I'm in so much pain"

    if body.rememberMe:
        response.cookies[".CHECKMATESECRET"]["expires"] = datetime.fromtimestamp(expires)

    return response

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
