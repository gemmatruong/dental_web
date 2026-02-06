#!/usr/bin/env python3
"""
Password Hash Generator
Generate secure password hashes for admin users
"""

from werkzeug.security import generate_password_hash
import getpass
import sys


def main():
    print("=" * 60)
    print("Admin Password Hash Generator")
    print("=" * 60)
    print()
    
    while True:
        # Get password input (hidden)
        password = getpass.getpass("Enter admin password (or 'q' to quit): ")
        
        if password.lower() == 'q':
            print("Goodbye!")
            sys.exit(0)
        
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long!")
            print()
            continue
        
        # Confirm password
        confirm = getpass.getpass("Confirm password: ")
        
        if password != confirm:
            print("❌ Passwords do not match!")
            print()
            continue
        
        # Generate hash
        password_hash = generate_password_hash(password)
        
        print()
        print("✓ Password hash generated successfully!")
        print()
        print("Add this to your .env file:")
        print("-" * 60)
        print(f"ADMIN_PASSWORD_HASH={password_hash}")
        print("-" * 60)
        print()
        
        # Ask if they want to generate another
        another = input("Generate another hash? (y/n): ")
        if another.lower() != 'y':
            print("Goodbye!")
            break
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)