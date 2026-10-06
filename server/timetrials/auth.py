import hashlib
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request

from .extensions import db
from .models import ApiToken, LinkCode, User, utcnow

auth_bp = Blueprint("auth", __name__)

DISCORD_API = "https://discord.com/api/v10"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
EXPIRED_MESSAGE = "That link has expired. Request a new one in game."


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_code(length=8):
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def token_user():
    token = (request.args.get("token") or "").strip()
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:].strip()

    if not token:
        return None

    record = ApiToken.query.filter_by(token_hash=hash_token(token), revoked=False).first()

    if record is None:
        return None

    record.last_used_at = utcnow()
    db.session.commit()
    return record.user


def token_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = token_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401

        g.user = user
        return view(*args, **kwargs)

    return wrapper


def pending_link_code(code):
    record = db.session.get(LinkCode, code) if code else None
    if record is None or record.expired() or record.user_id is not None:
        return None

    return record


def upsert_user(profile):
    user = User.query.filter_by(discord_id=profile["id"]).first()
    username = profile.get("global_name") or profile.get("username") or profile["id"]

    if user is None:
        user = User(discord_id=profile["id"], username=username)
        db.session.add(user)

    user.username = username
    user.avatar = profile.get("avatar")
    db.session.commit()

    return user


def discord_profile(discord_code):
    token_response = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": current_app.config["DISCORD_CLIENT_ID"],
            "client_secret": current_app.config["DISCORD_CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "code": discord_code,
            "redirect_uri": current_app.config["DISCORD_REDIRECT_URI"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if token_response.status_code != 200:
        abort(502, "discord token exchange failed")

    access_token = token_response.json().get("access_token")

    profile_response = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )

    if profile_response.status_code != 200:
        abort(502, "discord profile lookup failed")

    return profile_response.json()


@auth_bp.get("/link")
def link():
    code = (request.args.get("code") or "").strip().upper()
    if pending_link_code(code) is None:
        abort(404, EXPIRED_MESSAGE)

    params = {
        "client_id": current_app.config["DISCORD_CLIENT_ID"],
        "redirect_uri": current_app.config["DISCORD_REDIRECT_URI"],
        "response_type": "code",
        "scope": "identify",
        "state": code,
        "prompt": "none",
    }

    return redirect(f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}")


@auth_bp.get("/auth/callback")
def callback():
    record = pending_link_code((request.args.get("state") or "").strip().upper())
    if record is None:
        abort(404, EXPIRED_MESSAGE)

    discord_code = request.args.get("code")
    if not discord_code:
        abort(400, "missing code")

    user = upsert_user(discord_profile(discord_code))
    token = secrets.token_urlsafe(32)
    db.session.add(ApiToken(user_id=user.id, token_hash=hash_token(token), label=record.client or "game"))
    record.user_id = user.id
    record.token_plain = token
    db.session.commit()

    return render_template("linked.html", username=user.username)


def create_link_code(client):
    ttl = timedelta(seconds=current_app.config["LINK_CODE_TTL_SECONDS"])
    for _ in range(10):
        code = generate_code()
        if db.session.get(LinkCode, code) is None:
            record = LinkCode(code=code, expires_at=utcnow() + ttl, client=client[:64])
            db.session.add(record)
            db.session.commit()
            return record

    abort(500, "could not allocate link code")


def poll_link_code(code):
    record = db.session.get(LinkCode, code)

    if record is None or record.expired():
        if record is not None and record.user_id is None:
            db.session.delete(record)
            db.session.commit()
        return {"status": "expired"}

    if record.user_id is None:
        return {"status": "pending"}

    if record.delivered or not record.token_plain:
        return {"status": "expired"}

    token = record.token_plain
    record.token_plain = None
    record.delivered = True
    db.session.commit()

    return {"status": "linked", "token": token, "user": record.user.to_dict()}
