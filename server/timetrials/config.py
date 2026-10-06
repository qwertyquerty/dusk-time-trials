import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:5000").rstrip("/")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mysql+pymysql://timetrials:timetrials@localhost/timetrials?charset=utf8mb4"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
    DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", PUBLIC_URL + "/auth/callback")
    
    CATEGORIES_PATH = os.path.abspath(
        os.path.join(BASE_DIR, os.environ.get("CATEGORIES_PATH", "../res/categories.yaml"))
    )

    LINK_CODE_TTL_SECONDS = int(os.environ.get("LINK_CODE_TTL_SECONDS", "600"))
    LEADERBOARD_LIMIT = 100
