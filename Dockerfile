FROM python:3.10-slim

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Installation des dépendances système pour Playwright et Xvfb
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    xvfb \
    x11vnc \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire de travail
WORKDIR /app

# Copier les fichiers requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Installer Chromium avec Playwright
RUN playwright install chromium && \
    playwright install chromium && \
    ls -la /root/.cache/ms-playwright/

# Copier le code de l'application
COPY . .

# Script de démarrage avec Xvfb
RUN echo '#!/bin/bash\n\
# Démarrer Xvfb en arrière-plan\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &\n\
# Attendre que Xvfb démarre\n\
sleep 2\n\
# Démarrer l application\n\
exec uvicorn gmaps_scraper_server.main_api:app --host 0.0.0.0 --port 8001\n\
' > /app/start.sh && chmod +x /app/start.sh

# Exposer le port
EXPOSE 8001

# Commande de démarrage
CMD ["/app/start.sh"]
