#   Copyright 2024 Prof. Dr. Mahsa Fischer, Hochschule Heilbronn
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.*/

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

ENV OPENAI_API_KEY=""

# Command to run your script
CMD ["python", "script.py"]
