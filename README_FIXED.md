# Google Maps Scraper - Version Corrigée

## 🔧 Modifications apportées

Cette version corrige les problèmes suivants :
- ✅ Support du mode headless ET non-headless avec Xvfb
- ✅ Meilleure détection anti-bot (masquage WebDriver)
- ✅ Plusieurs sélecteurs CSS de secours pour `[role="feed"]`
- ✅ Gestion améliorée du formulaire de consentement
- ✅ Meilleure extraction des données
- ✅ Gestion d'erreurs robuste avec screenshots de debug
- ✅ Logging détaillé pour le diagnostic

## 📦 Installation

### 1. Cloner le projet original

```bash
git clone https://github.com/conor-is-my-name/google-maps-scraper.git
cd google-maps-scraper
```

### 2. Remplacer les fichiers par les versions corrigées

Remplace les fichiers suivants dans ton projet :

```bash
# Dockerfile
cp Dockerfile.fixed Dockerfile

# Scraper
cp scraper.py.fixed gmaps_scraper_server/scraper.py

# API
cp main_api.py.fixed gmaps_scraper_server/main_api.py

# Docker Compose
cp docker-compose.yml.fixed docker-compose.yml

# Requirements
cp requirements.txt.fixed requirements.txt
```

### 3. Structure du projet

Assure-toi d'avoir cette structure :

```
google-maps-scraper/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── gmaps_scraper_server/
    ├── __init__.py
    ├── main_api.py
    └── scraper.py
```

### 4. Créer le fichier __init__.py si absent

```bash
touch gmaps_scraper_server/__init__.py
```

## 🚀 Déploiement

### Option 1 : Docker (Recommandé)

```bash
# Arrêter les conteneurs existants
docker-compose down

# Construire et démarrer
docker-compose up --build -d

# Vérifier les logs
docker-compose logs -f
```

### Option 2 : Local (pour développement)

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Installer les navigateurs Playwright
playwright install chromium
playwright install-deps chromium

# Démarrer l'API
uvicorn gmaps_scraper_server.main_api:app --host 0.0.0.0 --port 8001 --reload
```

## 🧪 Tests

### 1. Test de santé

```bash
curl http://localhost:8001/health
```

Réponse attendue :
```json
{
  "status": "healthy",
  "service": "google-maps-scraper"
}
```

### 2. Test de scraping (GET)

```bash
# Avec headless=true (par défaut)
curl "http://localhost:8001/scrape-get?query=hotel%20in%20paris&max_places=5&lang=en&headless=true"

# Avec plus de résultats
curl "http://localhost:8001/scrape-get?query=restaurant%20in%20london&max_places=20&lang=en&headless=true"
```

### 3. Test de scraping (POST)

```bash
curl -X POST "http://localhost:8001/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "hotel in paris",
    "max_places": 10,
    "lang": "fr",
    "headless": true
  }'
```

### 4. Test avec IP locale

```bash
# Remplace 192.168.1.195 par ton IP
curl "http://192.168.1.195:8001/scrape-get?query=cafe%20in%20berlin&max_places=10&lang=en&headless=true"
```

## 📊 Format de réponse

```json
{
  "success": true,
  "query": "hotel in paris",
  "total_results": 10,
  "results": [
    {
      "name": "Hôtel Plaza Athénée",
      "rating": "4.5",
      "reviews_count": "1234",
      "category": "5-star hotel",
      "url": "https://www.google.com/maps/place/..."
    }
  ]
}
```

## 🔍 Diagnostic et Debug

### Vérifier les logs du conteneur

```bash
# Logs en temps réel
docker-compose logs -f

# Logs des 100 dernières lignes
docker logs gmaps_scraper_api --tail 100

# Entrer dans le conteneur
docker exec -it gmaps_scraper_api bash
```

### Endpoint de debug

```bash
curl http://localhost:8001/debug
```

### Screenshots de debug

Si le scraping échoue, un screenshot est automatiquement sauvegardé dans `/tmp/gmaps_error.png`.

Pour récupérer ce screenshot :

```bash
docker cp gmaps_scraper_api:/tmp/gmaps_error.png ./debug_screenshot.png
```

## 🎯 Utilisation avec n8n

### Node HTTP Request (GET)

```
URL: http://gmaps_scraper_api_service:8001/scrape-get
Méthode: GET
Query Parameters:
  - query: {{ $json.search_query }}
  - max_places: 20
  - lang: en
  - headless: true
```

### Node HTTP Request (POST)

```
URL: http://gmaps_scraper_api_service:8001/scrape
Méthode: POST
Body Type: JSON
Body:
{
  "query": "{{ $json.search_query }}",
  "max_places": 20,
  "lang": "en",
  "headless": true
}
```

## 🐛 Résolution des problèmes courants

### Problème : "Feed element not found"

**Solutions** :
1. Vérifier le screenshot de debug
2. Augmenter les délais d'attente
3. Essayer avec une query plus simple

### Problème : Aucun résultat retourné

**Solutions** :
1. Tester avec une query plus simple : "restaurant"
2. Changer de langue : `lang=fr` au lieu de `lang=en`
3. Ajouter des délais entre les requêtes

### Problème : Conteneur crashe

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## ✅ Checklist de déploiement

- [ ] Fichiers remplacés
- [ ] `__init__.py` créé dans `gmaps_scraper_server/`
- [ ] Docker Compose arrêté : `docker-compose down`
- [ ] Build sans cache : `docker-compose build --no-cache`
- [ ] Conteneur démarré : `docker-compose up -d`
- [ ] Health check OK : `curl http://localhost:8001/health`
- [ ] Test scraping OK
- [ ] Logs sans erreur

Bon scraping ! 🚀
