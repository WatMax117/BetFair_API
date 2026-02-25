# NetBet Auth Service - Betfair Authentication
FROM python:3.11-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /data /certs && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8080

CMD ["python", "-m", "src"]
