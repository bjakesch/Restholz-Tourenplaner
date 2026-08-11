import datetime

# ==========================================
# KONSTANTEN & STAMMDATEN
# ==========================================
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
STANDARD_TRUCK_CAP = 103
STANDARD_SHIFT_HOURS = 9.0

# ==========================================
# HILFSFUNKTIONEN
# ==========================================
def format_hours(hours_float):
    """Macht aus 6.5 Stunden einen String '06:30'."""
    hrs = int(hours_float)
    mins = int(round((hours_float - hrs) * 60))
    if mins == 60:
        hrs += 1
        mins = 0
    return f"{hrs:02d}:{mins:02d}"

def calculate_score(prio, bunker_level):
    """
    Berechnet den Dispo-Score basierend auf Kundenprio und Bunker-Füllstand.
    Höherer Score = wird als Erstes verplant.
    """
    score = prio * 10
    if bunker_level >= 80: 
        score += 30  # Akute Überfüllung = höchste Priorität
    elif bunker_level >= 60: 
        score += 15
    return score

# ==========================================
# HAUPT-ALGORITHMUS ZUR TOURENPLANUNG
# ==========================================
def calculate_tours(datum, offene_kontingente, blocked_trucks=None, extra_drivers=None, bunker_levels=None, shift_hours=STANDARD_SHIFT_HOURS, truck_cap=STANDARD_TRUCK_CAP):
    """
    Verteilt die offenen Kontingente auf die verfügbaren Fahrzeuge.
    
    :param datum: Das Planungsdatum
    :param offene_kontingente: Liste von Dicts mit {'kunde', 'produkt', 'menge_fuhren', 'dauer_h', 'prio', 'bemerkung'}
    :param blocked_trucks: Liste der gesperrten LKWs für diesen Tag
    :param extra_drivers: Liste der LKWs mit Aushilfsfahrer (+4 Stunden)
    :param bunker_levels: Dict mit den aktuellen Prozentwerten der Bunker
    :return: Eine Liste mit fertig berechneten Touren (Dicts)
    """
    if blocked_trucks is None: blocked_trucks = []
    if extra_drivers is None: extra_drivers = []
    if bunker_levels is None: bunker_levels = {"1 - Sägemehl": 50, "2 - Hackschnitzel": 50, "3 - Rinde": 50, "4 - Kappholz": 50}
    
    # 1. Verfügbare LKW und ihre maximalen Schichtzeiten ermitteln
    active_trucks = [t for t in TRUCK_PRIO if t not in blocked_trucks]
    truck_max_hours = {}
    truck_used_hours = {}
    schedule = {t: [] for t in active_trucks}
    
    for t in active_trucks:
        max_h = shift_hours + (4.0 if t in extra_drivers else 0.0)
        truck_max_hours[t] = max_h
        truck_used_hours[t] = 0.0  # Zu Beginn 0 Stunden verbraucht
        
    # 2. Kandidatenliste aufbauen und mit Score bewerten
    candidates = []
    for kontingent in offene_kontingente:
        p_name = kontingent.get("produkt")
        b_level = bunker_levels.get(p_name, 50)
        
        # Nur einplanen, wenn der Bunker nicht gesperrt ist (<= 10%)
        if b_level > 10 and kontingent.get("menge_fuhren", 0) > 0:
            score = calculate_score(kontingent.get("prio", 3), b_level)
            
            candidates.append({
                "Kunde": kontingent.get("kunde"),
                "Produkt": p_name,
                "dauer_h": kontingent.get("dauer_h", 2.0),
                "score": score,
                "rest_req": kontingent.get("bemerkung", "Keine"),
                "offene_fuhren": kontingent.get("menge_fuhren", 0)
            })
            
    # Nach Score absteigend sortieren (Wichtigste zuerst!)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # 3. Kontingente auf LKW verteilen (Rucksackproblem / Bin Packing)
    berechnete_touren = []
    
    for cand in candidates:
        while cand["offene_fuhren"] > 0:
            assigned = False
            
            # Versuche, die Tour in einem LKW unterzubringen
            for t in active_trucks:
                current_h = truck_used_hours[t]
                max_h = truck_max_hours[t]
                
                # Passt die Tour noch in die Schicht? (+0.1 Toleranz)
                if current_h + cand["dauer_h"] <= max_h + 0.1:
                    start_t = 6.0 + current_h  # Schichtbeginn fiktiv 06:00 Uhr
                    end_t = start_t + cand["dauer_h"]
                    time_slot_str = f"{format_hours(start_t)} - {format_hours(end_t)} Uhr"
                    
                    trip_obj = {
                        "Tag": datum.isoformat() if isinstance(datum, (datetime.date, datetime.datetime)) else datum,
                        "Fahrzeug": t,
                        "Zeitfenster": time_slot_str,
                        "Kunde": cand["Kunde"],
                        "Produkt": cand["Produkt"],
                        "Menge_m3": truck_cap,
                        "dauer_h": cand["dauer_h"],
                        "score": cand["score"],
                        "is_manual": False,
                        "Bemerkung": cand["rest_req"]
                    }
                    
                    berechnete_touren.append(trip_obj)
                    
                    # Kapazitäten aktualisieren
                    schedule[t].append(trip_obj)
                    truck_used_hours[t] += cand["dauer_h"]
                    cand["offene_fuhren"] -= 1
                    assigned = True
                    break # LKW gefunden, Schleife abbrechen und nächste Fuhre prüfen
            
            # Wenn kein LKW mehr Platz hat, brechen wir diese Kontingent-Schleife ab
            if not assigned:
                break
                
    return berechnete_touren
