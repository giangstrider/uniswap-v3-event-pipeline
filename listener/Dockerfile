FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

COPY abi/ abi/
COPY config/ config/

# Copy the rest of the application
COPY listener/ .

# Install requirements system-wide
RUN uv pip install --system -r requirements.txt

# Run the listener service
CMD ["python", "main.py"] 