import datetime

# ==========================================
# KONSTANTEN & STAMMDATEN
# ==========================================
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
STANDARD_TRUCK_CAP = 103
STANDARD_SHIFT_HOURS = 9.0

# ==========================================
# HILFSFUNKTIONEN ZUR BEWERTUNG
# ==========================================
def calculate_base_score(prio, bunker_level, combined_sm_hs, dauer_h):
    """
    Berechnet den Basis-Score (ohne Wechsel-Bonus).
    """
    score = prio * 10
    
    # 1. Bunker-Zuschlag (nur noch bei >= 80%)
    if bunker_level >= 80: 
        score += 30  
        
    # 2. Logik für kombiniertes Volumen (Sägemehl + Hackschnitzel)
    if combined_sm_hs > 130:
        # Bunker sind voll -> Kurze Touren priorisieren, um schnell Platz zu schaffen
        if dauer_h < 2.5:
            score += 50
        elif dauer_h < 3.5:
            score += 30
    elif combined_sm_hs < 60:
        # Bunker sind leer -> Lange Touren priorisieren, um das Lager zu schonen
        if dauer_h > 3.5:
            score += 50
        elif dauer_h > 2.5:
            score += 30
            
    return score

# ==========================================
# HAUPT-ALGORITHMUS ZUR TOURENPLANUNG
# ==========================================
def calculate_tours(datum, offene_kontingente, blocked_trucks=None, extra_drivers=None, bunker_levels=None, shift_hours=STANDARD_SHIFT_HOURS, truck_cap=STANDARD_TRUCK_CAP, initial_used_hours=None, initial_tour_counts=None, last_booked_product=None):
    """
    Verteilt Kontingente mit dynamischer Neubewertung (für Wechsel-Bonus) und Tages-Nummerierung.
    """
    if blocked_trucks is None: blocked_trucks = []
    if extra_drivers is None: extra_drivers = []
    if bunker_levels is None: bunker_levels = {"1 - Sägemehl": 50, "2 - Hackschnitzel": 50, "3 - Rinde": 50, "4 - Kappholz": 50}
    if initial_used_hours is None: initial_used_hours = {}
    if initial_tour_counts is None: initial_tour_counts = {}
    
    active_trucks = [t for t in TRUCK_PRIO if t not in blocked_trucks]
    truck_max_hours = {}
    truck_used_hours = {}
    truck_tour_counts = {}
    
    for t in active_trucks:
        truck_max_hours[t] = shift_hours + (4.0 if t in extra_drivers else 0.0)
        truck_used_hours[t] = initial_used_hours.get(t, 0.0)
        truck_tour_counts[t] = initial_tour_counts.get(t, 0)
        
    combined_sm_hs = bunker_levels.get("1 - Sägemehl", 50) + bunker_levels.get("2 - Hackschnitzel", 50)
    
    # 1. Grund-Kandidaten sammeln (alles was nicht gesperrt ist)
    candidates = []
    for kontingent in offene_kontingente:
        p_name = kontingent.get("produkt")
        b_level = bunker_levels.get(p_name, 50)
        
        # Nur einplanen, wenn der Bunker > 19% ist (Sperre)
        if b_level > 19 and kontingent.get("menge_fuhren", 0) > 0:
            base_score = calculate_base_score(
                prio=kontingent.get("prio", 3), 
                bunker_level=b_level, 
                combined_sm_hs=combined_sm_hs, 
                dauer_h=kontingent.get("dauer_h", 2.0)
            )
            candidates.append({
                "Kunde": kontingent.get("kunde"),
                "Produkt": p_name,
                "dauer_h": kontingent.get("dauer_h", 2.0),
                "base_score": base_score,
                "rest_req": kontingent.get("bemerkung", "Keine"),
                "offene_fuhren": kontingent.get("menge_fuhren", 0)
            })
            
    berechnete_touren = []
    current_last_product = last_booked_product
    
    # 2. Dynamische Verteilung (Sucht in jedem Durchlauf die absolut beste Tour)
    while True:
        best_cand_idx = -1
        best_truck = None
        max_score = -1
        
        for i, cand in enumerate(candidates):
            if cand["offene_fuhren"] <= 0:
                continue
                
            # Score dynamisch mit Wechsel-Bonus berechnen
            current_score = cand["base_score"]
            p_name = cand["Produkt"]
            
            if current_last_product == "1 - Sägemehl" and p_name == "2 - Hackschnitzel":
                current_score += 20
            elif current_last_product == "2 - Hackschnitzel" and p_name == "1 - Sägemehl":
                current_score += 20
                
            # Finde den ersten verfügbaren LKW (in Prio-Reihenfolge)
            truck_fits = None
            for t in active_trucks:
                if truck_used_hours[t] + cand["dauer_h"] <= truck_max_hours[t] + 0.1:
                    truck_fits = t
                    break
                    
            if truck_fits is not None:
                if current_score > max_score:
                    max_score = current_score
                    best_cand_idx = i
                    best_truck = truck_fits
                    
        # Abbruch, wenn keine Tour mehr in einen LKW passt
        if best_cand_idx == -1:
            break 
            
        # 3. Bestes Match verplanen und System aktualisieren
        best_cand = candidates[best_cand_idx]
        best_cand["offene_fuhren"] -= 1
        truck_used_hours[best_truck] += best_cand["dauer_h"]
        truck_tour_counts[best_truck] += 1
        current_last_product = best_cand["Produkt"] # Speichert die Tour für den nächsten Wechsel-Bonus
        
        trip_obj = {
            "Tag": datum.isoformat() if isinstance(datum, (datetime.date, datetime.datetime)) else datum,
            "Fahrzeug": best_truck,
            "Zeitfenster": f"Tour {truck_tour_counts[best_truck]}",
            "Kunde": best_cand["Kunde"],
            "Produkt": best_cand["Produkt"],
            "Menge_m3": truck_cap,
            "dauer_h": best_cand["dauer_h"],
            "score": max_score,
            "is_manual": False,
            "Bemerkung": best_cand["rest_req"]
        }
        berechnete_touren.append(trip_obj)
        
    return berechnete_touren
