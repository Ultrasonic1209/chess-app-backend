"""
Contains the sanic app that should be run.
"""
import os
from textwrap import dedent

import git
import sanic.response
import ujson
from sanic import Sanic, Request, json, text
from sanic_ext import Config

from chess_bp import chess_blueprint as chessBp
from login import login
from misc import misc

ISDEV = bool(os.environ.get("DEV", False))

repo = git.Repo(search_parent_directories=True)
sha = repo.head.object.hexsha

app = Sanic("CheckmateBackend")

app.extend(config=Config(
    oas=True,
    oas_autodoc=True,
    oas_ui_default="swagger",

    cors_origins="https://chessapp.ultras-playroom.xyz,https://*.chessapp.ultras-playroom.xyz/sign-in",
    cors_supports_credentials=True,

    FC_SECRET="captcha token redacted", #should be in an env var
    SECRET="web token redacted"
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
    app.run(
        host='0.0.0.0',
        port=6969,
        fast=True,
        auto_reload=True,
        debug=ISDEV,
        access_log=ISDEV,
    )
