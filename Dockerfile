FROM python:3.12-slim

WORKDIR /app

COPY first_run_builder.py .
COPY manga_fixer_main.py .
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
