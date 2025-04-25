from datetime import datetime, timedelta

def generate_schedule(activities, busy_times_utc, week_start_utc, week_end_utc, slot_duration_minutes=30):
    """
    Répartit les activités dans les créneaux disponibles d'une semaine.

    Args:
        activities (list): Liste d'objets Activity (de models.py).
        busy_times_utc (list): Liste de tuples (start_utc, end_utc) de périodes occupées.
        week_start_utc (datetime): Début de la semaine en UTC.
        week_end_utc (datetime): Fin de la semaine en UTC.
        slot_duration_minutes (int): Durée de chaque créneau de planification (ex: 30 ou 60).

    Returns:
        list: Liste de dictionnaires d'événements planifiés.
              Chaque dict: {'name', 'category', 'start_utc', 'end_utc'}.
    """
    scheduled_events = []
    slot_duration = timedelta(minutes=slot_duration_minutes)

    # 1. Créer tous les créneaux possibles de la semaine
    all_slots = []
    current_time = week_start_utc
    while current_time < week_end_utc:
        slot_end = current_time + slot_duration
        all_slots.append({'start': current_time, 'end': slot_end, 'available': True})
        current_time = slot_end

    # 2. Marquer les créneaux occupés par les événements externes
    for busy_start, busy_end in busy_times_utc:
        for slot in all_slots:
            # Vérifier si le créneau chevauche la période occupée
            # Chevauchement si: slot_start < busy_end ET slot_end > busy_start
            if slot['start'] < busy_end and slot['end'] > busy_start:
                slot['available'] = False

    # 3. Préparer les besoins en temps pour chaque activité (en nombre de créneaux)
    activity_needs = []
    for activity in activities:
        slots_needed = round(activity.weekly_minutes / slot_duration_minutes)
        if slots_needed > 0:
            activity_needs.append({
                'activity': activity,
                'slots_remaining': slots_needed,
                'scheduled_slots': [] # Pour stocker les créneaux attribués
            })

    # 4. Algorithme de placement simple : Premier arrivé, premier servi
    #    Itérer sur les créneaux disponibles et attribuer aux activités qui en ont besoin.
    #    A améliorer...
    current_need_index = 0
    for slot in all_slots:
        if not slot['available']:
            continue # Passer au créneau suivant si celui-ci est occupé

        if current_need_index < len(activity_needs):
            need = activity_needs[current_need_index]

            # Attribuer ce créneau à l'activité courante
            need['scheduled_slots'].append(slot)
            need['slots_remaining'] -= 1
            slot['available'] = False # Marquer le créneau comme utilisé par nous

            # Si l'activité a eu tous ses créneaux, passer à la suivante
            if need['slots_remaining'] == 0:
                current_need_index += 1
        else:
            break # Toutes les activités ont été planifiées (ou plus de créneaux nécessaires)


    # 5. Générer la liste finale d'événements planifiés
    #    Ici, chaque créneau est un événement séparé. (On pourrait fusionner les consécutifs)
    for need in activity_needs:
        activity = need['activity']
        for slot in need['scheduled_slots']:
            scheduled_events.append({
                'name': activity.name,
                'category': activity.category,
                'start_utc': slot['start'],
                'end_utc': slot['end']
            })
        # Afficher si une activité n'a pas pu être entièrement planifiée
        if need['slots_remaining'] > 0:
             print(f"Avertissement: Temps insuffisant pour planifier entièrement '{activity.name}'. "
                   f"{need['slots_remaining'] * slot_duration_minutes} minutes manquantes.")


    return scheduled_events