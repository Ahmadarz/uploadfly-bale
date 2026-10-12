"""واحد پول برنامه: تومان. همه‌ی سقف‌ها و قیمت‌های آماده از همین‌جا می‌آیند.

PRICE_UNIT فقط برای تست‌هاست (آن‌جا ۱ است تا عددهای تست کوچک و خوانا بمانند)؛ در اجرای واقعی ۱۰۰۰ تومان است.
"""
import os

UNIT = int(os.getenv("PRICE_UNIT", "1000"))

MIN_PRICE = UNIT                                    # ارزان‌ترین قیمت: ۱٬۰۰۰ تومان
MAX_PRICE = 10_000 * UNIT                           # ۱۰ میلیون تومان برای یک فاکتور
PRICE_PRESETS = tuple(n * UNIT for n in (10, 25, 50, 100, 250))
# سقف قیمت بر اساس تعداد فروش موفق: (کمتر از این تعداد فروش، سقف)
PRICE_TIERS = tuple((sales, cap * UNIT) for sales, cap in ((5, 100), (20, 300), (100, 1000)))
TIP_PRESETS = tuple(n * UNIT for n in (10, 50, 100, 500))
TIP_MIN, TIP_MAX = UNIT, 2_500 * UNIT


def toman(n: int) -> str:
    """۲۵۰۰۰ ← «25,000 تومان»."""
    return f"{n:,} تومان"
