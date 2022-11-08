"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

from datetime import datetime, timedelta
import email.errors
from email.headerregistry import Address
from statistics import mode
from typing import List, Optional

import jwt

from sanic import Blueprint, json
from sanic_ext import validate, openapi

from sqlalchemy import select
from sqlalchemy.sql.expression import Select, or_
from sqlalchemy.engine import Result
from sqlalchemy.sql.functions import count
from sqlalchemy import exc

from auth import is_logged_in, has_session
from captcha import validate_request_captcha
from classes import (
    Message,
    MessageWithAccept,
    Request,
    LoginBody,
    LoginResponse,
    SignupBody,
    SignupResponse,
    StatsResponse,
    UpdateBody,
    UpdateResponse,
)

import models

user_bp = Blueprint("user", url_prefix="/user")


@user_bp.post("/login")
@openapi.body(LoginBody)
@openapi.response(
    status=200,
    content={"application/json": LoginResponse},
    description="When a valid login attempt is made",
)
@validate(json=LoginBody, body_argument="params")
@validate_request_captcha(success_facing_message="Signed you in! Redirecting...")
@has_session()
async def do_login(
    request: Request,
    params: LoginBody,
    user_facing_message: str,
    user: models.User,
    session: models.Session,
):
    """
    Assigns JSON Web Token
    Captcha is provided by https://friendlycaptcha.com/
    """

    if session.user:
        return json({"accept": False, "message": "You are already logged in!"})

    query_session = request.ctx.session

    username = params.username
    password = params.password

    stmt = select(models.User).where(models.User.username == username)

    async with query_session.begin():
        resp: Result = await query_session.execute(stmt)

        user: Optional[models.User] = resp.scalar_one_or_none()

        if user is None:
            # account not found
            return json({"accept": False, "message": "Invalid username or password."})

        if user.password != password:
            # password incorrect
            return json({"accept": False, "message": "Invalid username or password."})

        # user is authenticated

        user.sessions.append(session)

    expires = (
        (datetime.now() + timedelta(weeks=4)).timestamp() if params.rememberMe else None
    )

    payload = {"user_id": user.user_id, "session": session.session, "expires": expires}

    response = json(
        {"accept": True, "message": user_facing_message, "profile": user.to_dict()}
    )

    token = jwt.encode(payload, request.app.config.SECRET)

    response.cookies[".CHECKMATESECRET"] = token

    if params.rememberMe:
        response.cookies[".CHECKMATESECRET"]["expires"] = datetime.fromtimestamp(
            expires
        )

    # the rest of the cookie params are set by the has_session() decorator

    return response


@user_bp.delete("/logout")
@is_logged_in(silent=True)
async def do_logout(request: Request, user: models.User, session: models.Session):
    """
    Removes JSON Web Token and destroys the session (if there are zero games associated with it).
    """
    query_session = request.ctx.session

    if len(session.players) == 0:

        async with query_session.begin():
            await query_session.delete(session)

        response = json({"success": True})
        del response.cookies[".CHECKMATESECRET"]
    else:

        async with query_session.begin():
            session.user = None

        response = json({"success": True})

    return response


@user_bp.get("/identify")
@is_logged_in(silent=True)
async def identify(request: Request, user: models.User, session: models.Session):
    """
    Returns the profile you are authenticating as.
    """

    return json(user.to_dict())


@user_bp.post("/new")
@openapi.body(SignupBody)
@openapi.response(
    status=200,
    content={"application/json": SignupResponse},
    description="When an account is made",
)
@openapi.response(status=400, content={"application/json": MessageWithAccept})
@validate(json=SignupBody, body_argument="params")
@validate_request_captcha(success_facing_message="Please log into your new account.")
@has_session()
async def new_user(
    request: Request,
    params: SignupBody,
    user: models.User,
    session: models.Session,
    user_facing_message: str,
):
    """
    Creates a new user.
    Uses the same captcha as /user/login
    """

    if session.user:
        return json(
            {"accept": False, "message": "Sign out before creating a new account."}
        )

    query_session = request.ctx.session
    try:
        async with query_session.begin():
            user = models.User() # see diagram at top of Classes/OOP section of documentation

            # params is the parsed HTTP POST body, as a Python dataclass
            # the username and password has to be set to this

            user.username = params.username
            user.password = params.password

            try:
                # python has a module for handling email, i see no reason why i can't use it
                # if the email field isnt blank then attempt to parse, else null the field in the database
                user.email = (
                    str(Address(addr_spec=params.email)) if params.email != "" else None
                )
            except email.errors.InvalidHeaderDefect: # it even has its own exceptions for error handling!
                return json(
                    {"accept": False, "message": "An invalid email was provided."},
                    status=400,
                )

            # now that the user object has been created, instruct the ORM to add it to the database
            query_session.add(user)
            # changes will apply when the query_session is exited
    except exc.IntegrityError: # if username unique constraint is not fulfilled
        return json(
            {
                "accept": False,
                "message": "An account with this username already exists or you have provided invalid information.",
            },
            status=400,
        )

    # await query_session.refresh(user)

    # session.user = user

    return json({"accept": True, "message": user_facing_message})


@user_bp.patch("/update")
@openapi.body(UpdateBody)
@openapi.response(
    status=200,
    content={"application/json": UpdateResponse},
    description="User was updated sucessfully.",
)
@openapi.response(status=400, content={"application/json": Message})
@openapi.response(
    status=401,
    content={"application/json": Message},
    description='"old_password" was incorrect.',
)
@validate(json=UpdateBody, body_argument="params")
@is_logged_in()
async def user_update(
    request: Request, user: models.User, session: models.Session, params: UpdateBody
):
    """
    Updates user information.
    """

    query_session = request.ctx.session

    async with query_session.begin():
        if user.password != params.old_password:
            return json({"message": "Incorrect password."}, status=401)

        if params.new_password:
            # await query_session.refresh(user, ["sessions"])

            user.password = params.new_password
            user.sessions = [session]

        if params.new_email:
            try:
                user.email = str(Address(addr_spec=params.new_email))
            except email.errors.InvalidHeaderDefect:
                await query_session.rollback()
                return json({"message": "Invalid email."}, status=400)

    return json({"message": "Success!", "profile": user.to_dict()})


@user_bp.get("/stats")
@openapi.response(
    status=200,
    content={"application/json": StatsResponse},
    description="The requesting user/session's stats",
)
@has_session()
async def user_stats(request: Request, user: models.User, session: models.Session):
    """
    Responds with statistics about the session or user using this endpoint.
    """

    def get_player(game: models.Game):
        """
        Returns the user's player in this game.
        """
        # "next" takes a given iterator and returns the next item in that iterator
        # in this usecase we're just getting the only item in the iterator
        return next(
            # filters the game's list of players
            # remove players that DO have the requesting session (or user)'s id
            # returns an iterator containing a single player
            filter(
                lambda player: (player.user_id == (user.user_id if user else -1))
                or (player.session_id == session.session_id),
                game.players, 
            ),
            None,
        )

    def get_opponent(game: models.Game):
        """
        Returns the opposing user's player in this game.
        """
        # "next" takes a given iterator and returns the next item in that iterator
        # in this usecase we're just getting the only item in the iterator
        return next(
            # filters the game's list of players
            # remove players that do NOT have the requesting session (or user)'s id
            # returns an iterator containing a single player
            filter(
                lambda player: (player.user_id != (user.user_id if user else -1))
                and (player.session_id != session.session_id),
                game.players,
            ),
            None,
        )

    # remove duplicates in the queries that may occur as a result of using the two subqueries in an "or"
    # (the cartesian product is unavoidable in this case)

    query_game_amount: Select = select(count(models.Game.game_id)) # SELECT COUNT(`Game`.*)
    query_game_amount = query_game_amount.distinct() 

    query_games: Select = select(models.Game) # SELECT `Game`.*
    query_games = query_games.distinct()

    # get the player's user_id where the user corresponds to the requesting session/user
    # and also where the player's game id is equal to the game's id
    query_users_games: Select = (
        select(models.Player.user_id)
        .where(models.Player.user == user)
        .where(models.Player.game_id == models.Game.game_id)
    )

    # get the player's session_id where the session corresponds to the requesting session
    # and also where the player's game id is equal to the game's id
    query_session_games: Select = (
        select(models.Player.session_id)
        .where(models.Player.session == session)
        .where(models.Player.game_id == models.Game.game_id)
    )

    if user: # set the query to use both subqueries with an OR operator if the requesting session has a user
        exp = or_(
                models.User.__table__.columns.user_id.in_(query_users_games),
                models.Session.__table__.columns.session_id.in_(query_session_games),
            )
    else: # if not, just use the session subquery
        exp = models.Session.__table__.columns.session_id.in_(query_session_games)

    # update the main queries with the given subquery/subqueries
    query_games = query_games.where(exp)
    query_game_amount = query_game_amount.where(exp)

    query_session = request.ctx.session

    async with query_session.begin():
        game_result_amount: Result = await query_session.execute(query_game_amount) # execute query_game_amount, save result to game_result_amount
        game_result: Result = await query_session.execute(query_games) # execute query_games, save result to game_result

    game_results: List[models.Game] = game_result.scalars().all() # represent games_result as a list of ORM Game objects

    games_played: int = game_result_amount.scalar_one() # represent game_result_amount as an integer showing the number of games played

    games_won = list(
        filter(
            lambda game: get_player(game).is_white == game.white_won,
            game_results # from the list of game results, remove those that the user did not win
        )
    )

    # from the list of game results, remove those that the user was playing black in
    games_played_black = list(
        filter(
            lambda game: get_player(game).is_white is False,
            game_results,
        )
    )

    # from the list of game results, "filter" out those that the user was playing white in
    games_played_white = list(
        filter(
            lambda game: get_player(game).is_white is True,
            game_results,
        )
    )

    # get all opponents to all the games that the player has played, then
    # "filter" out the opponents belonging to games that have none (remove all of the None entries)
    opponents = tuple(filter(None, (get_opponent(game) for game in game_results)))

    # gets the most common opponent in the opponents list
    opponent = (
        mode(opponents) if opponents else None
    )  # checks if empty, tuples/lists evalulate to False if they are

    return json({
        "games_played": games_played,
        "games_won": len(games_won),
        "percentage_of_playing_white": (len(games_played_white) / games_played * 100) if games_played else 0,  # to stop zero division errors
        "favourite_opponent": opponent.to_dict_generalised() if opponent else None,
    })
