"""
Will handle everything related to chess games.
"""
import datetime

import chess
import chess.pgn
import jwt
from sanic import Blueprint, text, json

from sqlalchemy.ext.asyncio import AsyncSession

from classes import Request
from auth import authenticate_request
from login import get_hostname
import models

chess_blueprint = Blueprint("chess", url_prefix="/chess")

@chess_blueprint.post("/create-game")
async def create_game(request: Request):
    """
    Creates a chess game in the database, being logged in is optional
    """
    query_session: AsyncSession = request.ctx.session
    user, session = await authenticate_request(request=request)

    toadd = []

    if (user is None) and (session is None):
        session = models.Session()
        toadd.append(session)

    player = models.Player()
    player.is_white = True

    if user:
        player.user_id = user.user_id
    else:
        player.session_id = session.session_id

    game = models.Game()
    game.players.append(player)

    toadd.extend([player, game])

    async with query_session.begin():
        query_session.add_all(toadd)

    response = json(dict(game_id=game.game_id))

    if len(toadd) > 2:
        payload = {
            'user_id': None,
            'session': session.session_id,
            'expires': None
        }

        token = jwt.encode(payload, request.app.config.SECRET)

        response.cookies[".CHECKMATESECRET"] = token
        response.cookies[".CHECKMATESECRET"]["secure"] = True
        response.cookies[".CHECKMATESECRET"]["samesite"] = "Lax"
        response.cookies[".CHECKMATESECRET"]["domain"] = get_hostname(request.headers.get("host", ""))
        response.cookies[".CHECKMATESECRET"]["comment"] = "I'm in so much pain"

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
