"""
Contains the sanic app that should be run.
"""
import os
from textwrap import dedent

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

    cors_origins=[
        "https://apichessapp.server.ultras-playroom.xyz",
        "https://chessapp.ultras-playroom.xyz",
        "https://dev.chessapp.ultras-playroom.xyz"
    ],
    cors_supports_credentials=True,
    cors_always_send=True,

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
