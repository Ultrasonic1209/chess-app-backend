"""
Contains the sanic app that should be run.
"""
import os
from textwrap import dedent
import re

import git
import sanic.response
import ujson
from dotenv import load_dotenv

from sanic import Sanic, Request, json, text
from sanic_ext import Config

from chess_bp import chess_blueprint as chessBp
from login import login
from misc import misc

load_dotenv()

ISDEV = bool(os.getenv("DEV"))

repo = git.Repo(search_parent_directories=True)
sha = repo.head.object.hexsha

app = Sanic("CheckmateBackend")

app.extend(config=Config(
    oas=True,
    oas_autodoc=True,
    oas_ui_default="swagger",

    cors_origins=re.compile(r"(.*)ultras-playroom\.xyz$"),
    cors_allow_headers=["Authorization", "Content-Type"],
    cors_supports_credentials=True,
    cors_always_send=True,
    cors_max_age=48,

    FC_SECRET=os.getenv("FRIENDLY_CAPTCHA_SECRET", ""),
    SECRET=os.getenv("JWT_SECRET", "")
))

app.ext.openapi.describe(
    title="Checkmate API",
    version=sha,
    description=dedent(
        """
        This API is a work-in-progress. _Everything_ is subject to change.
        """
    ),
)

app.blueprint((
    login,
    chessBp,
    misc
))

if not ISDEV:
    app.config.FORWARDED_SECRET = "secretsAreOverrated" # 10/10 secret

@app.middleware('response')
async def add_json(request: Request, response: sanic.response.HTTPResponse):
    """
    Adds my boilerplate JSON to any response JSON
    """
    if response.content_type == "application/json":
        parsed = ujson.loads(response.body)

        parsed["chess"] = "cool"

        new_response = json(parsed, status=response.status, headers=response.headers)

        return new_response

@app.middleware('response')
async def add_cors_response(request: Request, response: sanic.response.HTTPResponse):
    """
    Adds CORS headers to non-OPTIONS responses
    """
    if ((request.method.upper() != "OPTIONS") and
        (response.headers.get("Access-Control-Allow-Origin") is None) and
        (app.config.CORS_ORIGINS.match(request.headers.get("Origin")))):
        response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]

        return response


@app.get("/")
async def index(request: Request):
    """
    we all gotta start somewhere
    """

    resp = dedent(
        """
        Welcome to Checkmate's backend API.
        Please navigate to https://api-chessapp.server.ultras-playroom.xyz/docs for documentation.
        """
    )

    return text(resp)


if __name__ == '__main__':
    app.run( # poking around in the source, you can run app.make_coffee for coffee logo
        host='0.0.0.0',
        port=6969,
        fast=True,
        auto_reload=True,
        debug=ISDEV,
        access_log=True,
    )
