"""
Development seed data script.

DO NOT use in production. For production admin accounts, use:
    flask create-admin

This script requires migrations to be applied first:
    flask db upgrade
"""
print("WARNING: This script is for local development only.")
print("For production, use: flask create-admin")
print()
print("To set up a fresh local database:")
print("  1. flask db upgrade          # Create tables via migrations")
print("  2. flask create-admin        # Create your manager account")
print()
print("This script does nothing. Use the commands above instead.")
