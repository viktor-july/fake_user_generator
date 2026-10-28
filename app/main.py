
import csv
import io
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.database import db
from app.services import faker_service
from app.models import GenerateResponse


logger = logging.getLogger("uvicorn.error")

SUPPORTED_LOCALES = {"en_US", "de_DE"}
MAX_PREVIEW_SIZE = 100
MAX_EXPORT_COUNT = 1_000_000
ALLOWED_CHUNK_SIZES = {1000, 5000, 10000}

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR.parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(title="SQL Faker", lifespan=lifespan)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


def validate_locale(locale: str) -> str:
    if locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported locale. Use en_US or de_DE.",
        )
    return locale


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "locale": "en_US",
            "seed": 42,
            "batch_index": 0,
            "batch_size": 10,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    locale: str = Form("en_US"),
    seed: int = Form(42),
    batch_index: int = Form(0),
    batch_size: int = Form(10),
):
    locale = validate_locale(locale)
    batch_index = max(0, batch_index)
    batch_size = max(1, min(batch_size, MAX_PREVIEW_SIZE))

    started = perf_counter()

    users = await faker_service.generate_users(
        locale,
        seed,
        batch_index,
        batch_size,
    )

    elapsed = perf_counter() - started

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "users": users,
            "locale": locale,
            "seed": seed,
            "batch_index": batch_index,
            "batch_size": batch_size,
            "elapsed": elapsed,
        },
    )


@app.get("/download.csv")
async def download_csv(
    locale: str = Query("en_US"),
    seed: int = Query(42),
    count: int = Query(100_000, ge=1, le=MAX_EXPORT_COUNT),
    chunk_size: int = Query(1000),
):
    locale = validate_locale(locale)

    if chunk_size not in ALLOWED_CHUNK_SIZES:
        raise HTTPException(
            status_code=400,
            detail="chunk_size must be 1000, 5000, or 10000",
        )

    async def csv_rows() -> AsyncIterator[str]:
        export_started = perf_counter()
        database_seconds = 0.0
        csv_seconds = 0.0
        rows_written = 0
        batch_index = 0

        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)

        writer.writerow([
            "position",
            "full_name",
            "address",
            "latitude",
            "longitude",
            "physical",
            "phone",
            "email",
        ])

        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        while rows_written < count:
            batch_started = perf_counter()

            users = await faker_service.generate_users(
                locale=locale,
                seed=seed,
                batch_index=batch_index,
                batch_size=min(chunk_size, count - rows_written),
            )

            database_seconds += perf_counter() - batch_started

            if not users:
                logger.warning(
                    "CSV_EXPORT stopped early: no users returned "
                    "at start_index=%d",
                    rows_written,
                )
                break

            csv_started = perf_counter()

            for user in users:
                writer.writerow([
                    rows_written,
                    user.full_name,
                    user.address,
                    user.latitude,
                    user.longitude,
                    user.physical,
                    user.phone,
                    user.email,
                ])
                rows_written += 1

            csv_seconds += perf_counter() - csv_started

            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

            batch_index += 1

        total_seconds = perf_counter() - export_started

        logger.info(
            "CSV_EXPORT requested=%d written=%d chunk_size=%d "
            "service_call_seconds=%.2f csv_serialization_seconds=%.2f "
            "generator_elapsed_seconds=%.2f",
            count,
            rows_written,
            chunk_size,
            database_seconds,
            csv_seconds,
            total_seconds,
        )

    return StreamingResponse(
        csv_rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="fake_users.csv"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/users", response_model=GenerateResponse)
async def api_users(
    locale: str = Query("en_US"),
    seed: int = Query(42),
    batch_index: int = Query(0, ge=0),
    batch_size: int = Query(10, ge=1, le=MAX_PREVIEW_SIZE),
):
    locale = validate_locale(locale)

    users = await faker_service.generate_users(
        locale,
        seed,
        batch_index,
        batch_size,
    )

    return GenerateResponse(
        users=users,
        locale=locale,
        seed=seed,
        batch_index=batch_index,
    )
