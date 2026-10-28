# A scan service with no GPU and no network dependency at runtime.
# Mount the response files under /data and point the client at port 8000.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000
# Set KEEL_TOKEN to require a bearer token. Leave unset only on a private network.
ENV KEEL_TOKEN=""
CMD ["keel", "serve", "--root", "/data", "--port", "8000"]
