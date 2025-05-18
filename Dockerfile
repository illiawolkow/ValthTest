FROM python:3.11-slim

# Prevents Python from writing pyc files to disc (equivalent to python -B option)
ENV PYTHONDONTWRITEBYTECODE 1

# Keeps Python from buffering stdin/stdout (equivalent to python -u option)
ENV PYTHONUNBUFFERED 1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# Create and set the working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Ensure app.main:app is the correct path to your FastAPI application instance
# The --host 0.0.0.0 makes the server accessible from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 