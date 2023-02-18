"""
Will handle everything related to chess games.
"""
import random
from io import StringIO
from typing import List, Optional

import arrow
import chess
import chess.pgn

from sanic import Blueprint
from sanic.response import empty, json

# from sanic.log import logger
from sanic_ext import openapi, validate
from sqlalchemy import or_, select
from sqlalchemy.sql.expression import Select

import models
from auth import has_session
from classes import (
    ChessEntry,
    GetGameOptions,
    Message,
    NewChessGameOptions,
    NewChessGameResponse,
    NewChessMove,
    PublicChessGameResponse,
    Request,
)

chess_blueprint = Blueprint("chess", url_prefix="/chess")


def strtobool(val: str):
    """
    Taken from the now deprecated `distutils.util` module.

    Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError(f"invalid truth value {val}")


def get_player_team(game: models.Game, session: models.Session, user: models.User):
    """
    Checks if a user is already in a game.
    """

    for player in game.players:
        if ((session is not None) and (session == player.session)) or (
            (user is not None) and (user == player.user)
        ):
            return player.is_white
    return None


@chess_blueprint.get("/get-games")
@openapi.parameter("my_games", bool, required=True)
@openapi.parameter("page_size", int, required=True)
@openapi.parameter("page", int, required=True)
@openapi.response(
    status=200, content={"application/json": List[PublicChessGameResponse]}
)
@validate(query=GetGameOptions, query_argument="options")
@has_session()
async def get_games(
    request: Request,
    options: GetGameOptions,
    user: models.User,
    session: models.Session,
):
    """
    Lets users get a list of online games
    """

    # issue with parsing of options unfortunately
    options = dict(request.query_args)

    # get all game ids that the requesting user is participating in
    query_users_game_ids: Select = select(models.Player.game_id).where(
        models.Player.user == user
    )

    # get all game ids that the requesting session is participating in
    query_session_game_ids: Select = select(models.Player.game_id).where(
        models.Player.session == session
    )

    stmt: Select = select(models.Game)

    # limits the database response size to what the requesting client wants.
    # in order to give the the impression of pagination, offset will also be used
    # to move the database cursor along based off of the given page size.
    stmt = stmt.limit(int(options["page_size"])).offset(
        int(options["page"]) * int(options["page_size"])
    )

    if bool(strtobool(options["my_games"])) is True:
        if (
            user
        ):  # set the query to use both subqueries with an OR operator if the requesting session has a user
            exp = or_(
                models.Game.__table__.columns.game_id.in_(query_session_game_ids),
                models.Game.__table__.columns.game_id.in_(query_users_game_ids),
            )
        else:  # if the session does not have a user, just use the session subquery
            exp = models.Game.__table__.columns.game_id.in_(query_session_game_ids)

        stmt = stmt.where(exp)

    query_session = request.ctx.session

    async with query_session.begin():
        game_result = await query_session.execute(stmt)

    games = game_result.scalars().all()

    async def process_game(game: models.Game) -> PublicChessGameResponse:
        """
        Sets the `is_white` flag for games.
        """
        await game.hospice()

        dictgame = game.to_dict()

        dictgame["is_white"] = get_player_team(game=game, session=session, user=user)
        return dictgame

    formattedgames: List[PublicChessGameResponse] = [
        await process_game(game) for game in games
    ]

    return json(formattedgames)


@chess_blueprint.post("/game")
@openapi.body(NewChessGameOptions)
@openapi.response(status=201, content={"application/json": NewChessGameResponse})
@validate(json=NewChessGameOptions, body_argument="options")
@has_session()
async def create_game(
    request: Request,
    options: NewChessGameOptions,
    user: models.User,
    session: models.Session,
):
    """
    Creates a chess game in the database, being logged in is optional
    """
    query_session = request.ctx.session

    gtstmt: Select = select(models.GameTimer).where(
        models.GameTimer.timer_name
        == ("Countdown" if options.countingDown else "Countup")
    )

    async with query_session.begin():
        game_timer_result = await query_session.execute(gtstmt)

        game_timer = game_timer_result.scalar_one_or_none()

        if not game_timer:
            return json(
                {"message": "[SERVER ERROR] game type was not found"}, status=500
            )

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
async def get_game(
    request: Request, gameid: int, user: models.User, session: models.Session
):
    """
    Retrieves game status
    """

    query_session = request.ctx.session

    async with query_session.begin():
        game: Optional[models.Game] = await query_session.get(
            models.Game, gameid, populate_existing=True
        )

        if game is None:
            return json({"message": "game does not exist"}, status=404)

        is_white = get_player_team(game=game, session=session, user=user)

        await game.hospice()

    gamedict = PublicChessGameResponse(**game.to_dict(), is_white=is_white)

    return json(gamedict)


@chess_blueprint.patch("/game/<gameid:int>/enter")
@openapi.body(ChessEntry)
@openapi.response(status=204)
@openapi.response(status=401, content={"application/json": Message})
@openapi.response(status=404, content={"application/json": Message})
@validate(json=ChessEntry, body_argument="params")
@has_session()
async def enter_game(
    request: Request,
    gameid: int,
    params: ChessEntry,
    user: models.User,
    session: models.Session,
):
    """
    If someone wants to enter a game, they need only use this endpoint.
    """
    wants_white = (
        bool(random.getrandbits(1)) if params.wantsWhite is None else params.wantsWhite
    )

    query_session = request.ctx.session

    async with query_session.begin():
        game: Optional[models.Game] = await query_session.get(
            models.Game, gameid, populate_existing=True
        )

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

            pgn = chess.pgn.Game(
                {
                    "Event": "Checkmate Chess Game",
                    "Site": "chessapp.ultras-playroom.xyz",
                    "Date": time.strftime(r"%Y.%m.%d"),
                    "Round": 1,
                    "White": white.user.username if white.user else "Anonymous",
                    "Black": black.user.username if black.user else "Anonymous",
                    "Result": "*",
                    # "Annotator": "Checkmate",
                    # PlyCount
                    # TimeControl
                    "Time": time.strftime(r"%H:%M:%S"),
                    "Termination": "unterminated",
                    "Mode": "ICS",
                    # FEN
                }
            )

            exporter = chess.pgn.StringExporter(
                headers=True, variations=True, comments=True
            )
            pgn_string = pgn.accept(exporter)

            game.time_started = time
            game.game = pgn_string

    response = empty()

    return response


@chess_blueprint.patch("/game/<gameid:int>/move")
@openapi.body(NewChessMove)
@openapi.response(
    status=200,
    content={"application/json": PublicChessGameResponse},
    description="The updated chess game",
)
@openapi.response(status=400, content={"application/json": Message})
@openapi.response(status=401, content={"application/json": Message})
@openapi.response(status=404, content={"application/json": Message})
@validate(json=NewChessMove, body_argument="params")
@has_session(create=False)
async def make_move(
    request: Request,
    gameid: int,
    params: NewChessMove,
    user: models.User,
    session: models.Session,
):
    """
    lets players play!
    """
    query_session = request.ctx.session

    async with query_session.begin():
        game: Optional[models.Game] = await query_session.get(
            models.Game, gameid, populate_existing=True
        )

        if game is None:
            return json({"message": "game does not exist"}, status=404)

        if game.time_started is None:
            return json({"message": "game has not started"}, status=400)

        if game.time_ended is not None:
            return json({"message": "game is over"}, status=400)

        playeriswhite = get_player_team(game=game, session=session, user=user)

        if playeriswhite is None:
            return json({"message": "you are not playing this game"}, status=401)

        chessgame = chess.pgn.read_game(StringIO(game.game))

        if chessgame is None:
            return json({"message": "failed to read game data. uh oh"}, status=500)

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
            if game.timeLimit is None:
                return json(
                    {"message": "countdown games should have a time limit...\nuh oh."},
                    status=500,
                )

            times = []
            for node in chessgame.mainline():
                clock = node.clock()

                if clock is None:
                    return json(
                        {
                            "message": "failed to read move data. uh oh.",
                            "move": repr(node),
                        },
                        status=500,
                    )

                times.append(clock - game.timeLimit)

            white = 0
            black = 0

            last_time = game.timeLimit

            is_white = True

            for time in times:
                if is_white:
                    white += last_time - time
                else:
                    black += last_time - time
                last_time = time
                is_white = not is_white

            time_moving = white + black

            white = game.timeLimit - white
            black = game.timeLimit - black

            # if len(times) == 0:
            #    white = game.timeLimit
            #    black = game.timeLimit

            if chessgame.turn() == chess.WHITE:
                white -= seconds_since_start - time_moving
            elif chessgame.turn() == chess.BLACK:
                black -= seconds_since_start - time_moving

            if white <= 0:
                await request.respond(
                    json(
                        {
                            "message": "white ran out of time before your request reached the server"
                        }
                    )
                )

                return await game.hospice()
            elif black <= 0:
                await request.respond(
                    json(
                        {
                            "message": "black ran out of time before your request reached the server"
                        }
                    )
                )

                return await game.hospice()

            chessgame.end().add_line([move])
            chessgame.end().set_clock((game.timeLimit * 2) - seconds_since_start)

            # return json({"message": f"white has {white} seconds remaining\nblack has {black} seconds remaining"}, status=501)
        else:
            chessgame.end().add_line([move])
            chessgame.end().set_clock(seconds_since_start)

        await game.hospice(chessgame, force_save=True)

    # ** operator unpacks the dictionary into arguments
    # i can use this along with the is_white kwarg to easily build a response to
    # this request.
    gamedict = PublicChessGameResponse(**game.to_dict(), is_white=playeriswhite)

    return json(gamedict)
