#!/bin/bash
# Start Frontend Server
# Run this in Terminal 2

cd "$(dirname "$0")/frontend"
echo "starting Frontend Server..."
echo "================================"
npm run dev
