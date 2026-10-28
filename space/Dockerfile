# Build context is the repository root.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
COPY results ./results
COPY space ./space
COPY repro ./repro
COPY docs ./docs
RUN pip install --no-cache-dir . && pip install --no-cache-dir -r space/requirements.txt

EXPOSE 7860
CMD ["uvicorn", "space.app:app", "--host", "0.0.0.0", "--port", "7860"]
