import os
from flask import Flask, render_template, request, jsonify, Response
from config import Config
from models import db, Activity
from calendar_utils import get_busy_times, create_ical_feed
from scheduler import generate_schedule
from datetime import datetime, timedelta, time
import pytz # Pour la gestion des fuseaux horaires

# Crée le dossier 'instance' s'il n'existe pas (pour SQLite)
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
app.config.from_object(Config)

# Initialise SQLAlchemy avec l'application Flask
db.init_app(app)

# Crée les tables de la base de données si elles n'existent pas
with app.app_context():
    db.create_all()

# Route principale pour afficher l'interface
@app.route('/')
def index():
    # Récupère l'URL du calendrier depuis la config pour l'afficher (si besoin)
    calendar_url_config = app.config.get('APPLE_CALENDAR_URL', '')
    return render_template('index.html', calendar_url_config=calendar_url_config)


# --- API Routes ---

@app.route('/api/activities', methods=['GET'])
def get_activities():
    """Retourne la liste de toutes les activités."""
    activities = Activity.query.all()
    return jsonify([activity.to_dict() for activity in activities])

@app.route('/api/activities', methods=['POST'])
def add_activity():
    """Ajoute une nouvelle activité."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('weekly_minutes') or not data.get('category'):
        return jsonify({'message': 'Données manquantes'}), 400

    try:
        new_activity = Activity(
            name=data['name'],
            weekly_minutes=int(data['weekly_minutes']),
            category=data['category']
        )
        db.session.add(new_activity)
        db.session.commit()
        return jsonify(new_activity.to_dict()), 201 # 201 Created
    except ValueError:
         return jsonify({'message': 'Le temps doit être un nombre entier'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Erreur serveur: {e}'}), 500


@app.route('/api/activities/<int:id>', methods=['PUT'])
def update_activity(id):
    """Met à jour une activité existante."""
    activity = Activity.query.get_or_404(id) # Renvoie 404 si non trouvé
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Pas de données fournies'}), 400

    try:
        activity.name = data.get('name', activity.name)
        activity.weekly_minutes = int(data.get('weekly_minutes', activity.weekly_minutes))
        activity.category = data.get('category', activity.category)
        db.session.commit()
        return jsonify(activity.to_dict())
    except ValueError:
         return jsonify({'message': 'Le temps doit être un nombre entier'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Erreur serveur: {e}'}), 500


@app.route('/api/activities/<int:id>', methods=['DELETE'])
def delete_activity(id):
    """Supprime une activité."""
    activity = Activity.query.get_or_404(id)
    try:
        db.session.delete(activity)
        db.session.commit()
        return jsonify({'message': 'Activité supprimée'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Erreur serveur: {e}'}), 500


# --- Route pour le flux iCalendar ---

@app.route('/calendar/feed.ics')
def generate_ical_feed():
    """Génère et renvoie le planning sous forme de flux iCalendar."""

    # 0. Définir le fuseau horaire local (important!)
    local_tz_name = 'Europe/Paris'
    try:
        local_tz = pytz.timezone(local_tz_name)
    except pytz.UnknownTimeZoneError:
        print(f"Erreur: Fuseau horaire '{local_tz_name}' inconnu. Utilisation de UTC.")
        local_tz = pytz.utc
        local_tz_name = 'UTC'


    # 1. Définir la période pour laquelle générer le planning (ex: semaine prochaine)
    #    Calcul basé sur la date/heure actuelle du fuseau horaire spécifié
    now_local = datetime.now(local_tz)
    # Trouver le lundi de la semaine prochaine
    days_until_monday = (7 - now_local.weekday()) % 7
    next_monday_local = now_local.date() + timedelta(days=days_until_monday)
    # Si aujourd'hui est lundi, prendre le lundi suivant (commenter la ligne suivante si vous voulez la semaine en cours)
    if days_until_monday == 0: next_monday_local += timedelta(days=7)

    start_date_local = next_monday_local
    end_date_local = start_date_local + timedelta(days=6) # Du lundi au dimanche inclus

    print(f"Génération du planning pour la semaine du {start_date_local} au {end_date_local} ({local_tz_name})")


    # 2. Récupérer les activités depuis la base de données
    activities = Activity.query.all()
    if not activities:
        return Response("Aucune activité à planifier.", mimetype='text/plain')

    # 3. Récupérer l'URL du calendrier source depuis la configuration
    calendar_url = app.config.get('APPLE_CALENDAR_URL')
    if not calendar_url:
         print("Avertissement: Pas d'URL de calendrier source. Planning basé uniquement sur semaine vide.")
         # return Response("URL du calendrier source non configurée.", status=500, mimetype='text/plain')


    # 4. Obtenir les périodes occupées depuis le calendrier source
    #    Convertir les dates locales en datetime UTC pour get_busy_times
    start_dt_local_tz = local_tz.localize(datetime.combine(start_date_local, time.min))
    end_dt_local_tz = local_tz.localize(datetime.combine(end_date_local, time.max))
    week_start_utc = start_dt_local_tz.astimezone(pytz.utc)
    week_end_utc = end_dt_local_tz.astimezone(pytz.utc)

    busy_times_utc = get_busy_times(calendar_url, start_date_local, end_date_local, target_tz=local_tz_name)


    # 5. Générer le planning avec le scheduler
    #    Utilisation des datetime UTC pour la logique interne du scheduler
    scheduled_events = generate_schedule(activities, busy_times_utc, week_start_utc, week_end_utc)


    # 6. Créer le contenu du fichier iCalendar
    #    Les heures seront converties dans local_tz_name pour l'affichage client
    ical_content = create_ical_feed(scheduled_events, target_tz=local_tz_name)


    # 7. Renvoyer la réponse avec le bon type MIME
    return Response(
        ical_content,
        mimetype='text/calendar',
        headers={'Content-Disposition': 'attachment; filename=planning_genere.ics'} # Suggère un nom de fichier
    )


if __name__ == '__main__':
    app.run(debug=True) # Mode debug pour le développement local