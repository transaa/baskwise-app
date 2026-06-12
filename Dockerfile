# baskwise app container — used by Render (and works on Cloud Run / any Docker host)
FROM python:3.13-slim

# System dependency for photo-receipt OCR
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better build caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Render injects $PORT at runtime; 8501 is the local-docker default
ENV PORT=8501
EXPOSE 8501

# Shell form so $PORT expands
CMD streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
