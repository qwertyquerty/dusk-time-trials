from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discord_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    runs: Mapped[list["Run"]] = relationship(back_populates="user")

    def to_dict(self):
        return {"id": self.id, "username": self.username, "discord_id": self.discord_id}


class Category(db.Model):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    start_state_hash: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    runs: Mapped[list["Run"]] = relationship(back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group_name,
            "segments": self.config.get("segments", []),
            "fail_on_death": self.config.get("fail_on_death", False),
            "form": self.config.get("form", "choice"),
            "start_state_hash": self.start_state_hash,
            "active": self.active,
        }


class Run(db.Model):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    rta_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    replay_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    replay_path: Mapped[str] = mapped_column(String(512), nullable=False)
    replay_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mod_version: Mapped[str] = mapped_column(String(32), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False)
    start_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    loadout_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="accepted", nullable=False, index=True)

    user: Mapped[User] = relationship(back_populates="runs")
    category: Mapped[Category] = relationship(back_populates="runs")

    def to_dict(self, rank=None):
        data = {
            "run_id": self.id,
            "user": self.user.username if self.user else None,
            "category_id": self.category_id,
            "rta_ms": self.rta_ms,
            "frame_count": self.frame_count,
            "submitted_at": self.submitted_at.replace(tzinfo=timezone.utc).isoformat(),
            "mod_version": self.mod_version,
            "status": self.status,
        }
        if rank is not None:
            data["rank"] = rank
        return data


def best_runs_query(category_id, limit):
    best = (
        db.session.query(Run.user_id, func.min(Run.rta_ms).label("best"))
        .filter(Run.category_id == category_id, Run.status == "accepted")
        .group_by(Run.user_id)
        .subquery()
    )
    return (
        db.session.query(Run)
        .join(best, (Run.user_id == best.c.user_id) & (Run.rta_ms == best.c.best))
        .filter(Run.category_id == category_id, Run.status == "accepted")
        .order_by(Run.rta_ms.asc(), Run.submitted_at.asc())
        .limit(limit)
    )


def rank_for_run(run):
    better = (
        db.session.query(func.count(func.distinct(Run.user_id)))
        .filter(
            Run.category_id == run.category_id,
            Run.status == "accepted",
            Run.rta_ms < run.rta_ms,
            Run.user_id != run.user_id,
        )
        .scalar()
    )
    return int(better or 0) + 1
