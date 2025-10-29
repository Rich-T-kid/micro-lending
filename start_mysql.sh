#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found!"
    echo "Please create a .env file with your database credentials."
    exit 1
fi

# Check if required variables are set
if [ -z "$MYSQL_HOST" ] || [ -z "$MYSQL_USER" ] || [ -z "$MYSQL_PASSWORD" ] || [ -z "$MYSQL_DATABASE" ]; then
    echo "❌ Missing required environment variables!"
    echo "Please ensure .env has: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE"
    exit 1
fi

echo "🗄️  Connecting to MySQL database..."
echo "Host: $MYSQL_HOST"
echo "Database: $MYSQL_DATABASE"
echo "User: $MYSQL_USER"
echo ""

# Connect to MySQL
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"
