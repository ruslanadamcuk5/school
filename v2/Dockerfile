# Сборка сайта
FROM node:20-slim AS web
WORKDIR /app/v2/frontend
COPY v2/frontend/package.json v2/frontend/package-lock.json ./
RUN npm ci
COPY v2/frontend/ ./
RUN npm run build

# Backend + готовая статика
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/v2/backend:/app
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY v2/backend/requirements.txt v2/backend/requirements.txt
RUN pip install --no-cache-dir -r v2/backend/requirements.txt

COPY . .
COPY --from=web /app/v2/frontend/dist /app/v2/frontend/dist

EXPOSE 8000
CMD ["uvicorn", "school_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
