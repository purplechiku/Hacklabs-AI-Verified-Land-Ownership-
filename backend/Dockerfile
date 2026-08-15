# Backend — Docker image with Tesseract OCR
# Render's native Python environment blocks apt-get, so Tesseract (a system
# binary, not a pip package) needs Docker to install correctly.

FROM python:3.11-slim

# Install Tesseract OCR (the actual OCR engine) + English language data.
# --no-install-recommends keeps the image smaller; we don't need extras.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (separate layer = faster rebuilds when
# only your code changes, not your dependencies).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code.
COPY . .

EXPOSE 8000

# Render sets $PORT automatically — this falls back to 8000 if it's ever
# missing (e.g. running the image locally for testing).
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
