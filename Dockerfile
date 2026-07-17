FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ghostscript tesseract-ocr tesseract-ocr-por && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[document]"
ENV KE_CONVERTER=docling KE_DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "knowledge_engineering.api:app", "--host", "0.0.0.0", "--port", "8000"]
