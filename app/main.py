import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router, ws_router
from app.core.config import settings
from app.core.database import engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("hominsh.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # dev convenience; use Alembic migrations in production
    if settings.DEBUG:
        await seed_demo_data()
    yield
    await engine.dispose()


async def seed_demo_data() -> None:
    """Seed a ready-to-test demo user, content and device (idempotent, dev only)."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models import Content, ContentType, Device, User

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "dev@hominsh.com"))
        user = result.scalar_one_or_none()
        if user is None:
            db.add(User(email="dev@hominsh.com", name="Demo User", provider="local", points_balance=50000))
            logger.info("Seeded demo user dev@hominsh.com (50,000P)")

        result = await db.execute(select(Content).where(Content.stream_key == "demo-stream"))
        if result.scalar_one_or_none() is None:
            db.add(Content(title="Demo Live 360°", type=ContentType.LIVE_360, stream_key="demo-stream",
                           media_url=f"{settings.SRS_HLS_BASE_URL}/live/demo-stream.m3u8", price_points=500))

        result = await db.execute(select(Content).where(Content.title == "Demo VOD"))
        if result.scalar_one_or_none() is None:
            db.add(Content(title="Demo VOD", type=ContentType.VOD, price_points=0,
                           media_url="https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"))

        result = await db.execute(select(Device).where(Device.id == "HS-01"))
        if result.scalar_one_or_none() is None:
            db.add(Device(id="HS-01", model="Meta Quest 3", firmware_version="v1.2.0"))

        await db.commit()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
