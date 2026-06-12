# 1. Use a lightweight Python base image
FROM python:3.10-slim

# 2. Install Tesseract OCR and its dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your app's code
COPY . .

# 6. Expose port (informational only)
EXPOSE 10000

# 7. Start the server using Gunicorn — bind to Render's assigned port
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-10000}