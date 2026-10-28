
import logging
from time import perf_counter
from typing import List

from app.database import db
from app.models import FakeUser


logger = logging.getLogger("uvicorn.error")


class FakerService:
    async def generate_users(
        self,
        locale: str,
        seed: int,
        batch_index: int,
        batch_size: int,
    ) -> List[FakeUser]:
        total_started = perf_counter()

        # The SQL function now accepts a global starting position.
        start_index = batch_index * batch_size

        database_started = perf_counter()
        rows = await self._fetch_rows(
            locale=locale,
            seed=seed,
            start_index=start_index,
            batch_size=batch_size,
        )
        database_seconds = perf_counter() - database_started

        conversion_started = perf_counter()
        users = [self._row_to_user(row) for row in rows]
        conversion_seconds = perf_counter() - conversion_started

        total_seconds = perf_counter() - total_started

        logger.info(
            "GENERATION start_index=%d requested=%d returned=%d "
            "database_fetch_seconds=%.4f conversion_seconds=%.4f "
            "total_seconds=%.4f",
            start_index,
            batch_size,
            len(users),
            database_seconds,
            conversion_seconds,
            total_seconds,
        )

        return users

    async def _fetch_rows(
        self,
        locale: str,
        seed: int,
        start_index: int,
        batch_size: int,
    ) -> list:
        query = """
            SELECT *
            FROM generate_fake_users($1, $2, $3, $4)
        """

        async with db.connection() as conn:
            rows = await conn.fetch(
                query,
                locale,
                seed,
                start_index,
                batch_size,
            )

        return rows

    def _row_to_user(self, row) -> FakeUser:
        return FakeUser(
            batch_position=row["batch_position"],
            full_name=row["full_name"],
            address=row["address"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            physical=row["physical"],
            phone=row["phone"],
            email=row["email"],
        )


faker_service = FakerService()
