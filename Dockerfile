FROM python:3.12-slim

# Install lftp
RUN apt-get update && \
    apt-get install -y lftp cifs-utils && \
    apt-get clean

# Create app directory
WORKDIR /app

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY AppleConverter.py .


# Run continuously
ENTRYPOINT ["python3 /app/AppleConverter.py"]
