FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

COPY abi/ abi/

# Copy the application
COPY consumer/ .

# Install requirements system-wide
RUN uv pip install --system -r requirements.txt

# Make sure Python prints logs immediately (no buffering)
ENV PYTHONUNBUFFERED=1

# Run the consumer service
CMD ["python", "main.py"] 