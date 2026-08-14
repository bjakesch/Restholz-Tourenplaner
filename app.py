import logistics
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, date

from streamlit_autorefresh import st_autorefresh
import database as db

# ==========================================
# PAGE CONFIG & PFADE
# ==========================================
st.set_page_config(page_title="Restholz-Tourenplaner", layout="wide", page_icon="🪵")

# ==========================================
# CUSTOM CSS
# ==========================================
st.markdown("""
    <style>
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] { background-color: #2e7d32 !important; color: white !important; }
    .cal-day-header { background-color: #f0f2f6; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 10px; border: 1px solid #dcdcdc; }
    .cal-card { border-left: 4px solid #1b5e20; background-color: #ffffff; padding: 6px 8px; border-radius: 4px; margin-bottom: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 0.85em; }
    .cal-card-manual { border-left: 4px solid #1976d2; background-color: #f5f9ff; }
    .cal-card-past { border-left: 4px solid #9e9e9e; background-color: #f5f5f5; color: #777;}
    .stButton button { margin-top: 28px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# KONSTANTEN
# ==========================================
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
WEEKDAYS_GERMAN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
EXT_COL_ORDER = ["Produkt / Artikel", "Kunde", "Frachtführer / Spedition", "SOLL (Fuhren)", "IST (Erfüllt)", "Einsatztag", "Bemerkung / Uhrzeit"]

STATUS_VERFUEGBAR = "✅ Verfügbar"
STATUS_AUSFALL = "❌ Ausfall"
STATUS_AUSHILFE = "🟢 Aushilfe (17-21)"
TRUCK_STATUS_OPTIONS = [STATUS_VERFUEGBAR, STATUS_AUSFALL, STATUS_AUSHILFE]

# ==========================================
# DATEN-SYNCHRONISIERUNG (VERSION KEY PATTERN)
# ==========================================
def load_persistent_data():
    return db.load_app_state()

def save_persistent_data():
    data = {
        "shift_hours": st.session_state.get("shift_hours", 9.0),
        "truck_cap": st.session_state.get("truck_cap", 103),
        "truck_status_db": st.session_state.get("truck_status_db", {}),
        "blocked_customers": st.session_state.get("blocked_customers", {}),
        "bunkers": {
            "bunker_sm": int(st.session_state.get("bunker_sm", 50)),
            "bunker_hs": int(st.session_state.get("bunker_hs", 50)),
            "bunker_ri": int(st.session_state.get("bunker_ri", 50)),
            "bunker_kp": int(st.session_state.get("bunker_kp", 50))
        },
        "customer_db": st.session_state.customer_db.to_dict(orient="records") if "customer_db" in st.session_state else [],
        "ext_terminal_db": st.session_state.ext_terminal_db.to_dict(orient="records") if "ext_terminal_db" in st.session_state else [],
        "quotas_state": {f"{k[0]}|||{k[1]}": v for k, v in st.session_state.quotas_state.items()} if "quotas_state" in st.session_state else {},
        "booked_trips": st.session_state.get("booked_trips", []),
        "ext_booked_trips": st.session_state.get("ext_booked_trips", [])
    }
    db.save_app_state(data)

def sync_from_db():
    if not st.session_state.get("edit_mode", False):
        saved = load_persistent_data()
        if not saved: return
        
        # 1. Bunker (mit Versions-Kontrolle für die UI)
        b_saved = saved.get("bunkers", {})
        for k in ["bunker_sm", "bunker_hs", "bunker_ri", "bunker_kp"]:
            remote_val = b_saved.get(k, 50)
            local_val = st.session_state.get(k, 50)
            if int(remote_val) != int(local_val):
                st.session_state[k] = int(remote_val)
                # Erhöht die Version -> UI zeichnet den Regler neu
                v_key = f"{k}_version"
                st.session_state[v_key] = st.session_state.get(v_key, 0) + 1
                    
        # 2. Allgemeine Einstellungen
        for k in ["shift_hours", "truck_cap"]:
            r_val = saved.get(k)
            if r_val is not None and st.session_state.get(k) != r_val:
                st.session_state[k] = r_val
                
        # 3. Dataframes & komplexe Strukturen (mit Versions-Kontrolle)
        new_trucks = saved.get("truck_status_db", {})
        if st.session_state.get("truck_status_db", {}) != new_trucks:
            st.session_state["truck_status_db"] = new_trucks
            st.session_state["truck_db_version"] = st.session_state.get("truck_db_version", 0) + 1
            
        new_cust_df = pd.DataFrame(saved.get("customer_db", []))
        if "customer_db" not in st.session_state or not new_cust_df.equals(st.session_state["customer_db"]):
            st.session_state["customer_db"] = new_cust_df
            st.session_state["cust_db_version"] = st.session_state.get("cust_db_version", 0) + 1

        new_ext_df = pd.DataFrame(saved.get("ext_terminal_db", []))
        if "ext_terminal_db" not in st.session_state or not new_ext_df.equals(st.session_state["ext_terminal_db"]):
            st.session_state["ext_terminal_db"] = new_ext_df
            st.session_state["ext_db_version"] = st.session_state.get("ext_db_version", 0) + 1
            
        new_quotas = {tuple(k.split("|||")): v for k, v in saved.get("quotas_state", {}).items()}
        if st.session_state.get("quotas_state", {}) != new_quotas:
            st.session_state["quotas_state"] = new_quotas
            st.session_state["quotas_version"] = st.session_state.get("quotas_version", 0) + 1

        # 4. Listen
        st.session_state["booked_trips"] = saved.get("booked_trips", [])
        st.session_state["ext_booked_trips"] = saved.get("ext_booked_trips", [])
        st.session_state["blocked_customers"] = saved.get("blocked_customers", {})

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        return round(int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60.0, 2)
    except Exception:
        return 2.0

def format_hours(hours_float):
    hrs = int(hours_float)
    mins = int(round((hours_float - hrs) * 60))
    if mins == 60: hrs, mins = hrs + 1, 0
    return f"{hrs:02d}:{mins:02d}"

# ==========================================
# INITIALISIERUNG
# ==========================================
if "edit_mode" not in st.session_state: 
    st.session_state["edit_mode"] = False

sync_from_db()

# Fallback für leere Datenbanken
if "customer_db" not in st.session_state or st.session_state["customer_db"].empty:
    st.session_state["customer_db"] = pd.DataFrame([
        {"Kunde": "SIAT Urmatt", "Umlaufzeit (hh:mm)": "03:55", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False}
    ])

# ==========================================
# HEADER & REFRESH-STEUERUNG
# ==========================================
col_logo, col_head, col_date, col_status = st.columns([1.5, 4, 3, 3])

with col_logo:
    if os.path.exists("KELLERHOLZ-CMYK.png"):
        st.image("KELLERHOLZ-CMYK.png", use_container_width=True)
    else:
        st.markdown("<h3 style='color:#1b5e20;'>🪵 KELLERHOLZ</h3>", unsafe_allow_html=True)

with col_head:
    st.title("Restholz-Tourenplaner")

with col_date:
    st.write("") 
    selected_date = st.date_input("📅 Planungswoche (beliebiger Tag)", value=datetime.today().date())

with col_status:
    st.write("") 
    edit_mode = st.toggle("✏️ Bearbeitungsmodus", value=st.session_state.get("edit_mode", False), key="edit_mode", help="Pausiert das Live-Laden.")
    
    if edit_mode:
        st.warning("⏸️ Auto-refresh inaktiv")
    else:
        st.success("✅ Autorefresh aktiv (10s)")
        sync_from_db() 
        st_autorefresh(interval=10000, limit=None, key="data_refresh")

# ==========================================
# LOGIK & HILFSVARIABLEN
# ==========================================
today = datetime.now().date()
start_of_week = selected_date - timedelta(days=selected_date.weekday())
week_dates = [start_of_week + timedelta(days=i) for i in range(5)]

edited_cust_db = st.session_state.customer_db
cust_duration_map = {str(r["Kunde"]).strip(): parse_time_str(r["Umlaufzeit (hh:mm)"]) for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()}
all_customer_names = [str(r["Kunde"]).strip() for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()]

# ==========================================
# BUNKER-FÜLLSTÄNDE (JETZT MIT NATIVEM SLIDER)
# ==========================================
st.subheader("🏭 Aktuelle Bunker-Füllstände (%)")
col1, col2, col3, col4 = st.columns(4)

def render_bunker(col, title, db_key):
    with col:
        st.markdown(f"<div style='text-align: center;'><strong>{title}</strong></div>", unsafe_allow_html=True)
        
        v_key = f"{db_key}_version"
        current_val = int(st.session_state.get(db_key, 50))
        slider_key = f"slider_{db_key}_{st.session_state.get(v_key, 0)}"
        
        # Stabiler nativer Streamlit Slider
        val = st.slider(
            label=title,
            min_value=0,
            max_value=100,
            value=current_val,
            step=10,
            key=slider_key,
            label_visibility="collapsed"
        )
        
        # Wenn der Nutzer den Regler verstellt hat
        if val != current_val:
            st.session_state[db_key] = val
            save_persistent_data()
            st.rerun()
            
        display_val = int(st.session_state.get(db_key, 50))
        
        # Exakte Schwellenwerte
        if display_val <= 19: 
            st.warning("⛔ GESPERRT")
        elif display_val >= 80: 
            st.error("🚨 HOCH")
        else: 
            st.success("✅ Normal")

render_bunker(col1, "1 - Sägemehl", "bunker_sm")
render_bunker(col2, "2 - Hackschnitzel", "bunker_hs")
render_bunker(col3, "3 - Rinde", "bunker_ri")
render_bunker(col4, "4 - Kappholz", "bunker_kp")

st.divider()

# ==========================================
# WORKSPACES (TABS)
# ==========================================
tab_dispo, tab_fuhrpark, tab_kontingente, tab_abholungen, tab_kunden, tab_logbuch = st.tabs([
    "📅 Dispokalender", 
    "🚛 Fuhrparkeinstellungen", 
    "📋 Kontingente", 
    "📦 Abholungen",
    "👥 Kundendatenbank", 
    "📜 Logbuch"
])

# ------------------------------------------
# TAB 1: DISPOKALENDER (inkl. Manueller Buchung)
# ------------------------------------------
with tab_dispo:
    st.markdown("### 🛠️ Manuelle Verbuchung (Eigenfuhrpark)")
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    
    cust_keys = list(cust_duration_map.keys()) if cust_duration_map else ["-"]
    
    m_kunde_raw = m_col1.selectbox("Kunde", cust_keys, key="m_kunde_sel")
    m_prod = m_col2.selectbox("Produkt", PRODUCT_LIST, key="m_prod_sel")
    m_date = m_col3.date_input("Datum", value=selected_date, key="m_date_sel")
    m_truck = m_col4.selectbox("Fahrzeug", TRUCK_PRIO, key="m_truck_sel")
    m_dauer = cust_duration_map.get(m_kunde_raw, 2.0)
    
    if m_col5.button("⚡ Verbuchen", use_container_width=True, type="primary") and m_kunde_raw != "-":
        d_str_manual = m_date.strftime("%Y-%m-%d")
        m_id = f"manual_{d_str_manual}_{m_truck}_{m_kunde_raw}_{m_prod}_{len(st.session_state.booked_trips)}"
        st.session_state.booked_trips.append({
            "id": m_id, "Datum": d_str_manual, "Fahrzeug": m_truck, "Zeitfenster": "Manuell",
            "Kunde": m_kunde_raw, "Produkt": m_prod, "Menge_m3": st.session_state.truck_cap, "dauer_h": m_dauer,
            "score": 99, "is_manual": True
        })
        save_persistent_data()
        st.success("Tour manuell verbucht!")
        st.rerun()

    st.divider()

    # Algorithmus
    bunker_levels = {
        "1 - Sägemehl": int(st.session_state.get("bunker_sm", 50)),
        "2 - Hackschnitzel": int(st.session_state.get("bunker_hs", 50)),
        "3 - Rinde": int(st.session_state.get("bunker_ri", 50)),
        "4 - Kappholz": int(st.session_state.get("bunker_kp", 50)),
    }

    remaining_quotas = {}
    for k, v in st.session_state.quotas_state.items():
        already_booked = sum(1 for b in st.session_state.booked_trips if b.get("Kunde") == k[0] and b.get("Produkt") == k[1])
        remaining_quotas[k] = max(0, v.get("soll", 0) - already_booked)

    schedule_by_day = {d.strftime("%Y-%m-%d"): {t: [] for t in TRUCK_PRIO} for d in week_dates}
    truck_used_hours = {d.strftime("%Y-%m-%d"): {t: 0.0 for t in TRUCK_PRIO} for d in week_dates}

    for b in st.session_state.booked_trips:
        b_date = b.get("Datum")
        b_truck = b.get("Fahrzeug")
        if b_date in schedule_by_day and b_truck in TRUCK_PRIO:
            if "score" not in b: b["score"] = 99
            schedule_by_day[b_date][b_truck].append(b)
            truck_used_hours[b_date][b_truck] += b.get("dauer_h", 2.0)

    for d_obj in week_dates:
        d_str = d_obj.strftime("%Y-%m-%d")
        if d_obj < today: continue
            
        active_trucks = []
        extra_d_list = []
        for t in TRUCK_PRIO:
            status = st.session_state.truck_status_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR)
            if status != STATUS_AUSFALL:
                active_trucks.append(t)
            if status == STATUS_AUSHILFE:
                extra_d_list.append(t)
                
        truck_max_hours = {t: st.session_state.shift_hours + (4.0 if t in extra_d_list else 0.0) for t in active_trucks}
        blocked_customers_today = st.session_state.get("blocked_customers", {}).get(d_str, [])

        candidates = []
        for (c_name, p_name), rem_qty in remaining_quotas.items():
            if rem_qty <= 0 or c_name in blocked_customers_today: continue
            
            b_level = bunker_levels.get(p_name, 50)
            if b_level <= 19: continue # Sperrt Fuhren wenn Bunker <= 19%
                
            dur = cust_duration_map.get(c_name, 2.0)
            q_info = st.session_state.quotas_state.get((c_name, p_name), {})
            
            score = q_info.get("prio", 3) * 10
            if b_level >= 80: score += 30
            elif b_level >= 60: score += 15
            
            candidates.append({"Kunde": c_name, "Produkt": p_name, "dauer_h": dur, "score": score, "rest_req": q_info.get("rest", "Keine")})
            
        candidates.sort(key=lambda x: x["score"], reverse=True)

        for cand in candidates:
            c_key = (cand["Kunde"], cand["Produkt"])
            while remaining_quotas[c_key] > 0:
                assigned = False
                for t in active_trucks:
                    if truck_used_hours[d_str][t] + cand["dauer_h"] <= truck_max_hours[t] + 0.1:
                        start_t = 6.0 + truck_used_hours[d_str][t]
                        schedule_by_day[d_str][t].append({
                            "id": f"auto_{d_str}_{t}_{len(schedule_by_day[d_str][t])}", "Datum": d_str, "Fahrzeug": t,
                            "Zeitfenster": f"{format_hours(start_t)} - {format_hours(start_t + cand['dauer_h'])} Uhr",
                            "Kunde": cand["Kunde"], "Produkt": cand["Produkt"], "Menge_m3": st.session_state.truck_cap,
                            "dauer_h": cand["dauer_h"], "score": cand["score"], "is_manual": False, "Bemerkung": cand["rest_req"]
                        })
                        truck_used_hours[d_str][t] += cand["dauer_h"]
                        remaining_quotas[c_key] -= 1
                        assigned = True
                        break
                if not assigned: break

    cal_cols = st.columns(5)
    for idx, d_obj in enumerate(week_dates):
        d_str = d_obj.strftime("%Y-%m-%d")
        w_day = WEEKDAYS_GERMAN[d_obj.weekday()]
        is_past = d_obj < today
        
        with cal_cols[idx]:
            header_color = "#e0e0e0" if is_past else "#f0f2f6"
            st.markdown(f"<div class='cal-day-header' style='background-color:{header_color}'>{w_day}, {d_obj.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
            
            for t in TRUCK_PRIO:
                status = st.session_state.truck_status_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR)
                
                if status == STATUS_AUSFALL:
                    st.markdown(f"**🚛 {t}** <span style='color:red;'>❌ Ausfall</span>", unsafe_allow_html=True)
                else:
                    badge = "🟢" if status == STATUS_AUSHILFE else "✅"
                    st.markdown(f"**🚛 {t}** {badge} <small>({format_hours(truck_used_hours[d_str][t])}h)</small>", unsafe_allow_html=True)
                    
                    for trip in schedule_by_day[d_str][t]:
                        is_man = trip.get("is_manual", False)
                        
                        if is_past: 
                            card_class, tag_type = "cal-card-past", "🔒"
                        else:
                            card_class, tag_type = ("cal-card-manual", "🛠️") if is_man else ("cal-card", "🤖")
                            
                        st.markdown(f"""
                        <div class="{card_class}">
                            <strong>{tag_type} {trip.get('Zeitfenster', '').split(' ')[0]}</strong> | <b>{trip['Kunde']}</b><br>
                            <span style="color:#444;">📦 {trip['Produkt'].split(' - ')[1] if ' - ' in trip['Produkt'] else trip['Produkt']}</span>
                        </div>""", unsafe_allow_html=True)
                        
                        if not is_man and not is_past:
                            if st.button(f"📌 Fixieren", key=f"btn_book_{d_str}_{t}_{trip['id']}"):
                                trip["is_manual"] = True
                                st.session_state.booked_trips.append(trip)
                                save_persistent_data()
                                st.rerun()

# ------------------------------------------
# TAB 2: FUHRPARKEINSTELLUNGEN
# ------------------------------------------
with tab_fuhrpark:
    st.subheader("Allgemeine Kapazitäten")
    c_set1, c_set2 = st.columns(2)
    new_shift = c_set1.number_input("Max. Schichtzeit (Std./Tag)", step=0.5, value=st.session_state.shift_hours)
    new_cap = c_set2.number_input("Kapazität Sattelzug (m³)", step=1, value=st.session_state.truck_cap)
    if new_shift != st.session_state.shift_hours or new_cap != st.session_state.truck_cap:
        st.session_state.shift_hours = new_shift
        st.session_state.truck_cap = new_cap
        save_persistent_data()
        
    st.divider()
    st.subheader("Fahrzeug-Verfügbarkeit (Wochen-Matrix)")
    
    truck_db = st.session_state.truck_status_db
    day_cols = []
    date_strs = []
    for d_obj in week_dates:
        d_str = d_obj.strftime("%Y-%m-%d")
        col_name = f"{WEEKDAYS_GERMAN[d_obj.weekday()]}, {d_obj.strftime('%d.%m.')}"
        day_cols.append(col_name)
        date_strs.append(d_str)

    matrix_rows = []
    for t in TRUCK_PRIO:
        row = {"Fahrzeug": t}
        for d_str, col_name in zip(date_strs, day_cols):
            row[col_name] = truck_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR)
        matrix_rows.append(row)
            
    df_truck_status = pd.DataFrame(matrix_rows)
    
    col_config = {"Fahrzeug": st.column_config.TextColumn("Fahrzeug", disabled=True)}
    for col_name in day_cols:
        col_config[col_name] = st.column_config.SelectboxColumn(col_name, options=TRUCK_STATUS_OPTIONS, width="medium")
    
    edited_trucks = st.data_editor(
        df_truck_status,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        key=f"truck_matrix_editor_{st.session_state.get('truck_db_version', 0)}" 
    )
    
    trucks_changed = False
    for _, row in edited_trucks.iterrows():
        t = row["Fahrzeug"]
        for d_str, col_name in zip(date_strs, day_cols):
            new_status = row[col_name]
            if d_str not in truck_db: truck_db[d_str] = {}
            if truck_db[d_str].get(t, STATUS_VERFUEGBAR) != new_status:
                truck_db[d_str][t] = new_status
                trucks_changed = True
                
    if trucks_changed:
        st.session_state.truck_status_db = truck_db
        save_persistent_data()

# ------------------------------------------
# TAB 3: KONTINGENTE & SPERREN
# ------------------------------------------
with tab_kontingente:
    st.markdown("### 📋 Wochen-Kontingente (Eigenfuhrpark)")
    booked_counts_by_cust_prod = {}
    for b in st.session_state.booked_trips:
        key = (b.get("Kunde"), b.get("Produkt"))
        booked_counts_by_cust_prod[key] = booked_counts_by_cust_prod.get(key, 0) + 1

    initial_quota_rows = []
    for p_name in PRODUCT_LIST:
        for _, c_row in st.session_state.customer_db.iterrows():
            c_name = str(c_row["Kunde"]).strip()
            if not c_name: continue
            
            t_str = str(c_row.get("Umlaufzeit (hh:mm)", "02:00"))
            if c_row.get(p_name, False):
                key = (c_name, p_name)
                prev = st.session_state.quotas_state.get(key, {"soll": 0, "rest": "Keine", "prio": 3})
                ist = booked_counts_by_cust_prod.get(key, 0)
                
                initial_quota_rows.append({
                    "Produkt / Artikel": p_name,
                    "Kunde": f"{c_name} ({t_str})",
                    "SOLL (Geplante Fuhren)": prev["soll"],
                    "IST (Gebucht)": ist,
                    "Fix-Termine / Restriktionen": prev["rest"],
                    "Priorität (1-5)": min(5, max(1, prev.get("prio", 3))),
                    "_Produkt_Raw": p_name,
                    "_Kunde_Raw": c_name
                })

    edited_quotas = st.data_editor(
        pd.DataFrame(initial_quota_rows),
        use_container_width=True,
        num_rows="fixed",
        disabled=["Produkt / Artikel", "Kunde", "IST (Gebucht)", "_Produkt_Raw", "_Kunde_Raw"],
        column_config={
            "_Produkt_Raw": None, "_Kunde_Raw": None,
            "Produkt / Artikel": st.column_config.TextColumn("Produkt / Artikel", width="medium"),
            "Kunde": st.column_config.TextColumn("Kunde (Umlaufzeit)", width="medium"),
            "SOLL (Geplante Fuhren)": st.column_config.NumberColumn("SOLL", min_value=0, max_value=50, step=1),
            "IST (Gebucht)": st.column_config.NumberColumn("IST", min_value=0, max_value=50),
            "Fix-Termine / Restriktionen": st.column_config.TextColumn("Restriktionen", width="large"),
            "Priorität (1-5)": st.column_config.NumberColumn("Prio", min_value=1, max_value=5, step=1)
        },
        hide_index=True,
        key=f"quotas_editor_{st.session_state.get('quotas_version', 0)}"
    )

    quotas_changed = False
    for _, row in edited_quotas.iterrows():
        k = (row["_Kunde_Raw"], row["_Produkt_Raw"])
        new_val = {"soll": int(row["SOLL (Geplante Fuhren)"]), "rest": str(row["Fix-Termine / Restriktionen"]), "prio": int(row["Priorität (1-5)"])}
        if st.session_state.quotas_state.get(k) != new_val:
            st.session_state.quotas_state[k] = new_val
            quotas_changed = True

    if quotas_changed:
        save_persistent_data()

    st.divider()
    st.markdown("#### 🚫 Kundensperren / Annahmestopp")
    
    c_block1, c_block2 = st.columns([1, 2])
    block_date = c_block1.date_input("Datum für Sperre auswählen:", value=selected_date, key="block_date_input")
    block_date_str = block_date.strftime("%Y-%m-%d")

    current_blocked = st.session_state.get("blocked_customers", {}).get(block_date_str, [])
    valid_blocked = [c for c in current_blocked if c in all_customer_names]

    selected_blocked_custs_ui = c_block2.multiselect(
        f"Gesperrte Kunden am {block_date.strftime('%d.%m.%Y')}:",
        options=all_customer_names,
        default=valid_blocked,
        key=f"block_cust_ui_{block_date_str}"
    )

    blocked_dict = st.session_state.get("blocked_customers", {})
    if set(blocked_dict.get(block_date_str, [])) != set(selected_blocked_custs_ui):
        blocked_dict[block_date_str] = selected_blocked_custs_ui
        st.session_state["blocked_customers"] = blocked_dict
        save_persistent_data()

# ------------------------------------------
# TAB 4: ABHOLUNGEN
# ------------------------------------------
with tab_abholungen:
    st.markdown("### 🚛 Fremdspeditionen (Abholungen)")
    ext_df_display = st.session_state.ext_terminal_db.reindex(columns=EXT_COL_ORDER)

    edited_ext_db = st.data_editor(
        ext_df_display,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Produkt / Artikel": st.column_config.SelectboxColumn("Produkt", options=PRODUCT_LIST, default="1 - Sägemehl"),
            "Kunde": st.column_config.TextColumn("Kunde (Freitext)", default="", required=True),
            "Frachtführer / Spedition": st.column_config.TextColumn("Spedition", default="", required=True),
            "SOLL (Fuhren)": st.column_config.NumberColumn("SOLL", min_value=0, max_value=100, step=1, default=0),
            "IST (Erfüllt)": st.column_config.NumberColumn("IST", min_value=0, max_value=100, step=1, default=0),
            "Einsatztag": st.column_config.TextColumn("Tag(e) (z.B. Montag, Dienstag)", default=""),
        },
        hide_index=True,
        key=f"ext_terminal_editor_{st.session_state.get('ext_db_version', 0)}"
    )

    if not edited_ext_db.equals(st.session_state.ext_terminal_db):
        st.session_state.ext_terminal_db = edited_ext_db
        save_persistent_data()

    if not edited_ext_db.empty:
        col_sel, col_btn_ext = st.columns([3, 1])
        ext_options = []
        for idx, row in edited_ext_db.iterrows():
            prod = str(row.get("Produkt / Artikel", ""))
            cust = str(row.get("Kunde", "")).strip() or "Unbekannt"
            sped = str(row.get("Frachtführer / Spedition", "")).strip() or "Unbekannt"
            ext_options.append(f"Zeile {idx+1}: {prod} ➔ {cust} ({sped}) | IST: {row.get('IST (Erfüllt)', 0)}/{row.get('SOLL (Fuhren)', 0)}")
        
        selected_ext_idx_str = col_sel.selectbox("Tour zum Verbuchen auswählen:", options=ext_options, key="ext_book_select")
        
        if col_btn_ext.button("📌 +1 Verbuchen", use_container_width=True, type="primary"):
            row_idx = ext_options.index(selected_ext_idx_str)
            st.session_state.ext_terminal_db.at[row_idx, "IST (Erfüllt)"] += 1
            
            booked_row = st.session_state.ext_terminal_db.iloc[row_idx]
            st.session_state.ext_booked_trips.append({
                "Zeitpunkt": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "Produkt": booked_row.get("Produkt / Artikel"),
                "Kunde": booked_row.get("Kunde"),
                "Spedition": booked_row.get("Frachtführer / Spedition"),
                "Einsatztag": booked_row.get("Einsatztag") or "Keiner"
            })
            save_persistent_data()
            st.success("Fremdfuhre verbucht!")
            st.rerun()

# ------------------------------------------
# TAB 5: KUNDENDATENBANK
# ------------------------------------------
with tab_kunden:
    st.markdown("### 👥 Kundendatenbank (Stammdaten)")
    edited_cust_db_input = st.data_editor(
        st.session_state.customer_db,
        num_rows="dynamic",
        use_container_width=True,
        column_order=["Kunde", "Umlaufzeit (hh:mm)", "1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"],
        column_config={
            "Kunde": st.column_config.TextColumn("Kundenname", required=True),
            "Umlaufzeit (hh:mm)": st.column_config.TextColumn("Umlaufzeit (hh:mm)", default="02:00", required=True),
            "1 - Sägemehl": st.column_config.CheckboxColumn("Sägemehl", default=False),
            "2 - Hackschnitzel": st.column_config.CheckboxColumn("Hackschnitzel", default=False),
            "3 - Rinde": st.column_config.CheckboxColumn("Rinde", default=False),
            "4 - Kappholz": st.column_config.CheckboxColumn("4 - Kappholz", default=False),
        },
        hide_index=True,
        key=f"customer_editor_{st.session_state.get('cust_db_version', 0)}"
    )
    if not edited_cust_db_input.equals(st.session_state.customer_db):
        st.session_state.customer_db = edited_cust_db_input
        save_persistent_data()

# ------------------------------------------
# TAB 6: LOGBUCH
# ------------------------------------------
with tab_logbuch:
    col_log_own, col_log_ext = st.columns(2)
    
    # ---------------- EIGENFUHRPARK ----------------
    with col_log_own:
        st.markdown("### 🚛 Eigenfuhrpark (Diese Woche)")
        
        # Nur Touren filtern, die in den eingestellten Wochentagen liegen
        valid_date_strs = [d.strftime("%Y-%m-%d") for d in week_dates]
        week_own_trips = [b for b in st.session_state.booked_trips if b.get("Datum") in valid_date_strs]
        
        if week_own_trips:
            df_booked = pd.DataFrame(week_own_trips)
            df_booked = df_booked.sort_values(by="Datum", ascending=False)
            st.dataframe(df_booked, use_container_width=True, hide_index=True)
            
            st.divider()
            c_del1, c_del2 = st.columns([3, 1])
            selected_del_id = c_del1.selectbox("Tour stornieren:", options=[b.get("id") for b in week_own_trips if "id" in b], key="del_trip_select_box")
            
            if c_del2.button("❌ Löschen", use_container_width=True, type="secondary", key="del_btn_own"):
                st.session_state.booked_trips = [b for b in st.session_state.booked_trips if b.get("id") != selected_del_id]
                save_persistent_data()
                st.rerun()
        else:
            st.info("In dieser Woche wurden noch keine Touren für den Eigenfuhrpark verbucht.")

    # ---------------- FREMDFUHREN ----------------
    with col_log_ext:
        st.markdown("### 📦 Fremdfuhren (Diese Woche)")
        
        week_ext_trips = []
        week_ext_indices = []
        
        # Prüfen, ob der Buchungs-Zeitpunkt in die eingestellte Woche (Mo-So) fällt
        for i, b in enumerate(st.session_state.ext_booked_trips):
            z_str = str(b.get("Zeitpunkt", ""))
            try:
                # Format aus der Buchung ist "%d.%m.%Y %H:%M"
                b_date = datetime.strptime(z_str.split(" ")[0], "%d.%m.%Y").date()
                if start_of_week <= b_date <= (start_of_week + timedelta(days=6)):
                    week_ext_trips.append(b)
                    week_ext_indices.append(i) # Den Original-Index merken wir uns für sauberes Löschen
            except Exception:
                pass
                
        if week_ext_trips:
            df_ext = pd.DataFrame(week_ext_trips)
            df_ext = df_ext.iloc[::-1] # Reihenfolge umdrehen (neueste oben)
            st.dataframe(df_ext, use_container_width=True, hide_index=True)
            
            st.divider()
            c_del_ext1, c_del_ext2 = st.columns([3, 1])
            
            # String bauen für die Dropdown-Auswahl (inklusive dem unsichtbaren Index ganz vorn)
            ext_del_options = [f"{orig_idx} | {st.session_state.ext_booked_trips[orig_idx].get('Zeitpunkt')} - {st.session_state.ext_booked_trips[orig_idx].get('Kunde')}" for orig_idx in week_ext_indices]
            
            selected_del_ext_str = c_del_ext1.selectbox("Fremdfuhre stornieren:", options=ext_del_options, key="del_ext_select_box")
            
            if c_del_ext2.button("❌ Löschen", use_container_width=True, type="secondary", key="del_btn_ext"):
                # Echten Index extrahieren und aus der Liste werfen
                idx_to_del = int(selected_del_ext_str.split(" | ")[0])
                deleted_trip = st.session_state.ext_booked_trips.pop(idx_to_del)
                
                # ZUSATZLOGIK: Den IST-Zähler beim Kunden wieder um 1 reduzieren!
                for idx, row in st.session_state.ext_terminal_db.iterrows():
                    if (row.get("Produkt / Artikel") == deleted_trip.get("Produkt") and 
                        row.get("Kunde") == deleted_trip.get("Kunde") and 
                        row.get("Frachtführer / Spedition") == deleted_trip.get("Spedition")):
                        
                        if st.session_state.ext_terminal_db.at[idx, "IST (Erfüllt)"] > 0:
                            st.session_state.ext_terminal_db.at[idx, "IST (Erfüllt)"] -= 1
                        break # Nur einmal abziehen
                        
                save_persistent_data()
                st.rerun()
        else:
            st.info("In dieser Woche wurden noch keine Fremdfuhren verbucht.")
