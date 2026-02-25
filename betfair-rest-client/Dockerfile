# Betfair REST client – autonomous daemon sharing credentials with Java client
FROM python:3.11-slim

WORKDIR /app

# Only what this module needs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py risk.py sticky_prematch.py discovery_time_window.py backfill_tier_a.py backfill_book_risk_l3.py backfill_ladder_levels.py backfill_l1_backsize.py .

# Cert paths in container (mapped via volume); config from env_file in compose
ENV BF_CERT_PATH=/app/certs/client-2048.crt
ENV BF_KEY_PATH=/app/certs/client-2048.key

CMD ["python", "-u", "main.py"]
