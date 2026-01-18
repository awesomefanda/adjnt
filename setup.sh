#!/bin/bash

# Exit on error
set -e

echo "🧹 Step 0: Cleaning up existing containers..."
# This stops containers and clears the network to resolve ENOTFOUND errors
docker-compose down --remove-orphans
docker rm -f waha adjnt 2>/dev/null || true

echo "🚀 Step 1: Building and starting Adjnt Stack..."
# Build and start services defined in docker-compose.yml
docker-compose up -d --build

echo "⏳ Step 2: Waiting for engine to warm up (20s)..."
# NOWEB engine takes a moment to initialize the DNS bridge
sleep 20

echo "📲 Step 3: Initializing WhatsApp Session & Webhook..."
# We use PATCH here to ensure the internal WAHA config maps correctly to 'adjnt'
curl -s -X PATCH http://localhost:3001/api/sessions/default \
     -H "Content-Type: application/json" \
     -d '{
       "config": {
         "webhooks": [
           {
             "url": "http://adjnt:8000/webhook",
             "events": ["message", "message.any"],
             "enabled": true
           }
         ]
       }
     }' > /dev/null

# Ensure the session is actually started
curl -s -X POST http://localhost:3001/api/sessions/default/start > /dev/null

echo "------------------------------------------------"
echo "✅ SUCCESS: Adjnt System is Online!"
echo "👉 ACTION: Scan the QR code at the link below:"
echo "🔗 http://localhost:3001/api/screenshot?session=default"
echo "------------------------------------------------"
echo "📄 To view real-time logs: docker-compose logs -f adjnt"