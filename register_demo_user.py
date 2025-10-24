#!/usr/bin/env python3
"""
Register Demo User Script
Quick script to register a demo user in the microlending platform
"""

import requests
import json

# API Configuration
API_URL = "http://localhost:8000"

def register_demo_user():
    """Register a demo user with predefined credentials"""
    
    demo_user = {
        "email": "demo@microlending.com",
        "password": "Demo123!@#",
        "first_name": "Demo",
        "last_name": "User",
        "phone": "+1234567890",
        "address_line1": "123 Demo Street",
        "city": "San Francisco",
        "state_province": "CA",
        "postal_code": "94105",
        "country": "USA",
        "date_of_birth": "1990-01-01"
    }
    
    print("=" * 60)
    print("MicroLending Platform - Demo User Registration")
    print("=" * 60)
    print("\nRegistering demo user...")
    print(f"Email: {demo_user['email']}")
    print(f"Password: {demo_user['password']}")
    print()
    
    try:
        response = requests.post(
            f"{API_URL}/users",
            json=demo_user,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            data = response.json()
            print("✅ SUCCESS! Demo user registered successfully!")
            print(f"\nUser ID: {data.get('id')}")
            print(f"Email: {data.get('email')}")
            print(f"Name: {data.get('first_name')} {data.get('last_name')}")
            print("\n" + "=" * 60)
            print("You can now login with:")
            print(f"  Email: {demo_user['email']}")
            print(f"  Password: {demo_user['password']}")
            print("=" * 60)
        elif response.status_code == 409 or response.status_code == 400:
            print("⚠️  User already exists!")
            print("\nYou can login with:")
            print(f"  Email: {demo_user['email']}")
            print(f"  Password: {demo_user['password']}")
        else:
            print(f"❌ ERROR: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to API server!")
        print(f"\nMake sure the backend server is running at {API_URL}")
        print("Start it with: cd src/api_server && python server.py")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")

if __name__ == "__main__":
    register_demo_user()
