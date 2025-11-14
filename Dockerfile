FROM debian:13


# Install python, pip, CIFS mount tools, lftp, and clean up
RUN apt update && apt install -y \
    python3 python3-pip \
    cifs-utils \
    lftp \
    && apt clean && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY AppleConverter.py .


# Run continuously
CMD ["python3","/app/AppleConverter.py"]
