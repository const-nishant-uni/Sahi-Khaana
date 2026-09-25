# Sahi Khaana backend. Build and run from THIS folder:
#   docker build -t sahi-khaana-backend .
#   docker run -p 8000:8000 --env-file .env -v sahi-data:/data sahi-khaana-backend
FROM python:3.11-slim

# tesseract-ocr: fallback OCR engine. libgomp1: needed by onnxruntime (RapidOCR).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# rapidocr-onnxruntime goes in WITHOUT deps: it would pull in the full opencv-python,
# which clashes with opencv-python-headless (see README).
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir rapidocr-onnxruntime --no-deps

COPY app ./app

# Keep the database and uploaded photos in a volume, not in the image.
ENV DATABASE_URL=sqlite:////data/sahi_khaana.db \
    UPLOAD_DIR=/data/uploads
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
