# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (adjust as needed)
EXPOSE 8000

# Command to run the application
CMD ["python", "src/api_server/server.py"]



#docker build -t test-micro .
#docker run -p 8000:8000 test-micro