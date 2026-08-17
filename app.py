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
    Berechnet den Basis-Score und gibt eine Text-Erklärung (Breakdown) zurück.
    """
    breakdown = []
    
    score = prio * 10
    breakdown.append(f"Grund-Prio ({prio}): +{score}")
    
    if bunker_level >= 80: 
        score += 30  
        breakdown.append(f"Bunker kritisch ({bunker_level}%): +30")
        
    if combined_sm_hs > 130:
        if dauer_h < 2.5:
            score += 50
            breakdown.append("Lager >130% & Kurztour (<2.5h): +50")
        elif dauer_h < 3.0:
            score += 40
            breakdown.append("Lager >130% & Kurztour (<3.0h): +40")
        elif dauer_h < 3.5:
            score += 30
            breakdown.append("Lager >130% & Kurztour (<3.5h): +30")
            
    elif combined_sm_hs < 60:
        if dauer_h > 3.5:
            score += 50
            breakdown.append("Lager <60% & Langtour (>3.5h): +50")
        elif dauer_h > 3.0:
            score += 40
            breakdown.append("Lager <60% & Langtour (>3.0h): +40")
        elif dauer_h > 2.5:
            score += 30
            breakdown.append("Lager <60% & Langtour (>2.5h): +30")
            
    return score, breakdown

def format_hours(hours_float):
    hrs = int(hours_float)
    mins = int(round((hours_float - hrs) * 60))
    if mins == 60: 
        hrs += 1
        mins = 0
    return f"{hrs:02d}:{mins:02d}"

# ==========================================
# HAUPT-ALGORITHMUS ZUR TOURENPLANUNG
# ==========================================
def calculate_tours(datum, offene_kontingente, blocked_trucks=None, extra_drivers=None, bunker_levels=None, shift_hours=STANDARD_SHIFT_HOURS, truck_cap=STANDARD_TRUCK_CAP, initial_used_hours=None, initial_tour_counts=None, last_sm_hs=None):
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
    
    candidates = []
    for kontingent in offene_kontingente:
        p_name = kontingent.get("produkt")
        b_level = bunker_levels.get(p_name, 50)
        
        if b_level > 19 and kontingent.get("menge_fuhren", 0) > 0:
            base_score, breakdown = calculate_base_score(
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
                "breakdown": breakdown,
                "rest_req": kontingent.get("bemerkung", "Keine"),
                "offene_fuhren": kontingent.get("menge_fuhren", 0)
            })
            
    berechnete_touren = []
    
    # Dieser Wert springt nun WÄHREND der Verplanung dynamisch um!
    current_last_sm_hs = last_sm_hs
    
    while True:
        best_cand_idx = -1
        best_truck = None
        max_score = -1
        best_breakdown_str = ""
        
        for i, cand in enumerate(candidates):
            if cand["offene_fuhren"] <= 0:
                continue
                
            current_score = cand["base_score"]
            current_bd = cand["breakdown"].copy()
            p_name = cand["Produkt"]
            
            # Der Wechselbonus (Zick-Zack-Logik)
            if current_last_sm_hs == "1 - Sägemehl" and p_name == "2 - Hackschnitzel":
                current_score += 20
                current_bd.append("Wechselbonus (zuvor wurde Säge verplant): +20")
            elif current_last_sm_hs == "2 - Hackschnitzel" and p_name == "1 - Sägemehl":
                current_score += 20
                current_bd.append("Wechselbonus (zuvor wurde Hack verplant): +20")
                
            truck_fits = None
            best_fit_bonus = 0
            best_fit_reason = ""
            
            for t in active_trucks:
                restzeit = truck_max_hours[t] - truck_used_hours[t]
                
                if cand["dauer_h"] <= restzeit + 0.1:
                    if truck_used_hours[t] > 6.0:
                        luecke = restzeit - cand["dauer_h"]
                        if luecke >= -0.1 and luecke <= 1.0:
                            temp_bonus = 40 
                            if temp_bonus > best_fit_bonus:
                                best_fit_bonus = temp_bonus
                                truck_fits = t
                                best_fit_reason = f"Lückenfüller (Restzeit {restzeit:.1f}h): +40"
                    
                    if truck_fits is None:
                        truck_fits = t
                        
            if best_fit_bonus > 0:
                current_score += best_fit_bonus
                current_bd.append(best_fit_reason)
                
            if truck_fits is not None:
                score_with_tiebreaker = current_score + (cand["dauer_h"] * 0.1)
                
                if score_with_tiebreaker > max_score:
                    max_score = score_with_tiebreaker
                    best_cand_idx = i
                    best_truck = truck_fits
                    best_breakdown_str = "\n".join(current_bd)
                    
        if best_cand_idx == -1:
            break 
            
        best_cand = candidates[best_cand_idx]
        best_cand["offene_fuhren"] -= 1
        truck_used_hours[best_truck] += best_cand["dauer_h"]
        truck_tour_counts[best_truck] += 1
        
        # WICHTIG: Sobald die Tour feststeht, aktualisieren wir den Tracker sofort!
        if best_cand["Produkt"] in ["1 - Sägemehl", "2 - Hackschnitzel"]:
            current_last_sm_hs = best_cand["Produkt"]
        
        trip_obj = {
            "Tag": datum.isoformat() if isinstance(datum, (datetime.date, datetime.datetime)) else datum,
            "Fahrzeug": best_truck,
            "Zeitfenster": f"Tour {truck_tour_counts[best_truck]}",
            "Kunde": best_cand["Kunde"],
            "Produkt": best_cand["Produkt"],
            "Menge_m3": truck_cap,
            "dauer_h": best_cand["dauer_h"],
            "score": int(max_score),
            "score_details": best_breakdown_str, 
            "is_manual": False,
            "Bemerkung": best_cand["rest_req"]
        }
        berechnete_touren.append(trip_obj)
        
    final_touren = []
    for trip in berechnete_touren:
        t = trip["Fahrzeug"]
        if truck_used_hours[t] >= 4.0:
            final_touren.append(trip)
            
    return final_touren
