FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY directory ./directory
COPY lab_a_node ./lab_a_node
COPY lab_b_node ./lab_b_node
COPY inceptum_poc ./inceptum_poc
COPY sdk ./sdk
COPY demo ./demo
COPY docs ./docs
COPY examples ./examples

RUN pip install --no-cache-dir .

