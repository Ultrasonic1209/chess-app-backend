"""
From https://sanic.dev/en/guide/how-to/authentication.html#login.py
Captcha process influenced by
https://github.com/FriendlyCaptcha/friendly-captcha-examples/blob/main/nextjs/pages/api/submitBasic.js
"""

import email.errors
from datetime import datetime, timedelta
from email.headerregistry import Address
from statistics import mode

import jwt
from sanic import Blueprint, json
from sanic_ext import openapi, validate
from sqlalchemy import exc, select
from sqlalchemy.sql.expression import or_
from sqlalchemy.sql.functions import count

import models
from auth import has_session, is_logged_in
from captcha import validate_request_captcha
from classes import (
    LoginBody,
    LoginResponse,
    Message,
    MessageWithAccept,
    Request,
    SignupBody,
    SignupResponse,
    StatsResponse,
    UpdateBody,
    UpdateResponse,
)


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

    if user:
        return json({"accept": False, "message": "You are already logged in!"})

    query_session = request.ctx.session

    username = params.username
    password = params.password

    stmt = select(models.User).where(models.User.username == username)

    async with query_session.begin():
        resp = await query_session.execute(stmt)

        resp_user = resp.scalar_one_or_none()

        if resp_user is None:
            # account not found
            return json({"accept": False, "message": "Invalid username or password."})

        if resp_user.password != password:
            # password incorrect
            return json({"accept": False, "message": "Invalid username or password."})

        # user is authenticated

        resp_user.sessions.append(session)

    expires = (
        (datetime.now() + timedelta(weeks=4)).timestamp() if params.rememberMe else None
    )

    payload = {
        "user_id": resp_user.user_id,
        "session": session.session,
        "expires": expires,
    }

    response = json(
        {"accept": True, "message": user_facing_message, "profile": resp_user.to_dict()}
    )

    token = jwt.encode(payload, request.app.config.SECRET)

    response.cookies[".CHECKMATESECRET"] = token

    if expires:
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
            user = (
                models.User()
            )  # see diagram at top of Classes/OOP section of documentation

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
            except (
                email.errors.InvalidHeaderDefect
            ):  # it even has its own exceptions for error handling!
                return json(
                    {"accept": False, "message": "An invalid email was provided."},
                    status=400,
                )

            # now that the user object has been created, instruct the ORM to add it to the database
            query_session.add(user)
            # changes will apply when the query_session is exited
    except exc.IntegrityError:  # if username unique constraint is not fulfilled
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

    query_game_amount = select(
        count(models.Game.game_id)
    )  # SELECT COUNT(`Game`.game_id)

    query_games = select(models.Game)  # SELECT `Game`.*

    # get all game ids that the requesting user is participating in
    query_users_game_ids = select(models.Player.game_id).where(
        models.Player.user == user
    )

    # get all game ids that the requesting session is participating in
    query_session_game_ids = select(models.Player.game_id).where(
        models.Player.session == session
    )

    if (
        user
    ):  # set the query to use both subqueries with an OR operator if the requesting session has a user
        exp = or_(
            models.Game.__table__.columns.game_id.in_(query_session_game_ids),
            models.Game.__table__.columns.game_id.in_(query_users_game_ids),
        )
    else:  # if not, just use the session subquery
        exp = models.Game.__table__.columns.game_id.in_(query_session_game_ids)

    # update the main queries with the given subquery/subqueries
    query_games = query_games.where(exp)
    query_game_amount = query_game_amount.where(exp)

    query_session = request.ctx.session

    async with query_session.begin():
        # execute query_game_amount, save result to game_result_amount
        game_result_amount = await query_session.execute(query_game_amount)
        # execute query_games, save result to game_result
        game_result = await query_session.execute(query_games)

    # represent games_result as a list of ORM Game objects
    game_results = game_result.scalars().all()

    # represent game_result_amount as an integer showing the number of games played
    games_played = game_result_amount.scalar_one()

    games_won = list(
        filter(
            lambda game: getattr(get_player(game), "is_white", None) == game.white_won,
            game_results,  # from the list of game results, remove those that the user did not win
        )
    )

    # from the list of game results, "filter" out those that the user was playing black in
    list(
        filter(
            lambda game: getattr(get_player(game), "is_white", None) is False,
            game_results,
        )
    )

    # from the list of game results, "filter" out those that the user was playing white in
    games_played_white = list(
        filter(
            lambda game: getattr(get_player(game), "is_white", None) is True,
            game_results,
        )
    )

    # get all opponents to all the games that the player has played, then
    # "filter" out the opponents belonging to games that have none (remove all of the None entries)
    opponents = tuple(filter(None, (get_opponent(game) for game in game_results)))

    # gets the most common opponent in the opponents list
    opponent = (
        mode(opponents) if opponents else None
    )  # checks if empty, tuple/list objects evaluate to False if they are

    return json(
        {
            "games_played": games_played,
            "games_won": len(games_won),
            # to stop zero division errors
            "percentage_of_playing_white": (
                len(games_played_white) / games_played * 100
            )
            if games_played
            else 0,
            "favourite_opponent": opponent.to_dict_generalised() if opponent else None,
        }
    )
