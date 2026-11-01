#!/usr/bin/env python3
"""
Alerte carburant : te prévient sur ton iPhone (appli ntfy) quand du SP95 ou du
gazole redevient disponible dans tes stations.

Source des disponibilités : données officielles « Prix des carburants - Flux
instantané v2 » (data.economie.gouv.fr), mises à jour toutes les 10 minutes.
Source des enseignes : OpenStreetMap (les données officielles n'ont pas l'enseigne).

Modes :
  (aucun)   vérification normale, à lancer toutes les 10 minutes
  --test    envoie une notification de test
  --list    liste les stations TotalEnergies dans le rayon autour de la ville
            et affiche la ligne STATION_IDS prête à copier

Aucune dépendance : bibliothèque standard Python 3 uniquement.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ------------------------- À PERSONNALISER -------------------------
# Sur GitHub, le nom du sujet ntfy est lu dans un « secret » (variable NTFY_TOPIC).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "carburant-k7x92qpl")
VILLE = "Strasbourg"
CODE_DEPARTEMENT = "67"
CENTRE = (48.5734, 7.7521)  # centre de Strasbourg (latitude, longitude)
RAYON_KM = 30               # rayon à vol d'oiseau autour du centre
CARBURANTS = ["sp95", "gazole"]
# ID des stations à surveiller, lus dans la variable GitHub STATION_IDS
# (séparés par des virgules). Vide = toutes les stations de la ville.
STATION_IDS = [i.strip() for i in os.environ.get("STATION_IDS", "").split(",") if i.strip()]
# --------------------------------------------------------------------

API = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
)
OVERPASS = "https://overpass-api.de/api/interpreter"
STATE_FILE = Path(__file__).with_name("etat_carburant.json")
NOMS = {"sp95": "SP95", "gazole": "Gazole"}


def fetch_departement():
    """Récupère toutes les stations du département."""
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
    return stations


def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau (formule de haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def coordonnees(station):
    """Retourne (latitude, longitude) d'une station, ou None si absentes."""
    g = station.get("geom")
    if isinstance(g, dict) and g.get("lat") is not None and g.get("lon") is not None:
        return float(g["lat"]), float(g["lon"])
    try:
        lat, lon = float(station.get("latitude")), float(station.get("longitude"))
        if abs(lat) > 180 or abs(lon) > 180:  # ancien format : degrés x 100000
            lat, lon = lat / 100000, lon / 100000
        return lat, lon
    except (TypeError, ValueError):
        return None


def stations_total_osm():
    """Stations TotalEnergies connues d'OpenStreetMap autour de la ville."""
    rayon_m = int((RAYON_KM + 5) * 1000)
    lat, lon = CENTRE
    filtres = "".join(
        f'nwr["amenity"="fuel"]["{cle}"~"total",i](around:{rayon_m},{lat},{lon});'
        for cle in ("brand", "name", "operator")
    )
    requete = f"[out:json][timeout:60];({filtres});out center;"
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": requete}).encode())
    with urllib.request.urlopen(req, timeout=90) as r:
        elements = json.load(r).get("elements", [])
    points = []
    for e in elements:
        c = e.get("center") or e
        if "lat" in c and "lon" in c:
            points.append((c["lat"], c["lon"]))
    return points


def disponible(station, carburant):
    """Un carburant est disponible s'il a un prix et n'est pas déclaré en rupture."""
    prix = station.get(f"{carburant}_prix")
    rupture = station.get(f"{carburant}_rupture_type")
    return prix is not None and not rupture


def etat(station):
    return ", ".join(f"{NOMS[c]}: {'dispo' if disponible(station, c) else 'indispo'}" for c in CARBURANTS)


def notifier(titre, message):
    payload = json.dumps(
        {"topic": NTFY_TOPIC, "title": titre, "message": message, "priority": 4, "tags": ["fuelpump"]}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://ntfy.sh", data=payload, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=30).read()


def mode_liste(stations):
    proches = []
    for s in stations:
        c = coordonnees(s)
        if c:
            d = distance_km(CENTRE[0], CENTRE[1], c[0], c[1])
            if d <= RAYON_KM:
                proches.append((d, c, s))
    proches.sort(key=lambda x: x[0])

    try:
        total_osm = stations_total_osm()
    except Exception as e:
        print(f"Impossible de récupérer les enseignes (OpenStreetMap) : {e}")
        total_osm = None

    def est_total(c):
        return total_osm is not None and any(
            distance_km(c[0], c[1], p[0], p[1]) <= 0.3 for p in total_osm
        )

    total = [(d, s) for d, c, s in proches if est_total(c)]
    autres = [(d, s) for d, c, s in proches if not est_total(c)]

    print(f"=== TotalEnergies dans un rayon de {RAYON_KM} km autour de {VILLE} ({len(total)}) ===")
    for d, s in total:
        print(f"{s['id']}  {s.get('adresse')}, {s.get('cp')} {s.get('ville')}  ({d:.0f} km)  [{etat(s)}]")
    print(f"\nSTATION_IDS = {','.join(str(s['id']) for _, s in total)}")

    print(f"\n=== Autres stations dans le rayon, enseigne non confirmée ({len(autres)}) ===")
    for d, s in autres:
        print(f"{s['id']}  {s.get('adresse')}, {s.get('cp')} {s.get('ville')}  ({d:.0f} km)")


def main():
    if "--test" in sys.argv:
        notifier("Test alerte carburant", "Si tu vois ce message, les notifications fonctionnent.")
        print("Notification de test envoyée.")
        return

    try:
        stations = fetch_departement()
    except Exception as e:  # panne réseau ou API : on réessaiera au prochain passage
        print(f"Impossible de récupérer les données : {e}")
        return

    if "--list" in sys.argv:
        mode_liste(stations)
        return

    if STATION_IDS:
        ids = {str(i) for i in STATION_IDS}
        stations = [s for s in stations if str(s["id"]) in ids]
    else:
        stations = [s for s in stations if (s.get("ville") or "").strip().lower() == VILLE.lower()]

    ancien = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    nouveau, alertes = {}, []
    for s in stations:
        for c in CARBURANTS:
            cle = f"{s['id']}:{c}"
            nouveau[cle] = disponible(s, c)
            # Alerte uniquement sur un passage indispo -> dispo (pas au tout premier lancement)
            if ancien is not None and nouveau[cle] and not ancien.get(cle, False):
                alertes.append(f"{NOMS[c]} : {s.get('adresse')}, {s.get('cp')} {s.get('ville')}")

    STATE_FILE.write_text(json.dumps(nouveau))

    if alertes:
        notifier("Carburant disponible !", "\n".join(alertes))
    print(f"{len(stations)} station(s) vérifiée(s), {len(alertes)} alerte(s).")


if __name__ == "__main__":
    main()
