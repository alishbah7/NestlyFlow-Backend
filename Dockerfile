FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (uncomment if using psycopg2 for Postgres)
# RUN apt-get update && apt-get install -y libpq-dev gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set the environment variable for the port (Back4app usually defaults to 8080 or 80)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]