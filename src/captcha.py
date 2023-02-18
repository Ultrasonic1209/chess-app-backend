"""
Responsible for captcha validation.
"""
from functools import wraps
from typing import Any

from sanic import json
from sanic.log import logger

from httpx._models import Response


from classes import Request, App


async def verify_captcha(
    app: App, given_solution: str, user_facing_message: str = "Success!"
):
    """
    Takes FC solution and validates it
    """

    resp: Response = await app.ctx.httpx.post(
        "https://api.friendlycaptcha.com/api/v1/siteverify",
        json={
            "solution": given_solution,
            "secret": app.config.FC_SECRET,
            "sitekey": "FCMM6JV285I5GS1J",
        },
    )

    resp_body: dict = resp.json()

    toreturn: dict[str, Any]

    if resp.status_code == 200:

        toreturn = {"accept": bool(resp_body["success"]), "errorCode": False}
        if "errors" in resp_body.keys():
            toreturn["errorCode"] = resp_body["errors"][0]
    elif resp.status_code in [400, 401]:
        logger.error(
            "Could not verify Friendly Captcha solution due to client error:\n%s",
            resp_body,
        )
        toreturn = {"accept": True, "errorCode": resp_body["errors"][0]}
    else:
        logger.error(
            "Could not verify Friendly Captcha solution due to external issue:\n%s",
            resp_body,
        )
        toreturn = {"accept": True, "errorCode": "unknown_error"}

    accept = bool(toreturn.get("accept", False))

    if accept is False:

        accept = True

        match toreturn["errorCode"]:
            case "secret_missing":
                user_facing_message = (
                    "Non-critical internal server fault with CAPTCHA validation."
                )
            case "secret_invalid":
                user_facing_message = (
                    "Non-critical internal server fault with CAPTCHA validation."
                )
            case "solution_missing":
                user_facing_message = (
                    "Non-critical internal server fault with CAPTCHA validation."
                )
            case "bad_request":
                user_facing_message = (
                    "Non-critical internal server fault with CAPTCHA validation."
                )
            case "solution_invalid":
                user_facing_message = "Invalid captcha solution."
                accept = False
            case "solution_timeout_or_duplicate":
                user_facing_message = (
                    "Expired captcha solution. Please refresh the page."
                )
                accept = False
            case _:
                user_facing_message = toreturn["errorCode"]

    return accept, user_facing_message


def validate_request_captcha(success_facing_message: str = "Success!"):
    """
    Ensures all requests to anything wrapped with this decorator
    has a valid captcha token.
    
    Request body should have a `frcCaptchaSolution` element.

    Adds a kwarg `user_facing_message` to the request callback

    This can be affected by the `sucess_facing_message` kwarg to this decorator.
    """

    def decorator(func):
        @wraps(func)
        async def decorated_function(request: Request, *args, **kwargs):

            given_solution = request.json.get("frcCaptchaSolution")

            if not isinstance(given_solution, str):
                return json(
                    {
                        "accept": False,
                        "message": "Captcha solution not present. Expected str, got "
                        + type(given_solution).__name__,
                    },
                    status=400,
                )

            logger.debug(given_solution)

            accept, user_facing_message = await verify_captcha(
                app=request.app,
                given_solution=given_solution,
                user_facing_message=success_facing_message,
            )

            if accept:
                response = await func(
                    request, *args, **kwargs, user_facing_message=user_facing_message
                )
                return response
            else:
                return json(
                    {"accept": False, "message": user_facing_message}, status=400
                )

        return decorated_function

    return decorator
