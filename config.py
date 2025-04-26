import os
from dotenv import load_dotenv

# Charge les variables du fichier .env
basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
load_dotenv(dotenv_path)

# --- Ajout pour débogage ---
print(f"Debug [config.py]: .env path = {dotenv_path}")
print(f"Debug [config.py]: PERSONAL_CALENDAR_URL_1 from os.environ after load_dotenv = {os.environ.get('PERSONAL_CALENDAR_URL_1')}")
print(f"Debug [config.py]: PERSONAL_CALENDAR_URL_2 from os.environ after load_dotenv = {os.environ.get('PERSONAL_CALENDAR_URL_2')}")
print(f"Debug [config.py]: PERSONAL_CALENDAR_URL_3 from os.environ after load_dotenv = {os.environ.get('PERSONAL_CALENDAR_URL_3')}")
# --- Fin de l'ajout ---


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Chemin vers la base de données SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Récupère les URLs des calendriers depuis .env et les stocke dans une liste
    # Filtre les URLs vides ou non définies
    PERSONAL_CALENDAR_URLS = [
        url for url in [
            os.environ.get('PERSONAL_CALENDAR_URL_1'),
            os.environ.get('PERSONAL_CALENDAR_URL_2'),
            os.environ.get('PERSONAL_CALENDAR_URL_3')
        ] if url # Vérifie que l'URL n'est pas None ou vide
    ]
    # --- Ajout pour débogage ---
    print(f"Debug [config.py]: Config.PERSONAL_CALENDAR_URLS set to = {PERSONAL_CALENDAR_URLS}")
    # --- Fin de l'ajout ---

    # Conserver l'ancienne variable pour compatibilité si nécessaire, mais préférer la liste
    # APPLE_CALENDAR_URL = os.environ.get('PERSONAL_CALENDAR_URL_1') # Ou garder l'ancien nom si utilisé ailleurs