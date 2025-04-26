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

    # --- Ajout pour débogage ---
    print(f"Debug [app.py route]: Value in app.config['PERSONAL_CALENDAR_URLS'] = {app.config.get('PERSONAL_CALENDAR_URLS')}")
    # --- Fin de l'ajout ---

    # 0. Définir le fuseau horaire local (important!)
    local_tz_name = 'Europe/Paris' # <--- Utiliser cette variable
    try:
        local_tz = pytz.timezone(local_tz_name)
    except pytz.UnknownTimeZoneError:
        print(f"Erreur: Fuseau horaire '{local_tz_name}' inconnu. Utilisation de UTC.")
        local_tz = pytz.utc
        local_tz_name = 'UTC' # Update name if fallback occurs

    # 1. Définir la période pour laquelle générer le planning (ex: semaine prochaine)
    now_local = datetime.now(local_tz)
    days_until_monday = (7 - now_local.weekday()) % 7
    next_monday_local = now_local.date() + timedelta(days=days_until_monday)
    if days_until_monday == 0: next_monday_local += timedelta(days=7)
    start_date_local = next_monday_local
    end_date_local = start_date_local + timedelta(days=6) # Du lundi au dimanche inclus

    print(f"Génération du planning pour la semaine du {start_date_local} au {end_date_local} ({local_tz_name})")


    # 2. Récupérer les activités depuis la base de données
    activities = Activity.query.all()
    if not activities:
        # Retourner un calendrier vide mais valide
        empty_cal = create_ical_feed([], target_tz=local_tz_name)
        return Response(empty_cal, mimetype='text/calendar', headers={'Content-Disposition': 'attachment; filename=planning_vide.ics'})


    # 3. Récupérer les URLs des calendriers sources depuis la configuration
    calendar_urls = app.config.get('PERSONAL_CALENDAR_URLS', []) # Récupère la liste
    if not calendar_urls:
         print("Avertissement: Pas d'URLs de calendrier source configurées. Planning basé uniquement sur semaine vide.")


    # 4. Obtenir les périodes occupées depuis TOUS les calendriers sources
    all_busy_times_utc = []
    start_dt_local_tz = local_tz.localize(datetime.combine(start_date_local, time.min))
    end_dt_local_tz = local_tz.localize(datetime.combine(end_date_local, time.max))
    week_start_utc = start_dt_local_tz.astimezone(pytz.utc)
    week_end_utc = end_dt_local_tz.astimezone(pytz.utc)

    print("-" * 20)
    print("Récupération des périodes occupées depuis les calendriers:")
    for idx, calendar_url in enumerate(calendar_urls):
        print(f"  - Calendrier {idx+1}: {calendar_url[:50]}...") # Affiche le début de l'URL
        busy_times_single = get_busy_times(calendar_url, start_date_local, end_date_local, target_tz=local_tz_name)
        if busy_times_single:
            print(f"    > {len(busy_times_single)} période(s) trouvée(s).")
            all_busy_times_utc.extend(busy_times_single)
        else:
            print("    > Aucune période trouvée pour ce calendrier dans la plage horaire.")
    print("-" * 20)

    # 4.1 Fusionner et trier TOUTES les périodes occupées récupérées
    #     Même si get_busy_times fusionne déjà en interne, il faut refusionner
    #     les résultats combinés des différents calendriers.
    if all_busy_times_utc:
        all_busy_times_utc.sort() # Trier par heure de début
        merged_busy_times_utc = []
        if all_busy_times_utc: # Vérifier si la liste n'est pas vide après l'extend
            current_start, current_end = all_busy_times_utc[0]
            for next_start, next_end in all_busy_times_utc[1:]:
                if next_start <= current_end: # Chevauchement ou adjacence
                    current_end = max(current_end, next_end)
                else:
                    merged_busy_times_utc.append((current_start, current_end))
                    current_start, current_end = next_start, next_end
            merged_busy_times_utc.append((current_start, current_end))
        busy_times_utc = merged_busy_times_utc # Utiliser la liste fusionnée finale
        print("Périodes occupées totales fusionnées:")
        for start, end in busy_times_utc:
             print(f"  - De {start.strftime('%Y-%m-%d %H:%M:%S %Z')} à {end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("-" * 20)

    else:
        busy_times_utc = [] # Assurer que c'est une liste vide si aucun calendrier n'a renvoyé de période
        print("Aucune période occupée trouvée dans aucun calendrier.")
        print("-" * 20)


    # 5. Générer le planning avec le scheduler
    #    Utilisation des datetime UTC pour la logique interne du scheduler
    #    Passer le fuseau horaire local pour les contraintes internes au scheduler
    print(f"Appel de generate_schedule avec local_tz_name='{local_tz_name}'") # Debug
    scheduled_events = generate_schedule(
        activities,
        busy_times_utc,
        week_start_utc,
        week_end_utc,
        local_tz_name=local_tz_name # <-- Passer le nom du fuseau horaire ici
        # slot_duration_minutes peut être ajouté ici si on veut le rendre configurable via app.py
    )


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