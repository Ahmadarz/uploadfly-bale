"""انتقال SQLite → PostgreSQL باید همه‌ی جدول‌های مدل را ببرد (فهرست دستی قدیمی ۱۱ جدول را جا می‌انداخت)."""
from app.db import Base
from scripts.migrate_sqlite_to_postgres import TABLE_ORDER


def test_migration_copies_every_table_in_dependency_order():
    assert set(TABLE_ORDER) == set(Base.metadata.tables)
    seen = set()
    for name in TABLE_ORDER:   # هر جدول بعد از جدول‌هایی می‌آید که به آن‌ها کلید خارجی دارد
        for fk in Base.metadata.tables[name].foreign_keys:
            assert fk.column.table.name in seen or fk.column.table.name == name, (name, fk.column.table.name)
        seen.add(name)
