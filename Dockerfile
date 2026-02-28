FROM python:3.12-slim

WORKDIR /app

COPY "First Run - Builder.py" .
COPY "Manga Fixer Main.py" .
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

