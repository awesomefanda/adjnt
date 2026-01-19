#!/bin/bash

# Exit on error
set -e

echo "🧹 Step 0: Cleaning environment..."
docker-compose down --remove-orphans
docker rm -f waha adjnt 2>/dev/null || true
# Optional: Clear DB to start totally fresh
# rm -f adjnt_vault.db

echo "🚀 Step 1: Building and starting Adjnt Stack..."
docker-compose up -d --build

echo "⏳ Step 2: Waiting for WAHA API to be ready..."
# Loop until the WAHA health check returns 200
until $(curl --output /dev/null --silent --head --fail http://localhost:3001/api/sessions); do
    printf '.'
    sleep 2
done
echo " Ready!"

echo "📲 Step 3: Initializing WhatsApp Session..."

# 1. Force delete the 'default' session to clear any 'FAILED' status
echo "   - Resetting session status..."
curl -s -X DELETE http://localhost:3001/api/sessions/default > /dev/null || true

# 2. Create and start the session (The 'Atomic' way)
echo "   - Creating 'default' session..."
curl -s -X POST http://localhost:3001/api/sessions \
     -H "Content-Type: application/json" \
     -d '{"name": "default", "start": true}' > /dev/null

# 3. Apply the Webhook via the dedicated Webhooks endpoint (more reliable than PATCH)
echo "   - Configuring webhook bridge..."
curl -s -X POST http://localhost:3001/api/webhooks \
     -H "Content-Type: application/json" \
     -d '{
       "url": "http://adjnt:8000/webhook",
       "events": ["message", "message.any"],
       "enabled": true
     }' > /dev/null

echo "------------------------------------------------"
echo "✅ SUCCESS: Adjnt System is Online!"
echo "👉 ACTION: Scan the QR code at the link below:"
echo "🔗 http://localhost:3001/api/screenshot?session=default"
echo "------------------------------------------------"
echo "📄 To view logs: docker-compose logs -f adjnt"