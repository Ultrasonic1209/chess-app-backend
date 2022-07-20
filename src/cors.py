"""
Handles everything CORS.
From https://sanic.dev/en/guide/how-to/cors.html#cors.py
"""

from typing import Iterable
from sanic import Request
from sanic.response import HTTPResponse

def _add_cors_headers(response: HTTPResponse, methods: Iterable[str]) -> None:
    allow_methods = list(set(methods))
    if "OPTIONS" not in allow_methods:
        allow_methods.append("OPTIONS")
    headers = {
        "Access-Control-Allow-Methods": ",".join(allow_methods),
        "Access-Control-Allow-Origin": "chessapp.ultras-playroom.xyz *.chessapp.ultras-playroom.xyz",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": (
            "origin, content-type, accept, "
            "authorization"
        ),
    }
    response.headers.extend(headers)


def add_cors_headers(request: Request, response: HTTPResponse):
    """
    Adds CORS headers to all OPTIONS requests.
    """
    if request.method != "OPTIONS":
        methods = tuple(request.route.methods)
        _add_cors_headers(response, methods)
 