"""
Will handle everything related to chess games.
"""
import datetime

import chess
import chess.pgn
from sanic import Blueprint, Request, text, json

chess_blueprint = Blueprint("chess", url_prefix="/chess")

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
