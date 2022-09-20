"""
Contains the sanic app that should be run.
"""
from contextvars import ContextVar
import os
from textwrap import dedent
import re

import git
from dotenv import load_dotenv

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, AsyncConnection, create_async_engine
from sqlalchemy.orm import sessionmaker

from sanic import json, text
from sanic_ext.extensions.openapi import constants

from classes import App, AppConfig, Request
from chess_bp import chess_blueprint as chessBp
from login import login
from misc import misc

import models

load_dotenv()

ISDEV = bool(os.getenv("DEV")) or (os.getenv("GITHUB_CODESPACE_TOKEN") and True)

repo = git.Repo(search_parent_directories=True)
sha = repo.head.object.hexsha

app = App("CheckmateBackend")

app.extend(config=AppConfig(
    oas=True,
    oas_autodoc=True,
    oas_ui_default="swagger",
    swagger_ui_configuration={"apisSorter": "alpha", "operationsSorter": "alpha", "docExpansion": "list"},

    cors_origins=[
        re.compile(r"^https://(.*)ultras-playroom\.xyz"), # main domain
        re.compile(r"https://chess-app-frontend-?(.*)-ultrasonic1209\.vercel\.app"), # vercel previews
        re.compile(r"https://tauri\.localhost"), # tauri demo
        re.compile(r"https://ultrasonic1209-(.*)\.githubpreview\.dev") # gh codespace web previews
    ], # re.compile(r"^((.*)ultras-playroom\.xyz)|(tauri\.localhost)")
    cors_supports_credentials=True,
    cors_allow_headers=["content-type"],
    cors_always_send=True,
    cors_max_age=48
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

app.ext.openapi.add_security_scheme(
    "JWT",
    name=".CHECKMATESECRET",
    type=constants.SecuritySchemeType.API_KEY,
    location=constants.SecuritySchemeLocation.COOKIE,
    description="JWT containing user id, secret, and expiry"
)

app.blueprint((
    login,
    chessBp,
    misc
))

sqlpass = os.getenv("SQL_PASSWORD", "")

bind = create_async_engine(
    f"mysql+asyncmy://checkmate:{sqlpass}@server.ultras-playroom.xyz/checkmate",
    echo=ISDEV,
    pool_pre_ping=True,
)

app.config.SECRET = os.getenv("JWT_SECRET", "")
app.config.FC_SECRET = os.getenv("FRIENDLY_CAPTCHA_SECRET", "")

if not ISDEV:
    app.config.FORWARDED_SECRET = os.getenv("FORWARDED_SECRET", "")

_base_model_session_ctx = ContextVar("session")

@app.middleware("request")
async def inject_session(request: Request):
    """
    Adds a SQL session to the request's context
    From https://sanic.dev/en/guide/how-to/orm.html#sqlalchemy
    """
    request.ctx.session = sessionmaker(bind, AsyncSession, expire_on_commit=False)()
    request.ctx.session_ctx_token = _base_model_session_ctx.set(request.ctx.session)


@app.middleware("response")
async def close_session(request: Request, response):
    """
    Cleans the SQL session up
    From https://sanic.dev/en/guide/how-to/orm.html#sqlalchemy
    """
    if hasattr(request.ctx, "session_ctx_token"):
        _base_model_session_ctx.reset(request.ctx.session_ctx_token)
        await request.ctx.session.close()

@app.get("/sql")
async def sql(request: Request):
    """
    lists all tables.
    TODO https://docs.sqlalchemy.org/en/14/tutorial/metadata.html
    """
    session: AsyncSession = request.ctx.session

    async with session.begin():
        conn: AsyncConnection = await session.connection()

        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    return json(tables)

@app.patch("/sql/initalise")
async def sql_initalise(request: Request):
    """
    resets the database.

    openapi:
    ---
    parameters:
      - name: x-admin-key
        in: header
        description: This needs to be correct.
        required: true
    """
    auth = request.headers.get("x-admin-key")

    if auth != "***REMOVED***":
        return text("hint: first name, capital S", status=401)

    session: AsyncSession = request.ctx.session
    async with session.begin():
        conn: AsyncConnection = await session.connection()

        await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)

        user = models.User()

        user.username = "bar"
        user.password = "ha"
        user.email = "email@example.com"

        countup = models.GameTimer()
        countup.timer_name = "Countup"

        countdown = models.GameTimer()
        countdown.timer_name = "Countdown"

        session.add_all([
            user,
            countup,
            countdown
        ])

    assert user.password == "ha"

    return text("done!")

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

app.static('/static', './static')
app.static("/favicon.ico", "./static/favicon.ico", name="favicon")

if __name__ == '__main__':
    app.run( # app.make_coffee is also a thing somehow lol
        host='0.0.0.0',
        port=6969,
        fast=True,
        auto_reload=(not ISDEV), # crashed my codespace
        debug=ISDEV,
        access_log=ISDEV,
    )
