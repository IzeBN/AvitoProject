#!/usr/bin/env python3
"""
Создаёт партиции для секционированных таблиц на текущий и следующие месяцы.

Запускать: ежемесячно (cron или arq periodic task).
Таблицы с партиционированием по дате: chat_messages, audit_log, error_log.

Пример запуска:
    DATABASE_URL=postgresql://avitocrm:pass@localhost:5432/avitocrm python create_partitions.py

Пример cron (1-го числа каждого месяца в 02:00):
    0 2 1 * * /usr/bin/env python3 /app/infra/scripts/create_partitions.py
"""

import asyncio
import os
import sys
from datetime import date

import asyncpg
from dateutil.relativedelta import relativedelta

# Таблицы, для которых нужно создавать партиции.
# Каждая из них должна быть объявлена как PARTITION BY RANGE (created_at).
PARTITIONED_TABLES = [
    "chat_messages",
    "audit_log",
    "error_log",
]

# Создаём партиции на текущий месяц + N месяцев вперёд.
MONTHS_AHEAD = 2


async def create_partition_for_month(
    conn: asyncpg.Connection,
    table: str,
    year: int,
    month: int,
) -> None:
    """Создаёт партицию таблицы для указанного месяца (IF NOT EXISTS)."""
    partition_name = f"{table}_{year:04d}_{month:02d}"
    start = date(year, month, 1)
    end = start + relativedelta(months=1)

    sql = f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF {table}
        FOR VALUES FROM ('{start}') TO ('{end}');
    """

    await conn.execute(sql)
    print(f"  [ok] {partition_name}  ({start} — {end})")


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # asyncpg не понимает префикс postgresql+asyncpg — нормализуем URL.
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"Connecting to database...")
    conn = await asyncpg.connect(dsn)

    today = date.today()
    print(f"Today: {today}. Creating partitions for {MONTHS_AHEAD + 1} month(s)...\n")

    try:
        for months_offset in range(MONTHS_AHEAD + 1):
            target = today + relativedelta(months=months_offset)
            print(f"Month: {target.year}-{target.month:02d}")
            for table in PARTITIONED_TABLES:
                await create_partition_for_month(conn, table, target.year, target.month)
            print()
    finally:
        await conn.close()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
