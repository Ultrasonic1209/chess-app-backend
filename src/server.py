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

    cors_origins=re.compile(r"^(.*)ultras-playroom\.xyz"),
    cors_supports_credentials=True,
    cors_allow_headers=["content-type"],
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

sqlpass = os.getenv("SQL_PASSWORD", "")

bind = create_async_engine(
    f"mysql+asyncmy://checkmate:{sqlpass}@server.ultras-playroom.xyz/checkmate",
    echo=True
)

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
    conn: AsyncConnection = await session.connection()

    tables = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).get_table_names()
    )
    return json(tables)


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
    app.run( # app.make_coffee is also a thing somehow lol
        host='0.0.0.0',
        port=6969,
        fast=True,
        auto_reload=(not ISDEV), # crashed my codespace
        debug=ISDEV,
        access_log=True,
    )
