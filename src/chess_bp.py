"""
Will handle everything related to chess games.
"""
from dataclasses import dataclass
import datetime
import secrets
import random
from typing import Optional

import chess
import chess.pgn
import jwt

from sanic import Blueprint
from sanic.response import text, json, empty
#from sanic.log import logger
from sanic_ext import validate, openapi

from sqlalchemy.ext.asyncio import AsyncSession

from classes import PublicChessGame, Request, ChessEntry, NewChessGameResponse, NewChessGameOptions, Message

from auth import has_session, get_hostname

import models

chess_blueprint = Blueprint("chess", url_prefix="/chess")

@chess_blueprint.post("/game")
@openapi.body(NewChessGameOptions)
@openapi.response(status=201, content={"application/json": NewChessGameResponse})
@validate(json=dataclass(NewChessGameOptions))
@has_session()
async def create_game(request: Request, body: NewChessGameOptions, user: models.User, session: models.Session):
    """
    Creates a chess game in the database, being logged in is optional
    TODO make creation options work
    """
    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():

        if session is None: # no session = no user either
            session = models.Session()
            session.session = secrets.token_hex(32)

            async with query_session.begin_nested():
                query_session.add(session)

        player = models.Player()
        player.is_white = body.creatorStartsWhite

        player.user = user
        player.session = session if user is None else None

        game = models.Game()
        game.players.append(player)

        query_session.add_all([player, game])

    response = json(dict(game_id=game.game_id), status=201)

    if session.user is None: # userless session
        payload = {
            'user_id': None,
            'session': session.session,
            'expires': None
        }

        token = jwt.encode(payload, request.app.config.SECRET)

        response.cookies[".CHECKMATESECRET"] = token
        response.cookies[".CHECKMATESECRET"]["secure"] = True
        response.cookies[".CHECKMATESECRET"]["samesite"] = "Lax"
        response.cookies[".CHECKMATESECRET"]["domain"] = get_hostname(request.headers.get("host", ""))
        response.cookies[".CHECKMATESECRET"]["comment"] = "I'm in so much pain"

    return response

@chess_blueprint.get("/game/<gameid:int>")
@openapi.response(status=404, content={"application/json": Message})
@openapi.response(status=200, content={"application/json": PublicChessGame})
async def get_game(request: Request, gameid: int):
    """
    Retrieves game status
    """

    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():
        game: Optional[models.Game] = await query_session.get(models.Game, gameid, populate_existing=True)

        if game is None:
            return json({"message": "game does not exist"}, status=404)

    return json(game.to_dict())


@chess_blueprint.patch("/game/<gameid:int>/enter")
@openapi.body(ChessEntry)
@openapi.response(status=204)
@openapi.response(status=401, content={"application/json": Message})
@openapi.response(status=404, content={"application/json": Message})
@validate(json=dataclass(ChessEntry))
@has_session()
async def enter_game(request: Request, gameid: int, body: ChessEntry, user: models.User, session: models.Session):
    """
    If someone wants to enter a game, they need only use this endpoint.
    """
    wants_white = body.wantsWhite or bool(random.getrandbits(1))

    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():

        game: Optional[models.Game] = await query_session.get(models.Game, gameid, populate_existing=True)

        if game is None:
            return json({"message": "game does not exist"}, status=404)

        for player in game.players:
            if (player.user == user) or (player.session == session):
                return json({"message": "you are already in this game"}, status=401)

        if len(game.players) >= 2:
            return json({"message": "game cannot be joined"}, status=401)

        if await query_session.get(models.Player, (game.game_id, wants_white)):
            if body.wantsWhite is None:
                wants_white = not wants_white
            else:
                return json({"message": "colour is not available"}, status=401)

        player = models.Player()
        player.game = game

        player.user = user
        player.session = session if session.user is None else None

        player.is_white = wants_white

        query_session.add(player)

        if len(game.players) == 2:
            # start the game!

            time = datetime.datetime.now()

            white: models.Player
            black: models.Player

            for player in game.players:
                if player.is_white:
                    white = player
                else:
                    black = player

            pgn = chess.pgn.Game({
                "Event": "Checkmate Chess Game",
                "Site": "chessapp.ultras-playroom.xyz",
                "Date": time.strftime(r"%Y.%m.%d"),
                "Round": 1,
                "White": white.user.username if white.user else "Anonymous",
                "Black": black.user.username if black.user else "Anonymous",
                "Result": "*",

                "Annotator": "Checkmate",
                #PlyCount
                #TimeControl
                "Time": time.strftime(r"%H:%M:%S"),
                "Termination": "unterminated",
                "Mode": "ICS",
                #FEN
            })

            exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
            pgn_string = pgn.accept(exporter)

            game.time_started = time
            game.game = pgn_string


    response = empty()

    return response


@chess_blueprint.get("/starter")
async def chess_board(request: Request):
    """
    returns a starter board
    """

    board = chess.Board()

    return text(str(board))

@chess_blueprint.get("/starter-options")
async def chess_moves(request: Request):
    """
    returns a list of moves for the starter board
    """

    board = chess.Board()

    return json({"moves": [move.uci() for move in board.legal_moves]})

@chess_blueprint.patch("/starter-move")
async def chess_move(request: Request):
    """
    take a chess board, and make a move

    openapi:
    ---
    parameters:
      - in: query
        name: moves[]
        description: the moves you want to make (UCI format)
        required: true
        schema:
            type: array
            items:
                type: string
    """

    time = datetime.datetime.now()

    game = chess.pgn.Game({
        "Event": "Checkmate Chess Game",
        "Site": request.headers["origin"].replace("https://", ""),
        "Date": time.strftime(r"%Y.%m.%d"),
        "Round": 1,
        "White": "Surname, Forename",
        "Black": "Surname, Forename",
        "Result": "*",

        "Annotator": "Checkmate",
        #PlyCount
        #TimeControl
        "Time": time.strftime(r"%H:%M:%S"),
        "Termination": "unterminated",
        "Mode": "ICS",
        #FEN
    })

    movecount = 1
    for ucimove in request.args['moves[]']:
        game.end().add_line([chess.Move.from_uci(ucimove)], comment=f"comment here! move {movecount}").set_clock(3 * movecount)
        movecount += 1

    board = game.end().board()

    print(game)

    return text(str(board))
