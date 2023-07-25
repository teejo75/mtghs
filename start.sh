#! /usr/bin/env sh
set -e
./app/prestart.sh

cd /app
uvicorn main:app --host 0.0.0.0 --port 80
