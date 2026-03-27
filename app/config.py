import os
import secrets

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "kube_control_plane"

# Generate secure SECRET_KEY - MUST be set via environment variable in production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # In development, generate a random key
    SECRET_KEY = secrets.token_urlsafe(32)
    print("WARNING: SECRET_KEY not set. Generated random key for development only.")
    print("Set SECRET_KEY environment variable for production!")

#GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
#GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")