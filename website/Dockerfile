# سایت معرفی UploadFly: فقط پایتون استاندارد؛ با آدرس واقعی (SITE_URL) در یک volume ساخته می‌شود و Caddy نشانش می‌دهد
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /site
COPY build.py pages.py ./
COPY assets ./assets
CMD ["python", "build.py", "--out", "/srv/site"]
