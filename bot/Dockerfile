# UploadFly: ربات + Mini App در یک کانتینر (سایت جداست: website/Dockerfile). ffmpeg برای پیش‌نمایش ویدیو و صدا لازم است.
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TZ=UTC
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY webapp ./webapp

# مرحله‌ی تست: docker build --target test . && docker run --rm <image>
FROM base AS test
COPY requirements-dev.txt pytest.ini ./
COPY tests ./tests
RUN pip install -r requirements-dev.txt
CMD ["python", "-m", "pytest", "-q", "-p", "no:warnings"]

# مرحله‌ی اصلی (پیش‌فرض)
FROM base AS app
# بدون دسترسی root؛ فقط پوشه‌ی کش و لوگو قابل نوشتن است
RUN useradd --create-home --uid 1000 uploadfly \
    && mkdir -p /app/cache && chown -R uploadfly /app/cache /app/webapp
USER uploadfly
ENV WEBAPP_HOST=0.0.0.0 WEBAPP_PORT=8080
EXPOSE 8080
CMD ["python", "-m", "app.main"]
