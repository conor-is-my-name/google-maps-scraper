# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies required by Playwright's browsers
# Using the combined command to install dependencies for all browsers
# See: https://playwright.dev/docs/docker#install-system-dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # --- Playwright dependencies ---
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    # --- Other useful packages ---
    curl \
    # --- Cleanup ---
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt setup.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e . --no-deps

# Install Playwright browsers
# This command downloads the browser binaries into the image
RUN playwright install --with-deps

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port the app runs on
EXPOSE 8001

# Define the command to run the application
# Use 0.0.0.0 to make it accessible from outside the container
CMD ["uvicorn", "gmaps_scraper_server.main_api:app", "--host", "0.0.0.0", "--port", "8001"]