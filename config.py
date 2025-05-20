import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "bar_inventory.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Generate a random secret key
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
