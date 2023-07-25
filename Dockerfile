FROM python:3.11.4-slim

LABEL org.opencontainers.image.source=https://github.com/teejo75/mtghs
LABEL org.opencontainers.image.description="Moonraker Tuya Generic HTTP Server"
LABEL org.opencontainers.image.licenses=MIT

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./app /app

RUN chown -R 1000:1000 /app && chmod +x /app/tinytuya.sh

VOLUME /app/config

CMD ["./start.sh"]
