#!/usr/bin/env python3
"""
Alerte carburant : te prévient sur ton iPhone (appli ntfy) quand du SP95 ou du
gazole redevient disponible dans une station de Strasbourg.

Source : données officielles « Prix des carburants - Flux instantané v2 »
(data.economie.gouv.fr), mises à jour toutes les 10 minutes environ.

Usage :
  python3 alerte_carburant.py --list   # liste les stations de la ville (pour choisir les ID)
  python3 alerte_carburant.py --test   # envoie une notification de test
  python3 alerte_carburant.py          # vérification normale (à lancer toutes les 10 min)

Aucune dépendance : bibliothèque standard Python 3 uniquement.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ------------------------- À PERSONNALISER -------------------------
NTFY_TOPIC = "carburant-k7x92qpl"
VILLE = "Strasbourg"
CODE_DEPARTEMENT = "67"
CARBURANTS = ["sp95", "gazole"]
# ID des stations à surveiller (obtenus avec --list).
# Liste vide = toutes les stations de la ville (peut faire beaucoup de notifications).
STATION_IDS = []
# --------------------------------------------------------------------

API = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
)
STATE_FILE = Path(__file__).with_name("etat_carburant.json")
NOMS = {"sp95": "SP95", "gazole": "Gazole"}


def fetch_stations():
    """Récupère toutes les stations du département puis filtre sur la ville."""
    stations, offset = [], 0
    while True:
        params = urllib.parse.urlencode(
            {"where": f'code_departement="{CODE_DEPARTEMENT}"', "limit": 100, "offset": offset}
        )
        with urllib.request.urlopen(f"{API}?{params}", timeout=30) as r:
            data = json.load(r)
        batch = data.get("results", [])
        stations.extend(batch)
        offset += 100
        if len(batch) < 100:
            break
    return [s for s in stations if (s.get("ville") or "").strip().lower() == VILLE.lower()]


def disponible(station, carburant):
    """Un carburant est disponible s'il a un prix et n'est pas déclaré en rupture."""
    prix = station.get(f"{carburant}_prix")
    rupture = station.get(f"{carburant}_rupture_type")
    return prix is not None and not rupture


def notifier(titre, message):
    payload = json.dumps(
        {"topic": NTFY_TOPIC, "title": titre, "message": message, "priority": 4, "tags": ["fuelpump"]}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://ntfy.sh", data=payload, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    if "--test" in sys.argv:
        notifier("Test alerte carburant", "Si tu vois ce message, les notifications fonctionnent.")
        print("Notification de test envoyée.")
        return

    stations = fetch_stations()
    if "--list" in sys.argv:
        for s in sorted(stations, key=lambda x: x.get("adresse") or ""):
            etat = ", ".join(
                f"{NOMS[c]}: {'dispo' if disponible(s, c) else 'indispo'}" for c in CARBURANTS
            )
            print(f"{s['id']}  {s.get('adresse')}, {s.get('cp')}  [{etat}]")
        print(f"\n{len(stations)} stations trouvées à {VILLE}.")
        return

    if STATION_IDS:
        stations = [s for s in stations if str(s["id"]) in {str(i) for i in STATION_IDS}]

    ancien = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    nouveau, alertes = {}, []
    for s in stations:
        for c in CARBURANTS:
            cle = f"{s['id']}:{c}"
            nouveau[cle] = disponible(s, c)
            # Alerte uniquement sur un passage indispo -> dispo (pas au tout premier lancement)
            if ancien is not None and nouveau[cle] and not ancien.get(cle, False):
                alertes.append(f"{NOMS[c]} : {s.get('adresse')}, {s.get('cp')}")

    STATE_FILE.write_text(json.dumps(nouveau))

    if alertes:
        notifier("Carburant disponible !", "\n".join(alertes))
    print(f"{len(stations)} station(s) vérifiée(s), {len(alertes)} alerte(s).")


if __name__ == "__main__":
    main()
