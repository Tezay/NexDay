import os
from dotenv import load_dotenv

# Charge les variables du fichier .env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Chemin vers la base de données SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Récupère l'URL du calendrier depuis .env
    APPLE_CALENDAR_URL = os.environ.get('APPLE_CALENDAR_URL')