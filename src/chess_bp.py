"""
Will handle everything related to chess games.
"""
import chess
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
      - name: move
        in: query
        description: the move you want to make (UCI format)
        required: true
    """

    move = request.args.get("move")

    board = chess.Board()
    board.push_uci(move)

    return text(str(board))
