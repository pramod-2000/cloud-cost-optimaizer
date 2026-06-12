import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from ai_analyzer import AiAnalyzerError, analyze_costs
from aws_scanner import AwsCliError, list_regions, scan_region
from db import (
    DatabaseError,
    close_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_history,
    init_db,
    save_analysis,
)


load_dotenv()

app = FastAPI(title="AI Cloud Cost Detective API")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProgressManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, analysis_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(analysis_id, []).append(websocket)

    def disconnect(self, analysis_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(analysis_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(analysis_id, None)

    async def send(self, analysis_id: str, message: str) -> None:
        connections = list(self._connections.get(analysis_id, []))
        for websocket in connections:
            try:
                await websocket.send_json({"analysis_id": analysis_id, "message": message})
            except RuntimeError:
                self.disconnect(analysis_id, websocket)


progress_manager = ProgressManager()


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class AnalyzeRequest(BaseModel):
    region: str = Field(..., min_length=1, description="AWS region name, for example us-east-1")
    analysis_id: str | None = Field(
        default=None,
        description="Optional client-generated UUID used for WebSocket progress tracking.",
    )


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET is not configured.")
    return secret


def _create_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    try:
        user = await get_user_by_id(user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    return {
        "id": str(user["id"]),
        "email": user["email"],
        "created_at": user["created_at"].isoformat(),
    }


@app.post("/api/auth/signup")
async def signup(payload: AuthRequest) -> dict[str, Any]:
    email = payload.email.strip().lower()
    password_hash = await run_in_threadpool(_hash_password, payload.password)

    try:
        user = await create_user(email, password_hash)
    except DatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    token = _create_token(str(user["id"]), user["email"])
    return {"token": token, "user": {"id": str(user["id"]), "email": user["email"]}}


@app.post("/api/auth/login")
async def login(payload: AuthRequest) -> dict[str, Any]:
    email = payload.email.strip().lower()

    try:
        user = await get_user_by_email(email)
    except DatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if user is None or not await run_in_threadpool(_verify_password, payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = _create_token(str(user["id"]), user["email"])
    return {"token": token, "user": {"id": str(user["id"]), "email": user["email"]}}


@app.get("/api/regions")
def get_regions(_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, list[str]]:
    try:
        return {"regions": list_regions()}
    except AwsCliError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/api/analyze")
async def analyze_region(
    payload: AnalyzeRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    analysis_id = payload.analysis_id or str(uuid4())
    region = payload.region.strip()

    try:
        await progress_manager.send(analysis_id, "Fetching regions...")
        regions = await run_in_threadpool(list_regions)
        if region not in regions:
            raise HTTPException(status_code=400, detail=f"Invalid AWS region: {region}")

        await progress_manager.send(analysis_id, f"Scanning resources in {region}...")
        scan_result = await run_in_threadpool(scan_region, region)

        await progress_manager.send(analysis_id, "Analyzing costs with AI...")
        analysis = await run_in_threadpool(analyze_costs, scan_result)

        full_result = {
            "scan": scan_result,
            "analysis": analysis,
        }
        issues_found = len(analysis.get("issues", []))

        await progress_manager.send(analysis_id, "Storing results...")
        saved_analysis = await save_analysis(
            analysis_id=analysis_id,
            user_id=user["id"],
            region=region,
            resources_scanned=scan_result.get("resource_count", 0),
            issues_found=issues_found,
            estimated_savings=analysis.get("estimated_monthly_savings", "unknown"),
            analysis_result=full_result,
            status="complete",
        )

        await progress_manager.send(analysis_id, "Analysis complete")
        return {
            "analysis_id": str(saved_analysis["id"]),
            **full_result,
        }
    except AwsCliError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except AiAnalyzerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/api/history")
async def history(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        analyses = await get_user_history(user["id"])
    except DatabaseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {"user": user, "analyses": analyses}


@app.websocket("/ws/progress/{analysis_id}")
async def progress_websocket(websocket: WebSocket, analysis_id: str) -> None:
    await progress_manager.connect(analysis_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        progress_manager.disconnect(analysis_id, websocket)
