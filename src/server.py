#pylint: disable=unused-argument,missing-module-docstring,c-extension-no-member,logging-fstring-interpolation

import asyncio
import os
import chess
import sanic
import sanic.response
import ujson
from sanic import Sanic
from sanic.response import json, text
from sanic.log import logger

from sanic_ext import Config

ISDEV = bool(os.environ.get("DEV", False))

app = Sanic("CheckmateBackend")

app.extend(config=Config(
    oas=True,
    oas_autodoc=True,
    oas_ui_default="swagger",
))

if not ISDEV:
    app.config.FORWARDED_SECRET = "secretsAreOverrated" # 10/10 secret

@app.middleware('response')
async def add_json(request: sanic.Request, response: sanic.response.HTTPResponse):
    """
    Adds my boilerplate JSON to any response JSON
    """
    if response.content_type == "application/json":
        parsed = ujson.loads(response.body)

        parsed["chess"] = "cool"

        new_response = json(parsed, status=response.status, headers=response.headers)

        return new_response

@app.get("/")
async def index(request: sanic.Request):
    """
    we all gotta start somewhere
    """
    return json({"message": "Hello, world.", "docs": "/docs"})

@app.get("/chess")
async def chess_board(request: sanic.Request):
    """
    returns a starter board
    """

    board = chess.Board()

    return text(str(board))

@app.get("/chess2")
async def chess_moves(request: sanic.Request):
    """
    returns a list of moves for the starter board
    """

    board = chess.Board()

    return json({"moves": [move.uci() for move in board.legal_moves]})

@app.get("/chess3")
async def chess_move(request: sanic.Request):
    """
    take a chess board, and make a move

    openapi:
    ---
    parameters:
      - name: move
        in: query
        description: the move you want to make (UCI format)
        required: true
    """

    move = request.args.get("move")

    board = chess.Board()
    board.push_uci(move)

    return text(str(board))

@app.patch("update")
async def git_update(request: sanic.Request):
    """
    Pulls from GitHub. Sanic's auto-reload should do the rest.

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

    logger.warning(f"Update request from {request.ip}")

    proc = await asyncio.create_subprocess_exec(
        'git', 'pull',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    await proc.communicate()

    return_code = proc.returncode

    return text(f"return code {return_code}")

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=6969,
        fast=True,
        auto_reload=True,
        debug=ISDEV,
        access_log=ISDEV,
    )
