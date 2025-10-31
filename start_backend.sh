#!/bin/bash
# Start Backend Server
# Run this in Terminal 1

cd "$(dirname "$0")"
source venv/bin/activate
cd src/api_server
echo " starting Backend Server..."
echo "================================"
python server.py
