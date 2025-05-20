from flask import Flask
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS
from models import db

app = Flask(__name__)

# Configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS

# Initialize Database
db.init_app(app)

# Create Tables
with app.app_context():
    db.drop_all()  # Drop all tables to ensure a clean slate
    db.create_all()  # Create all tables based on the models
    print("📦 Database and tables created successfully!")
