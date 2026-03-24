FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY core/ core/
COPY api/ api/

RUN pip install --no-cache-dir ".[api]"

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
