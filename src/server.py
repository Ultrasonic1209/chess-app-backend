#pylint: disable=unused-argument,missing-module-docstring,multiple-imports,c-extension-no-member

import sanic, sanic.response, ujson, os
from sanic import Sanic
from sanic.response import json

from sanic_ext import Config

app = Sanic("CheckmateBackend")

app.extend(config=Config(
    oas=True,
    oas_autodoc=True,
    oas_ui_default="swagger",
))

@app.middleware('response')
async def add_json(request: sanic.Request, response: sanic.response.HTTPResponse):
    if response.content_type == "application/json":
        parsed = ujson.loads(response.body)

        parsed["chess"] = "cool"

        new_response = json(parsed, status=response.status, headers=response.headers)

        return new_response
    else:
        return None

@app.get("/")
@app.route('/<path:path>')
async def index(request, path=""):
    return json({"message": "Hello, world.", "path": path})

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=8080,
        fast=True,
        dev=bool(os.environ.get("CODESPACES", False))
    )
