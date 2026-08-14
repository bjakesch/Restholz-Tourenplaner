import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, date

from streamlit_autorefresh import st_autorefresh
import streamlit_vertical_slider as svs

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
# DATEN-SYNCHRONISIERUNG
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
            "bunker_sm": st.session_state.get("bunker_sm", 50),
            "bunker_hs": st.session_state.get("bunker_hs", 50),
            "bunker_ri": st.session_state.get("bunker_ri", 50),
            "bunker_kp": st.session_state.get("bunker_kp", 50)
        },
        "customer_db": st.session_state.customer_db.to_dict(orient="records") if "customer_db" in st.session_state else [],
        "ext_terminal_db": st.session_state.ext_terminal_db.to_dict(orient="records") if "ext_terminal_db" in st.session_state else [],
        "quotas_state": {f"{k[0]}|||{k[1]}": v for k, v in st.session_state.quotas_state.items()} if "quotas_state" in st.session_state else {},
        "booked_trips": st.session_state.get("booked_trips", []),
        "ext_booked_trips": st.session_state.get("ext_booked_trips", [])
    }
    db.save_app_state(data)

def refresh_data_from_db():
    saved_data = load_persistent_data()
    st.session_state["shift_hours"] = float(saved_data.get("shift_hours", 9.0))
    st.session_state["truck_cap"] = int(saved_data.get("truck_cap", 103))
    st.session_state["truck_status_db"] = saved_data.get("truck_status_db", {})
    st.session_state["blocked_customers"] = saved_data.get("blocked_customers", {})
    
    b_saved = saved_data.get("bunkers", {})
    st.session_state["bunker_sm"] = b_saved.get("bunker_sm", 50)
    st.session_state["bunker_hs"] = b_saved.get("bunker_hs", 50)
    st.session_state["bunker_ri"] = b_saved.get("bunker_ri", 50)
    st.session_state["bunker_kp"] = b_saved.get("bunker_kp", 50)
    
    if "booked_trips" not in st.session_state or not st.session_state.get("edit_mode", False):
        st.session_state["booked_trips"] = saved_data.get("booked_trips", [])
        st.session_state["ext_booked_trips"] = saved_data.get("ext_booked_trips", [])
        
    if "customer_db" in saved_data and saved_data["customer_db"]:
        st.session_state["customer_db"] = pd.DataFrame(saved_data["customer_db"])
        
    if "ext_terminal_db" in saved_data and saved_data["ext_terminal_db"]:
        st.session_state["ext_terminal_db"] = pd.DataFrame(saved_data["ext_terminal_db"])
        
    if "quotas_state" in saved_data and saved_data["quotas_state"]:
        st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in saved_data["quotas_state"].items()}

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
# START-INITIALISIERUNG
# ==========================================
if "firebase_loaded" not in st.session_state:
    refresh_data_from_db()
    st.session_state["firebase_loaded"] = True

if "truck_status_db" not in st.session_state: st.session_state["truck_status_db"] = {}
if "blocked_customers" not in st.session_state: st.session_state["blocked_customers"] = {}
if "customer_db" not in st.session_state: st.session_state["customer_db"] = pd.DataFrame()

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
    edit_mode = st.toggle("✏️ Bearbeitungsmodus", value=False, key="edit_mode", help="Pausiert das Live-Laden.")
    
    if edit_mode:
        st.warning("⏸️ Auto-refresh inaktiv")
    else:
        st.success("✅ Autorefresh aktiv (5s)")
        refresh_data_from_db()
        st_autorefresh(interval=5000, limit=None, key="data_refresh")

# ==========================================
# LOGIK & UI
# ==========================================
today = datetime.now().date()
start_of_week = selected_date - timedelta(days=selected_date.weekday())
week_dates = [start_of_week + timedelta(days=i) for i in range(5)]

st.subheader("🏭 Aktuelle Bunker-Füllstände (%)")
col1, col2, col3, col4 = st.columns(4)

def render_bunker(col, title, key, default):
    with col:
        st.markdown(f"<div style='text-align: center;'><strong>{title}</strong></div>", unsafe_allow_html=True)
        
        # Sicherstellen, dass der Key im Session State existiert
        if key not in st.session_state:
            st.session_state[key] = default
            
        old_val = st.session_state[key]
        
        # Sauber an den State gekoppelter Regler (verhindert Einfrieren)
        val = svs.vertical_slider(
            key=key,
            default_value=st.session_state[key],
            step=10,
            min_value=0,
            max_value=100,
            slider_color="#2e7d32",
            track_color="#dcdcdc"
        )
        
        if val is not None and val != old_val:
            st.session_state[key] = val
            save_persistent_data()
            
        current_val = st.session_state[key]
        if current_val <= 10: 
            st.warning("⛔ GESPERRT")
        elif current_val >= 80: 
            st.error("🚨 HOCH")
        else: 
            st.success("✅ Normal")

render_bunker(col1, "1 - Sägemehl", "bunker_sm", 50)
render_bunker(col2, "2 - Hackschnitzel", "bunker_hs", 50)
render_bunker(col3, "3 - Rinde", "bunker_ri", 50)
render_bunker(col4, "4 - Kappholz", "bunker_kp", 50)

st.divider()

edited_cust_db = st.session_state.customer_db
cust_duration_map = {str(r["Kunde"]).strip(): parse_time_str(r["Umlaufzeit (hh:mm)"]) for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()}
all_customer_names = [str(r["Kunde"]).strip() for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()]

tab_dispo, tab_fuhrpark, tab_kontingente, tab_abholungen, tab_kunden, tab_logbuch = st.tabs([
    "📅 Dispokalender", "🚛 Fuhrparkeinstellungen", "📋 Kontingente", "📦 Abholungen", "👥 Kundendatenbank", "📜 Logbuch"
])

with tab_dispo:
    st.markdown("### 🛠️ Manuelle Verbuchung (Eigenfuhrpark)")
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    cust_keys = list(cust_duration_map.keys()) if 'cust_duration_map' in locals() and cust_duration_map else ["-"]
    m_kunde_raw = m_col1.selectbox("Kunde", cust_keys, key="m_kunde_sel")
    m_prod = m_col2.selectbox("Produkt", PRODUCT_LIST, key="m_prod_sel")
    m_date = m_col3.date_input("Datum", value=selected_date, key="m_date_sel")
    m_truck = m_col4.selectbox("Fahrzeug", TRUCK_PRIO, key="m_truck_sel")
    m_dauer = cust_duration_map.get(m_kunde_raw, 2.0) if 'cust_duration_map' in locals() else 2.0
    
    st.markdown("<style>.stButton button { margin-top: 28px; }</style>", unsafe_allow_html=True)
    if m_col5.button("⚡ Verbuchen", use_container_width=True, type="primary") and m_kunde_raw != "-":
        st.session_state.booked_trips.append({"id": f"man_{datetime.now().timestamp()}", "Datum": m_date.strftime("%Y-%m-%d"), "Fahrzeug": m_truck, "Zeitfenster": "Manuell", "Kunde": m_kunde_raw, "Produkt": m_prod, "Menge_m3": st.session_state.truck_cap, "dauer_h": m_dauer, "score": 99, "is_manual": True})
        save_persistent_data()
        st.rerun()
    st.divider()

    bunker_levels = {"1 - Sägemehl": st.session_state.bunker_sm, "2 - Hackschnitzel": st.session_state.bunker_hs, "3 - Rinde": st.session_state.bunker_ri, "4 - Kappholz": st.session_state.bunker_kp}
    remaining_quotas = {}
    for k, v in st.session_state.quotas_state.items():
        already_booked = sum(1 for b in st.session_state.booked_trips if b.get("Kunde") == k[0] and b.get("Produkt") == k[1])
        remaining_quotas[k] = max(0, v.get("soll", 0) - already_booked)

    schedule_by_day = {d.strftime("%Y-%m-%d"): {t: [] for t in TRUCK_PRIO} for d in week_dates}
    truck_used_hours = {d.strftime("%Y-%m-%d"): {t: 0.0 for t in TRUCK_PRIO} for d in week_dates}
    for b in st.session_state.booked_trips:
        b_date, b_truck = b.get("Datum"), b.get("Fahrzeug")
        if b_date in schedule_by_day and b_truck in TRUCK_PRIO:
            schedule_by_day[b_date][b_truck].append(b)
            truck_used_hours[b_date][b_truck] += b.get("dauer_h", 2.0)

    for d_obj in week_dates:
        d_str = d_obj.strftime("%Y-%m-%d")
        if d_obj < today: continue
        active_trucks = [t for t in TRUCK_PRIO if st.session_state.truck_status_db.get(d_str, {}).get(t) != STATUS_AUSFALL]
        extra_d_list = [t for t in TRUCK_PRIO if st.session_state.truck_status_db.get(d_str, {}).get(t) == STATUS_AUSHILFE]
        truck_max_hours = {t: st.session_state.shift_hours + (4.0 if t in extra_d_list else 0.0) for t in active_trucks}
        blocked_customers_today = st.session_state.get("blocked_customers", {}).get(d_str, [])
        candidates = []
        for (c_name, p_name), rem_qty in remaining_quotas.items():
            if rem_qty <= 0 or c_name in blocked_customers_today or bunker_levels.get(p_name, 50) <= 10: continue
            q_info = st.session_state.quotas_state.get((c_name, p_name), {})
            score = q_info.get("prio", 3) * 10 + (30 if bunker_levels.get(p_name, 50) >= 80 else (15 if bunker_levels.get(p_name, 50) >= 60 else 0))
            candidates.append({"Kunde": c_name, "Produkt": p_name, "dauer_h": cust_duration_map.get(c_name, 2.0), "score": score, "rest_req": q_info.get("rest", "Keine")})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            c_key = (cand["Kunde"], cand["Produkt"])
            while remaining_quotas[c_key] > 0:
                assigned = False
                for t in active_trucks:
                    if truck_used_hours[d_str][t] + cand["dauer_h"] <= truck_max_hours[t] + 0.1:
                        start_t = 6.0 + truck_used_hours[d_str][t]
                        schedule_by_day[d_str][t].append({"id": f"auto_{d_str}_{t}_{len(schedule_by_day[d_str][t])}", "Datum": d_str, "Fahrzeug": t, "Zeitfenster": f"{format_hours(start_t)} - {format_hours(start_t + cand['dauer_h'])} Uhr", "Kunde": cand["Kunde"], "Produkt": cand["Produkt"], "Menge_m3": st.session_state.truck_cap, "dauer_h": cand["dauer_h"], "score": cand["score"], "is_manual": False, "Bemerkung": cand["rest_req"]})
                        truck_used_hours[d_str][t] += cand["dauer_h"]
                        remaining_quotas[c_key] -= 1
                        assigned = True
                        break
                if not assigned: break

    cal_cols = st.columns(5)
    for idx, d_obj in enumerate(week_dates):
        d_str = d_obj.strftime("%Y-%m-%d")
        with cal_cols[idx]:
            st.markdown(f"<div class='cal-day-header' style='background-color:{'#e0e0e0' if d_obj < today else '#f0f2f6'}'>{WEEKDAYS_GERMAN[d_obj.weekday()]}, {d_obj.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
            for t in TRUCK_PRIO:
                status = st.session_state.truck_status_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR)
                if status == STATUS_AUSFALL: st.markdown(f"**🚛 {t}** <span style='color:red;'>❌ Ausfall</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**🚛 {t}** {'🟢' if status == STATUS_AUSHILFE else '✅'} <small>({format_hours(truck_used_hours[d_str][t])}h)</small>", unsafe_allow_html=True)
                    for trip in schedule_by_day[d_str][t]:
                        st.markdown(f"<div class='{'cal-card-past' if d_obj < today else ('cal-card-manual' if trip['is_manual'] else 'cal-card')}'><strong>{'🔒' if d_obj < today else ('🛠️' if trip['is_manual'] else '🤖')} {trip.get('Zeitfenster', '').split(' ')[0]}</strong> | <b>{trip['Kunde']}</b><br><span style='color:#444;'>📦 {trip['Produkt'].split(' - ')[1] if ' - ' in trip['Produkt'] else trip['Produkt']}</span></div>", unsafe_allow_html=True)
                        if not trip.get('is_manual', False) and d_obj >= today and st.button(f"📌 Fixieren", key=f"btn_book_{d_str}_{t}_{trip['id']}"):
                            trip["is_manual"] = True
                            st.session_state.booked_trips.append(trip)
                            save_persistent_data()
                            st.rerun()

with tab_fuhrpark:
    truck_db = st.session_state.truck_status_db
    day_cols, date_strs = [], []
    for d_obj in week_dates:
        day_cols.append(f"{WEEKDAYS_GERMAN[d_obj.weekday()]}, {d_obj.strftime('%d.%m.')}")
        date_strs.append(d_obj.strftime("%Y-%m-%d"))
    matrix_rows = [{"Fahrzeug": t, **{col: truck_db.get(d, {}).get(t, STATUS_VERFUEGBAR) for d, col in zip(date_strs, day_cols)}} for t in TRUCK_PRIO]
    edited_trucks = st.data_editor(pd.DataFrame(matrix_rows), use_container_width=True, hide_index=True, column_config={"Fahrzeug": st.column_config.TextColumn("Fahrzeug", disabled=True), **{col: st.column_config.SelectboxColumn(col, options=TRUCK_STATUS_OPTIONS) for col in day_cols}})
    trucks_changed = False
    for _, row in edited_trucks.iterrows():
        t = row["Fahrzeug"]
        for d_str, col_name in zip(date_strs, day_cols):
            if truck_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR) != row[col_name]:
                if d_str not in truck_db: truck_db[d_str] = {}
                truck_db[d_str][t] = row[col_name]
                trucks_changed = True
    if trucks_changed: save_persistent_data()

with tab_kontingente:
    booked_counts_by_cust_prod = {}
    for b in st.session_state.booked_trips: booked_counts_by_cust_prod[(b.get("Kunde"), b.get("Produkt"))] = booked_counts_by_cust_prod.get((b.get("Kunde"), b.get("Produkt")), 0) + 1
    rows = []
    for p_name in PRODUCT_LIST:
        for _, c_row in st.session_state.customer_db.iterrows():
            c_name = str(c_row["Kunde"]).strip()
            if c_name and c_row.get(p_name, False):
                prev = st.session_state.quotas_state.get((c_name, p_name), {"soll": 0, "rest": "Keine", "prio": 3})
                rows.append({"Produkt / Artikel": p_name, "Kunde": f"{c_name} ({c_row.get('Umlaufzeit (hh:mm)', '02:00')})", "SOLL (Geplante Fuhren)": prev["soll"], "IST (Gebucht)": booked_counts_by_cust_prod.get((c_name, p_name), 0), "Fix-Termine / Restriktionen": prev["rest"], "Priorität (1-5)": min(5, max(1, prev.get("prio", 3))), "_Produkt_Raw": p_name, "_Kunde_Raw": c_name})
    edited_quotas = st.data_editor(pd.DataFrame(rows), use_container_width=True, num_rows="fixed", disabled=["Produkt / Artikel", "Kunde", "IST (Gebucht)", "_Produkt_Raw", "_Kunde_Raw"], column_config={"_Produkt_Raw": None, "_Kunde_Raw": None, "SOLL (Geplante Fuhren)": st.column_config.NumberColumn("SOLL", min_value=0, step=1), "Priorität (1-5)": st.column_config.NumberColumn("Prio", min_value=1, max_value=5, step=1)}, hide_index=True)
    for _, row in edited_quotas.iterrows():
        k = (row["_Kunde_Raw"], row["_Produkt_Raw"])
        if st.session_state.quotas_state.get(k) != {"soll": int(row["SOLL (Geplante Fuhren)"]), "rest": str(row["Fix-Termine / Restriktionen"]), "prio": int(row["Priorität (1-5)"])}:
            st.session_state.quotas_state[k] = {"soll": int(row["SOLL (Geplante Fuhren)"]), "rest": str(row["Fix-Termine / Restriktionen"]), "prio": int(row["Priorität (1-5)"])}
            save_persistent_data()
    st.divider()
    st.markdown("#### 🚫 Kundensperren")
    block_date = st.date_input("Datum für Sperre:", value=selected_date)
    block_date_str = block_date.strftime("%Y-%m-%d")
    selected_blocked_custs_ui = st.multiselect(f"Gesperrte Kunden am {block_date.strftime('%d.%m.%Y')}:", options=all_customer_names, default=st.session_state.blocked_customers.get(block_date_str, []))
    if set(st.session_state.blocked_customers.get(block_date_str, [])) != set(selected_blocked_custs_ui):
        st.session_state.blocked_customers[block_date_str] = selected_blocked_custs_ui
        save_persistent_data()

with tab_abholungen:
    edited_ext_db = st.data_editor(st.session_state.ext_terminal_db.reindex(columns=EXT_COL_ORDER), use_container_width=True, num_rows="dynamic", column_config={"Produkt / Artikel": st.column_config.SelectboxColumn("Produkt", options=PRODUCT_LIST), "Einsatztag": st.column_config.TextColumn("Tag(e) (z.B. Montag, Dienstag)")})
    if not edited_ext_db.equals(st.session_state.ext_terminal_db):
        st.session_state.ext_terminal_db = edited_ext_db
        save_persistent_data()
    if not edited_ext_db.empty:
        ext_options = [f"Zeile {idx+1}: {row.get('Produkt / Artikel', '')} ➔ {row.get('Kunde', '')}" for idx, row in edited_ext_db.iterrows()]
        sel = st.selectbox("Tour zum Verbuchen:", options=ext_options)
        if st.button("📌 +1 Verbuchen"):
            row_idx = ext_options.index(sel)
            st.session_state.ext_terminal_db.at[row_idx, "IST (Erfüllt)"] += 1
            booked_row = st.session_state.ext_terminal_db.iloc[row_idx]
            st.session_state.ext_booked_trips.append({"Zeitpunkt": datetime.now().strftime("%d.%m.%Y %H:%M"), "Produkt": booked_row.get("Produkt / Artikel"), "Kunde": booked_row.get("Kunde"), "Spedition": booked_row.get("Frachtführer / Spedition")})
            save_persistent_data()
            st.rerun()

with tab_kunden:
    edited_cust_db_input = st.data_editor(st.session_state.customer_db, num_rows="dynamic", use_container_width=True, column_order=["Kunde", "Umlaufzeit (hh:mm)", "1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"], column_config={"Kunde": st.column_config.TextColumn("Kundenname", required=True)})
    if not edited_cust_db_input.equals(st.session_state.customer_db):
        st.session_state.customer_db = edited_cust_db_input
        save_persistent_data()

with tab_logbuch:
    if st.session_state.booked_trips:
        st.dataframe(pd.DataFrame(st.session_state.booked_trips).sort_values(by="Datum", ascending=False), use_container_width=True, hide_index=True)
        if st.button("❌ Löschen (Letzte Auswahl)"):
            st.session_state.booked_trips.pop()
            save_persistent_data()
            st.rerun()
    if st.session_state.ext_booked_trips: st.dataframe(pd.DataFrame(st.session_state.ext_booked_trips), use_container_width=True, hide_index=True)
