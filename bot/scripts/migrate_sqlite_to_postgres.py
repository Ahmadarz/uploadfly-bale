"""انتقال یک‌باره‌ی داده‌ها از SQLite (مک) به PostgreSQL (سرور).

استفاده:
    python -m scripts.migrate_sqlite_to_postgres \\
        --source sqlite+aiosqlite:///uploadfly.db \\
        --target postgresql+asyncpg://uploadfly:PASSWORD@localhost:5432/uploadfly

- جدول‌ها را در مقصد می‌سازد و داده‌ها را به ترتیب وابستگی کپی می‌کند.
- اگر مقصد از قبل داده داشته باشد، کاری نمی‌کند (برای جلوگیری از رونویسی اشتباهی).
- در پایان تعداد ردیف‌های هر جدول را در مبدأ و مقصد مقایسه می‌کند.
"""
import argparse
import asyncio
import sys
from datetime import timezone

from sqlalchemy import DateTime, func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import Base, _add_missing_columns

# همه‌ی جدول‌های مدل، به ترتیب کلیدهای خارجی (اول کاربرها، بعد چیزهایی که به آن‌ها اشاره می‌کنند).
# فهرست دستی نیست تا هر جدول تازه خودکار منتقل شود (فهرست دستی قدیمی ویترین‌ها، عضویت‌ها و … را جا می‌انداخت)
TABLE_ORDER = [t.name for t in Base.metadata.sorted_tables]


def fix_row(table, row: dict) -> dict:
    """SQLite زمان‌ها را بدون منطقه‌ی زمانی برمی‌گرداند؛ ستون‌های «با منطقه» در PostgreSQL زمان UTC آگاه می‌خواهند."""
    out = dict(row)
    for col in table.columns:
        value = out.get(col.name)
        if value is not None and isinstance(col.type, DateTime) and col.type.timezone and value.tzinfo is None:
            out[col.name] = value.replace(tzinfo=timezone.utc)
    return out


async def migrate(source_url: str, target_url: str) -> bool:
    source = create_async_engine(source_url)
    target = create_async_engine(target_url)
    async with source.begin() as conn:  # ستون‌های جدید در دیتابیس قدیمی هم باشند
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    async with target.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for name in TABLE_ORDER:
            if await conn.scalar(select(func.count()).select_from(Base.metadata.tables[name])):
                print(f"⛔️ مقصد از قبل داده دارد (جدول {name}). برای امنیت، کاری انجام نشد.")
                return False

    counts = {}
    async with source.connect() as src, target.begin() as dst:
        for name in TABLE_ORDER:
            table = Base.metadata.tables[name]
            rows = [fix_row(table, dict(r._mapping)) for r in (await src.execute(select(table))).all()]
            if rows:
                await dst.execute(table.insert(), rows)
            counts[name] = len(rows)
            print(f"  {name}: {len(rows)} ردیف")
        # شمارنده‌ی شناسه‌های خودکار PostgreSQL باید از بزرگ‌ترین شناسه‌ی کپی‌شده ادامه دهد
        for name in TABLE_ORDER:
            table = Base.metadata.tables[name]
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement is True:
                await dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{name}', '{pk[0].name}'), "
                    f"COALESCE((SELECT MAX({pk[0].name}) FROM {name}), 0) + 1, false)"))

    ok = True
    async with target.connect() as dst:
        for name in TABLE_ORDER:
            n = await dst.scalar(select(func.count()).select_from(Base.metadata.tables[name]))
            status = "✅" if n == counts[name] else "❌"
            ok &= n == counts[name]
            print(f"{status} {name}: مبدأ {counts[name]} / مقصد {n}")
    await source.dispose()
    await target.dispose()
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    sys.exit(0 if asyncio.run(migrate(args.source, args.target)) else 1)


if __name__ == "__main__":
    main()
