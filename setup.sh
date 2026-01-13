#!/bin/bash

# Exit on error
set -e

echo "🧹 Step 0: Cleaning up existing containers..."
docker-compose down # This stops and removes containers defined in the yaml
docker rm -f waha adjnt-app 2>/dev/null || true # Forced cleanup of manual runs

echo "🚀 Step 1: Building and starting Adjnt Stack..."
docker-compose up -d --build

echo "⏳ Step 2: Waiting for engine to warm up (15s)..."
# Give WAHA time to initialize the NOWEB engine
sleep 15

echo "📲 Step 3: Initializing WhatsApp Session..."
# Using curl to tell WAHA to start the 'default' session
curl -s -X POST http://localhost:3001/api/sessions/start \
     -H "Content-Type: application/json" \
     -d '{"name": "default"}' > /dev/null

echo "------------------------------------------------"
echo "✅ SUCCESS: Adjnt System is Online!"
echo "👉 ACTION: Scan the QR code at the link below:"
echo "🔗 http://localhost:3001/api/screenshot?session=default"
echo "------------------------------------------------"
echo "📄 To view real-time logs: docker-compose logs -f"