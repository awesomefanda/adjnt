#!/bin/bash

echo "☢️ Warning: This will delete your database and WhatsApp login."
read -p "Are you sure? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "🧹 Cleaning up..."
    docker-compose down -v
    rm -f adjnt_vault.db
    rm -rf ./waha_sessions
    echo "✨ Project cleaned. Run ./setup.sh to start fresh."
fi