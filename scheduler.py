from datetime import datetime, timedelta, time, date
import pytz # Import pytz for timezone handling
from collections import defaultdict

# --- Configuration Constants ---
WORKING_HOUR_START = 9  # 9 AM
WORKING_HOUR_END = 22 # 10 PM
LUNCH_START_HOUR = 12 # 12 PM
LUNCH_END_HOUR = 15   # 3 PM (exclusive, so includes 14:00-14:59)
MIN_GAP_MINUTES = 30    # Minimum 30 minutes between scheduled events
MAX_CONTINUOUS_MINUTES_PER_ACTIVITY = 120 # Max 2 hours for a single activity block
BUSY_TIME_BUFFER_MINUTES = 60 # 1 hour buffer before/after external events
# Define the local timezone used for working hours and daily constraints
# This should ideally match the one used in app.py
LOCAL_TZ_NAME = 'Europe/Paris'
# --- End Configuration ---

def generate_schedule(activities, busy_times_utc, week_start_utc, week_end_utc, local_tz_name=LOCAL_TZ_NAME, slot_duration_minutes=30):
    """
    Répartit les activités dans les créneaux disponibles d'une semaine,
    en respectant les heures de travail, les contraintes de catégorie/jour,
    l'espacement et la durée maximale par bloc.

    Args:
        activities (list): Liste d'objets Activity.
        busy_times_utc (list): Liste de tuples (start_utc, end_utc) de périodes occupées.
        week_start_utc (datetime): Début de la semaine en UTC.
        week_end_utc (datetime): Fin de la semaine en UTC.
        local_tz_name (str): Nom du fuseau horaire local (ex: 'Europe/Paris').
        slot_duration_minutes (int): Durée de chaque créneau.

    Returns:
        list: Liste de dictionnaires d'événements planifiés.
    """
    scheduled_events_final = []
    slot_duration = timedelta(minutes=slot_duration_minutes)
    min_gap_duration = timedelta(minutes=MIN_GAP_MINUTES)
    max_continuous_duration = timedelta(minutes=MAX_CONTINUOUS_MINUTES_PER_ACTIVITY)
    buffer_duration = timedelta(minutes=BUSY_TIME_BUFFER_MINUTES) # Buffer duration

    try:
        local_tz = pytz.timezone(local_tz_name)
    except pytz.UnknownTimeZoneError:
        print(f"Erreur: Fuseau horaire '{local_tz_name}' inconnu. Utilisation de UTC.")
        local_tz = pytz.utc # Fallback to UTC

    # 1. Créer tous les créneaux possibles et filtrer selon les heures de travail et de déjeuner locales
    all_slots = []
    current_time_utc = week_start_utc
    while current_time_utc < week_end_utc:
        slot_end_utc = current_time_utc + slot_duration
        # Convertir le début du créneau en heure locale pour vérifier les heures de travail/déjeuner
        current_time_local = current_time_utc.astimezone(local_tz)
        slot_hour_local = current_time_local.hour

        # Vérifier si le créneau est DANS les heures de travail ET HORS des heures de déjeuner
        is_working_hour = WORKING_HOUR_START <= slot_hour_local < WORKING_HOUR_END
        is_lunch_hour = LUNCH_START_HOUR <= slot_hour_local < LUNCH_END_HOUR

        if is_working_hour and not is_lunch_hour:
            all_slots.append({
                'start': current_time_utc,
                'end': slot_end_utc,
                'available': True,
                'local_date': current_time_local.date() # Stocker la date locale
            })
        current_time_utc = slot_end_utc

    # 2. Appliquer le buffer aux périodes occupées externes et les fusionner
    buffered_busy_times_utc = []
    for busy_start, busy_end in busy_times_utc:
        # Apply buffer, ensuring start doesn't go before week_start and end doesn't go after week_end
        buffered_start = max(week_start_utc, busy_start - buffer_duration)
        buffered_end = min(week_end_utc, busy_end + buffer_duration)
        # Only add if the interval is still valid after buffering
        if buffered_start < buffered_end:
            buffered_busy_times_utc.append((buffered_start, buffered_end))

    # Merge overlapping/adjacent buffered intervals
    merged_buffered_busy_times_utc = []
    if buffered_busy_times_utc:
        buffered_busy_times_utc.sort() # Sort by start time
        current_start, current_end = buffered_busy_times_utc[0]
        for next_start, next_end in buffered_busy_times_utc[1:]:
            # Check for overlap or adjacency (<= allows adjacent intervals to merge)
            if next_start <= current_end:
                current_end = max(current_end, next_end) # Extend the current interval
            else:
                # No overlap, finalize the current interval and start a new one
                merged_buffered_busy_times_utc.append((current_start, current_end))
                current_start, current_end = next_start, next_end
        # Add the last merged interval
        merged_buffered_busy_times_utc.append((current_start, current_end))

    # 3. Marquer les créneaux occupés (en utilisant les périodes bufferisées et fusionnées)
    for busy_start, busy_end in merged_buffered_busy_times_utc: # Use the merged buffered list
        for slot in all_slots:
            # Check for overlap: slot_start < busy_end AND slot_end > busy_start
            if slot['start'] < busy_end and slot['end'] > busy_start:
                slot['available'] = False

    # 4. Préparer les besoins en temps pour chaque activité (Renumbered from 3)
    activity_needs = []
    total_slots_needed = 0
    for activity in activities:
        slots_needed = round(activity.weekly_minutes / slot_duration_minutes)
        if slots_needed > 0:
            activity_needs.append({
                'activity': activity,
                'slots_remaining': slots_needed,
            })
            total_slots_needed += slots_needed

    if not activity_needs:
        print("Aucune activité à planifier.")
        return []

    # 5. Algorithme de placement amélioré (Renumbered from 4)
    scheduled_slots_details = [] # Stocke les détails des créneaux assignés
    scheduled_slots_by_day = defaultdict(lambda: defaultdict(int)) # {date: {category: count}}
    last_event_end_utc = None # Fin du dernier événement planifié par NOUS
    last_activity_info = {'id': None, 'continuous_duration': timedelta(0)} # Pour suivre la durée consécutive

    available_slots = [slot for slot in all_slots if slot['available']]
    available_slots.sort(key=lambda s: s['start']) # Assurer l'ordre chronologique

    activity_index = 0 # Pour le round-robin
    slots_scheduled_count = 0

    # Itérer tant qu'il reste des besoins et des créneaux disponibles
    processed_slot_indices = set() # Pour éviter de revérifier sans fin un créneau inutilisable
    slot_idx = 0
    while slots_scheduled_count < total_slots_needed and activity_needs and slot_idx < len(available_slots):

        slot = available_slots[slot_idx]

        # Si ce créneau a déjà été traité sans succès pour toutes les activités, passer au suivant
        if slot_idx in processed_slot_indices:
             slot_idx += 1
             continue

        # --- Vérifications préliminaires pour le créneau ---
        # A. Est-il disponible ? (Redondant car on itère sur available_slots, mais sécurité)
        if not slot['available']:
            slot_idx += 1
            continue

        # B. Respecte-t-il l'espacement minimum ?
        if last_event_end_utc is not None and slot['start'] < last_event_end_utc + min_gap_duration:
            # Ce créneau est trop proche du précédent, on ne peut rien y mettre
            # Marquer comme traité pour ne pas le retenter inutilement
            processed_slot_indices.add(slot_idx)
            slot_idx += 1
            continue

        # --- Essayer de placer une activité (Round-Robin) ---
        placed_activity_in_slot = False
        initial_activity_index = activity_index # Pour détecter si on a fait un tour complet
        tried_all_activities = False

        while not placed_activity_in_slot and not tried_all_activities:
            need = activity_needs[activity_index]
            activity = need['activity']
            slot_local_date = slot['local_date']

            # --- Vérifications spécifiques à l'activité pour ce créneau ---
            can_schedule = True

            # C. Contrainte catégorie/jour: Pas plus d'une activité de cette catégorie ce jour-là
            if scheduled_slots_by_day[slot_local_date][activity.category] >= 1:
                can_schedule = False

            # D. Contrainte de durée consécutive
            is_continuing = (last_activity_info['id'] == activity.id and
                             last_event_end_utc is not None and
                             slot['start'] == last_event_end_utc) # Strictement consécutif

            current_block_duration = last_activity_info['continuous_duration'] if is_continuing else timedelta(0)

            if current_block_duration + slot_duration > max_continuous_duration:
                 can_schedule = False # Dépasserait la durée max

            # --- Placement si toutes les conditions sont remplies ---
            if can_schedule:
                # Assigner le créneau
                slot['available'] = False # Marquer comme utilisé
                need['slots_remaining'] -= 1
                slots_scheduled_count += 1

                # Mettre à jour les suivis
                scheduled_slots_by_day[slot_local_date][activity.category] += 1
                last_event_end_utc = slot['end']

                if is_continuing:
                    last_activity_info['continuous_duration'] += slot_duration
                else:
                    last_activity_info = {'id': activity.id, 'continuous_duration': slot_duration}

                # Ajouter aux détails planifiés
                scheduled_slots_details.append({
                    'activity': activity,
                    'slot': slot
                })

                # Si l'activité est terminée, la retirer de la liste des besoins
                if need['slots_remaining'] == 0:
                    print(f"Activité '{activity.name}' entièrement planifiée.")
                    activity_needs.pop(activity_index)
                    # Ajuster l'index pour le prochain tour si on supprime l'élément courant
                    if not activity_needs: break # Plus rien à planifier
                    activity_index %= len(activity_needs)
                else:
                    # Passer à l'activité suivante pour le prochain créneau (round-robin)
                    activity_index = (activity_index + 1) % len(activity_needs)

                placed_activity_in_slot = True # Sortir de la boucle d'essai des activités pour ce créneau

            else:
                # Essayer l'activité suivante pour ce même créneau
                activity_index = (activity_index + 1) % len(activity_needs)
                if activity_index == initial_activity_index:
                    tried_all_activities = True # On a fait un tour complet sans succès

        # Si aucune activité n'a pu être placée dans ce créneau après les avoir toutes essayées
        if not placed_activity_in_slot:
             processed_slot_indices.add(slot_idx) # Marquer ce créneau comme non utilisable pour le moment

        # Passer au créneau suivant dans tous les cas
        slot_idx += 1


    # 6. Générer la liste finale d'événements et afficher les avertissements (Renumbered from 5)
    for detail in scheduled_slots_details:
        activity = detail['activity']
        slot = detail['slot']
        scheduled_events_final.append({
            'name': activity.name,
            'category': activity.category,
            'start_utc': slot['start'],
            'end_utc': slot['end']
        })

    # Afficher les avertissements pour les activités non entièrement planifiées
    for need in activity_needs:
        if need['slots_remaining'] > 0:
            activity = need['activity']
            minutes_missing = need['slots_remaining'] * slot_duration_minutes
            print(f"Avertissement: Temps insuffisant ou créneaux incompatibles pour planifier entièrement '{activity.name}'. "
                  f"{minutes_missing} minutes ({need['slots_remaining']} créneaux) manquantes.")

    print(f"Planification terminée. {len(scheduled_events_final)} créneaux planifiés.")
    return scheduled_events_final

# --- Fin de scheduler.py ---