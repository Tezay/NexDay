import requests
from icalendar import Calendar, Event
from datetime import datetime, date, timedelta, time
import pytz # Pour les fuseaux horaires

def get_busy_times(calendar_url, start_date, end_date, target_tz='UTC'):
    """
    Télécharge et parse un calendrier iCal pour trouver les plages horaires occupées
    entre start_date et end_date (inclusives).

    Args:
        calendar_url (str): URL du fichier .ics public.
        start_date (datetime.date): Date de début de la période.
        end_date (datetime.date): Date de fin de la période.
        target_tz (str): Fuseau horaire cible pour normaliser les heures (ex: 'Europe/Paris').

    Returns:
        list: Une liste de tuples [(start_datetime_utc, end_datetime_utc), ...],
              représentant les périodes occupées en UTC.
              Retourne une liste vide en cas d'erreur ou si l'URL n'est pas fournie.
    """
    if not calendar_url:
        print("Avertissement: Aucune URL de calendrier source n'est configurée.")
        return []

    try:
        response = requests.get(calendar_url, timeout=10) # Timeout de 10s
        response.raise_for_status() # Lève une exception pour les erreurs HTTP (4xx, 5xx)
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors du téléchargement du calendrier: {e}")
        return []

    try:
        cal = Calendar.from_ical(response.text)
    except Exception as e:
        print(f"Erreur lors du parsing du calendrier iCal: {e}")
        return []

    busy_periods_utc = []
    target_timezone = pytz.timezone(target_tz)

    # Convertir les dates de début/fin en datetime au début/fin de journée dans le fuseau horaire cible
    # Puis convertir en UTC pour la comparaison, car icalendar retourne souvent en UTC ou sans TZ
    start_dt_local = target_timezone.localize(datetime.combine(start_date, time.min))
    end_dt_local = target_timezone.localize(datetime.combine(end_date, time.max))
    start_dt_utc = start_dt_local.astimezone(pytz.utc)
    end_dt_utc = end_dt_local.astimezone(pytz.utc)


    for component in cal.walk():
        if component.name == "VEVENT":
            dtstart = component.get('dtstart')
            dtend = component.get('dtend')

            if not dtstart or not dtend:
                continue # Événement incomplet

            start_time = dtstart.dt
            end_time = dtend.dt

            # Gérer les dates simples (événements sur toute la journée)
            # Si c'est une date sans heure, on considère toute la journée comme occupée
            if isinstance(start_time, date) and not isinstance(start_time, datetime):
                 # Convertir la date en datetime au début du jour dans le fuseau cible, puis UTC
                start_time_local = target_timezone.localize(datetime.combine(start_time, time.min))
                 # Pour la fin, prendre la date de fin (qui est exclusive dans ce cas) ou dtstart + 1 jour
                if isinstance(end_time, date) and not isinstance(end_time, datetime):
                    end_dt_date = end_time
                else:
                    end_dt_date = start_time + timedelta(days=1) # Fin exclusive

                end_time_local = target_timezone.localize(datetime.combine(end_dt_date, time.min))
                start_time_utc = start_time_local.astimezone(pytz.utc)
                end_time_utc = end_time_local.astimezone(pytz.utc)

            # Gérer les datetime avec ou sans fuseau horaire
            elif isinstance(start_time, datetime):
                # Si pas de fuseau horaire, supposer UTC (comportement courant d'icalendar)
                if start_time.tzinfo is None or start_time.tzinfo.utcoffset(start_time) is None:
                    start_time_utc = pytz.utc.localize(start_time)
                else:
                    start_time_utc = start_time.astimezone(pytz.utc)

                if end_time.tzinfo is None or end_time.tzinfo.utcoffset(end_time) is None:
                    end_time_utc = pytz.utc.localize(end_time)
                else:
                    end_time_utc = end_time.astimezone(pytz.utc)
            else:
                 continue # Type de date non géré


            # Vérifier si l'événement chevauche la période demandée [start_dt_utc, end_dt_utc]
            # L'événement est pertinent si : event_start < period_end ET event_end > period_start
            if start_time_utc < end_dt_utc and end_time_utc > start_dt_utc:
                 # Tronquer l'événement aux limites de la période si nécessaire
                actual_start = max(start_time_utc, start_dt_utc)
                actual_end = min(end_time_utc, end_dt_utc)
                if actual_start < actual_end: # Ignorer les événements de durée nulle après troncature
                    busy_periods_utc.append((actual_start, actual_end))

    # Trier les périodes occupées
    busy_periods_utc.sort()

    # Fusionner les périodes qui se chevauchent ou sont adjacentes
    if not busy_periods_utc:
        return []

    merged_busy_periods = []
    current_start, current_end = busy_periods_utc[0]

    for next_start, next_end in busy_periods_utc[1:]:
        if next_start <= current_end: # Chevauchement ou adjacence
            current_end = max(current_end, next_end) # Étendre la période courante
        else:
            merged_busy_periods.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged_busy_periods.append((current_start, current_end)) # Ajouter la dernière période

    # print(f"Périodes occupées fusionnées (UTC): {merged_busy_periods}") # Debug
    return merged_busy_periods


def create_ical_feed(scheduled_events, target_tz='UTC'):
    """
    Crée une chaîne de caractères au format iCalendar (.ics) à partir d'une liste d'événements planifiés.

    Args:
        scheduled_events (list): Liste de dictionnaires, chacun représentant un événement planifié.
                                 Chaque dict doit avoir : 'name', 'category', 'start_utc', 'end_utc'.
        target_tz (str): Le fuseau horaire dans lequel afficher les événements dans le calendrier client.

    Returns:
        bytes: Le contenu du fichier iCalendar encodé en UTF-8.
    """
    cal = Calendar()
    cal.add('prodid', '-//Mon Planificateur Personnel//mxm.dk//')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH') # Indique que c'est un calendrier publié

    timezone = pytz.timezone(target_tz)

    for event_data in scheduled_events:
        event = Event()
        event.add('summary', event_data['name'])

        # Convertir les datetimes UTC en datetime locaux pour l'affichage
        start_utc = event_data['start_utc']
        end_utc = event_data['end_utc']
        start_local = start_utc.astimezone(timezone)
        end_local = end_utc.astimezone(timezone)

        event.add('dtstart', start_local)
        event.add('dtend', end_local)
        event.add('dtstamp', datetime.now(pytz.utc)) # Heure de création de l'événement
        event.add('uid', f"{start_utc.strftime('%Y%m%dT%H%M%SZ')}-{event_data['name']}@monplanificateur.perso") # ID unique
        if 'category' in event_data:
            event.add('categories', [event_data['category']])
        # event.add('description', f"Planifié automatiquement. Catégorie: {event_data.get('category', 'N/A')}")

        cal.add_component(event)

    return cal.to_ical() # Retourne des bytes (UTF-8 par défaut)

# --- Fin de calendar_utils.py ---