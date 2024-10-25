# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install system dependencies for MySQL and other required packages
RUN apt-get update && apt-get install -y \
    gcc \
    libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (if your application serves something directly, otherwise this can be omitted)
EXPOSE 8000

# Command to run your script
CMD ["python", "script.py"]
