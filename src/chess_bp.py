"""
Will handle everything related to chess games.
"""
from io import StringIO
import random
from typing import Optional
from distutils.util import strtobool

import chess
import chess.pgn

from sanic import Blueprint
from sanic.response import json, empty
#from sanic.log import logger
from sanic_ext import validate, openapi

import arrow

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.sql.expression import Select

from classes import PublicChessGameResponse, Request, ChessEntry, NewChessGameResponse, NewChessGameOptions, Message, NewChessMove, GetGameOptions

from auth import has_session

import models

chess_blueprint = Blueprint("chess", url_prefix="/chess")

def get_player_team(game: models.Game, session: models.Session, user: models.User):
    """
    Checks if a user is already in a game.
    """

    for player in game.players:
        if ((session is not None) and (session == player.session)) or ((user is not None) and (user == player.user)):
            return player.is_white
    return None

@chess_blueprint.get("/get-games")
@openapi.parameter("my_games", bool, required=True)
@openapi.parameter("page_size", int, required=True)
@openapi.parameter("page", int, required=True)
@validate(query=GetGameOptions, query_argument="options")
@has_session()
async def get_games(request: Request, options: GetGameOptions, user: models.User, session: models.Session):
    """
    Lets users get a list of online games
    """

    options = {item: value for (item, value) in request.query_args}

    stmt: Select = select(models.Game)

    stmt = stmt.limit(int(options["page_size"])).offset(int(options["page"]) * int(options["page_size"]))

    if bool(strtobool(options["my_games"])) is True:
        if user:
            stmt = stmt.where(or_(
                models.User.in_(
                    select(models.Player.session_id)
                    .where(models.Player.user == user)
                    .where(models.Player.game_id == models.Game.game_id)
                ),
                models.Session.__table__.columns.session_id.in_(
                    select(models.Player.session_id)
                    .where(models.Player.session == session)
                    .where(models.Player.game_id == models.Game.game_id)
                )
            ))
        else:
            stmt = stmt.where(models.Session.__table__.columns.session_id.in_(
                select(models.Player.session_id)
                .where(models.Player.session == session)
                .where(models.Player.game_id == models.Game.game_id)
            ))

    session: AsyncSession = request.ctx.session

    print(stmt.compile(session.bind))

    async with session.begin():
        game_result: Result = await session.execute(stmt)
        game_results = game_result.all()

    resp = [game["Game"].to_dict() for game in game_results]

    return json(resp)

    #return json({
    #    "myGames": options.myGames,
    #    "iveWon": options.iveWon,
    #    "imWhite": options.imWhite,
    #    "perPage": options.perPage,
    #    "page": options.page
    #})


@chess_blueprint.post("/game")
@openapi.body(NewChessGameOptions)
@openapi.response(status=201, content={"application/json": NewChessGameResponse})
@validate(json=NewChessGameOptions, body_argument="options")
@has_session()
async def create_game(request: Request, options: NewChessGameOptions, user: models.User, session: models.Session):
    """
    Creates a chess game in the database, being logged in is optional
    TODO make creation options work
    """
    query_session: AsyncSession = request.ctx.session

    gtstmt = select(models.GameTimer).where(
        models.GameTimer.timer_name == ("Countdown" if options.countingDown else "Countup")
    )

    async with query_session.begin():

        game_timer_result: Result = await query_session.execute(gtstmt)

        game_timer_row = game_timer_result.first()

        if not game_timer_row:
            return json({"message": "[SERVER ERROR] game type was not found"}, status=500)

        game_timer: models.GameTimer = game_timer_row["GameTimer"]

        player = models.Player()
        player.is_white = options.creatorStartsWhite

        player.user = user
        player.session = session if user is None else None

        game = models.Game()
        game.timer = game_timer
        game.timeLimit = options.timeLimit

        game.players.append(player)

        query_session.add_all([player, game])

    response = json(dict(game_id=game.game_id), status=201)

    return response

@chess_blueprint.get("/game/<gameid:int>")
@openapi.response(status=404, content={"application/json": Message})
@openapi.response(status=200, content={"application/json": PublicChessGameResponse})
@has_session()
async def get_game(request: Request, gameid: int, user: models.User, session: models.Session):
    """
    Retrieves game status
    """

    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():
        game: Optional[models.Game] = await query_session.get(models.Game, gameid, populate_existing=True)

        if game is None:
            return json({"message": "game does not exist"}, status=404)

        is_white = get_player_team(game=game, session=session, user=user)


    gamedict: PublicChessGameResponse = game.to_dict()

    gamedict["is_white"] = is_white

    return json(gamedict)


@chess_blueprint.patch("/game/<gameid:int>/enter")
@openapi.body(ChessEntry)
@openapi.response(status=204)
@openapi.response(status=401, content={"application/json": Message})
@openapi.response(status=404, content={"application/json": Message})
@validate(json=ChessEntry, body_argument="params")
@has_session()
async def enter_game(request: Request, gameid: int, params: ChessEntry, user: models.User, session: models.Session):
    """
    If someone wants to enter a game, they need only use this endpoint.
    """
    wants_white = bool(random.getrandbits(1)) if params.wantsWhite is None else params.wantsWhite

    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():

        game: Optional[models.Game] = await query_session.get(models.Game, gameid, populate_existing=True)

        if game is None:
            return json({"message": "game does not exist"}, status=404)


        if get_player_team(game=game, session=session, user=user) is not None:
            return json({"message": "you are already in this game"}, status=401)

        if len(game.players) >= 2:
            return json({"message": "game cannot be joined"}, status=401)

        if await query_session.get(models.Player, (game.game_id, wants_white)):
            if params.wantsWhite is None:
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

            time = arrow.now()

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

@chess_blueprint.patch("/game/<gameid:int>/move")
@openapi.body(NewChessMove)
@openapi.response(status=200, content={"application/json": PublicChessGameResponse}, description="The updated chess game")
@openapi.response(status=400, content={"application/json": Message})
@openapi.response(status=401, content={"application/json": Message})
@openapi.response(status=404, content={"application/json": Message})
@validate(json=NewChessMove, body_argument="params")
@has_session(create=False)
async def make_move(request: Request, gameid: int, params: NewChessMove, user: models.User, session: models.Session):
    """
    lets players play!
    """
    query_session: AsyncSession = request.ctx.session

    async with query_session.begin():

        game: Optional[models.Game] = await query_session.get(models.Game, gameid, populate_existing=True)

        if game is None:
            return json({"message": "game does not exist"}, status=404)

        if game.time_started is None:
            return json({"message": "game has not started"}, status=400)

        playeriswhite = get_player_team(game=game, session=session, user=user)

        if playeriswhite is None:
            return json({"message": "you are not playing this game"}, status=401)

        chessgame = chess.pgn.read_game(StringIO(game.game))

        chessboard = chessgame.end().board()

        whiteturn = chessgame.end().board().turn == chess.WHITE

        if playeriswhite != whiteturn:
            return json({"message": "not your turn"}, status=400)

        try:
            move = chessboard.parse_san(params.san)
        except ValueError:
            return json({"message": "invalid move"}, status=400)

        seconds_since_start = (arrow.now() - game.time_started).total_seconds()

        if game.timer.timer_name == "Countdown":

            times = []
            for node in chessgame.mainline():
                times.append(node.clock() - game.timeLimit)

            is_white = True
            white = 0
            black = 0

            last_time = game.timeLimit

            for time in times:

                if is_white:
                    white += last_time - time
                elif not is_white:
                    black += last_time - time
                last_time = time
                is_white = not is_white

            time_moving = white + black

            white = game.timeLimit - white
            black = game.timeLimit - black

            #if len(times) == 0:
            #    white = game.timeLimit
            #    black = game.timeLimit

            if chessgame.turn() == chess.WHITE:
                white -= seconds_since_start - time_moving
            elif chessgame.turn() == chess.BLACK:
                black -= seconds_since_start - time_moving

            if white <= 0:
                return json({"message": "white ran out of time"})
            elif black <= 0:
                return json({"message": "black ran out of time"})

            chessgame.end().add_line([move])
            chessgame.end().set_clock((game.timeLimit * 2) - seconds_since_start)

            #return json({"message": f"white has {white} seconds remaining\nblack has {black} seconds remaining"}, status=501)
        else:
            chessgame.end().add_line([move])
            chessgame.end().set_clock(seconds_since_start)

        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)

        pgn_string = chessgame.accept(exporter)

        game.game = pgn_string

    gamedict: PublicChessGameResponse = game.to_dict()
    gamedict["is_white"] = playeriswhite

    return json(game.to_dict())
