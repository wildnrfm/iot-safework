"""Aplikasi web (FastAPI): membungkus Service menjadi endpoint HTTP dan menyajikan dashboard."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .service import Service

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class RuleIn(BaseModel):
    item: str
    requirement: str = "wajib"


class ProfileIn(BaseModel):
    id: str
    name: str
    description: str = ""
    rules: list[RuleIn] = Field(default_factory=list)


class ActiveIn(BaseModel):
    id: str


def create_app(service: Service) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        service.start()
        try:
            yield
        finally:
            service.stop()

    app = FastAPI(title="SAFEWORK AI", lifespan=lifespan)

    def require_admin(token: Optional[str]) -> None:
        if not service.is_admin(token):
            raise HTTPException(status_code=401, detail="Token admin salah atau belum diisi.")

    @app.get("/api/state")
    def get_state():
        return service.state()

    @app.get("/api/profiles")
    def get_profiles():
        return service.profiles_payload()

    @app.post("/api/profiles")
    def post_profile(body: ProfileIn, x_admin_token: Optional[str] = Header(default=None)):
        require_admin(x_admin_token)
        try:
            return service.save_profile(body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/profiles/{profile_id}")
    def delete_profile(profile_id: str, x_admin_token: Optional[str] = Header(default=None)):
        require_admin(x_admin_token)
        try:
            service.delete_profile(profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Profil tidak ditemukan.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/profiles/active")
    def post_active(body: ActiveIn, x_admin_token: Optional[str] = Header(default=None)):
        require_admin(x_admin_token)
        try:
            return service.set_active(body.id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Profil tidak ditemukan.") from exc

    @app.get("/api/history")
    def get_history(limit: int = Query(default=50, ge=1, le=500)):
        return service.history_list(limit)

    @app.get("/api/summary")
    def get_summary():
        return service.summary()

    @app.get("/api/history.csv")
    def get_history_csv():
        return PlainTextResponse(service.history_csv(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="riwayat-safework.csv"'})

    @app.post("/api/indicator/test")
    def post_indicator_test(x_admin_token: Optional[str] = Header(default=None)):
        require_admin(x_admin_token)
        service.test_indicator()
        return {"ok": True}

    @app.get("/stream.mjpg")
    def stream():
        return StreamingResponse(service.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
