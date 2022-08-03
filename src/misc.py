"""
Misc things that don't fit in anywhere else
"""
import asyncio
from sanic import Blueprint, text, json
from sanic.log import logger

from classes import Request

misc = Blueprint("misc", url_prefix="/misc")

@misc.get("eyep")
async def eyep(request: Request):
    """
    eyep
    """
    return json({
        "ip": request.remote_addr
    })

@misc.patch("update")
async def git_update(request: Request):
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

    logger.warning(f"Update request from {request.remote_addr}")

    proc = await asyncio.create_subprocess_exec(
        'git', 'pull',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    await proc.communicate()

    return_code = proc.returncode

    return text(f"return code {return_code}")
    