import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, date
from streamlit_autorefresh import st_autorefresh
import streamlit_vertical_slider as svs
import database as db

# ==========================================
# PAGE CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Restholz-Tourenplaner", layout="wide", page_icon="🪵")
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
# KONSTANTEN & FUNKTIONEN
# ==========================================
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
WEEKDAYS_GERMAN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
STATUS_VERFUEGBAR = "✅ Verfügbar"
STATUS_AUSFALL = "❌ Ausfall"
STATUS_AUSHILFE = "🟢 Aushilfe (17-21)"
TRUCK_STATUS_OPTIONS = [STATUS_VERFUEGBAR, STATUS_AUSFALL, STATUS_AUSHILFE]

def save_persistent_data():
    data = {
        "shift_hours": st.session_state.get("shift_hours", 9.0),
        "truck_cap": st.session_state.get("truck_cap", 103),
        "truck_status_db": st.session_state.get("truck_status_db", {}),
        "blocked_customers": st.session_state.get("blocked_customers", {}),
        "bunkers": {"bunker_sm": st.session_state.get("bunker_sm", 50), "bunker_hs": st.session_state.get("bunker_hs", 50), "bunker_ri": st.session_state.get("bunker_ri", 50), "bunker_kp": st.session_state.get("bunker_kp", 50)},
        "customer_db": st.session_state.customer_db.to_dict(orient="records"),
        "ext_terminal_db": st.session_state.ext_terminal_db.to_dict(orient="records"),
        "quotas_state": {f"{k[0]}|||{k[1]}": v for k, v in st.session_state.quotas_state.items()},
        "booked_trips": st.session_state.get("booked_trips", []),
        "ext_booked_trips": st.session_state.get("ext_booked_trips", [])
    }
    db.save_app_state(data)

def sync_from_db():
    saved = db.load_app_state()
    st.session_state["shift_hours"] = float(saved.get("shift_hours", 9.0))
    st.session_state["truck_cap"] = int(saved.get("truck_cap", 103))
    st.session_state["truck_status_db"] = saved.get("truck_status_db", {})
    st.session_state["blocked_customers"] = saved.get("blocked_customers", {})
    b = saved.get("bunkers", {})
    st.session_state["bunker_sm"] = b.get("bunker_sm", 50)
    st.session_state["bunker_hs"] = b.get("bunker_hs", 50)
    st.session_state["bunker_ri"] = b.get("bunker_ri", 50)
    st.session_state["bunker_kp"] = b.get("bunker_kp", 50)
    if "booked_trips" not in st.session_state or not st.session_state.get("edit_mode", False):
        st.session_state["booked_trips"] = saved.get("booked_trips", [])
        st.session_state["ext_booked_trips"] = saved.get("ext_booked_trips", [])
    if "customer_db" in saved: st.session_state["customer_db"] = pd.DataFrame(saved["customer_db"])
    if "ext_terminal_db" in saved: st.session_state["ext_terminal_db"] = pd.DataFrame(saved["ext_terminal_db"])
    if "quotas_state" in saved: st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in saved["quotas_state"].items()}

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        return round(int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60.0, 2)
    except: return 2.0

def format_hours(hours_float):
    hrs = int(hours_float)
    mins = int(round((hours_float - hrs) * 60))
    if mins == 60: hrs, mins = hrs + 1, 0
    return f"{hrs:02d}:{mins:02d}"

# ==========================================
# INITIALISIERUNG
# ==========================================
if "edit_mode" not in st.session_state: st.session_state["edit_mode"] = False
if "customer_db" not in st.session_state: st.session_state["customer_db"] = pd.DataFrame()
sync_from_db()

# Hilfsvariablen für Algorithmus (Berechnung nach Sync)
cust_duration_map = {str(r["Kunde"]).strip(): parse_time_str(r.get("Umlaufzeit (hh:mm)", "02:00")) for _, r in st.session_state.customer_db.iterrows() if str(r.get("Kunde")).strip()}
all_customer_names = [str(r["Kunde"]).strip() for _, r in st.session_state.customer_db.iterrows() if str(r.get("Kunde")).strip()]

# ==========================================
# HEADER
# ==========================================
col_logo, col_head, col_date, col_status = st.columns([1.5, 4, 3, 3])
with col_logo:
    if os.path.exists("KELLERHOLZ-CMYK.png"): st.image("KELLERHOLZ-CMYK.png", use_container_width=True)
    else: st.markdown("<h3 style='color:#1b5e20;'>🪵 KELLERHOLZ</h3>", unsafe_allow_html=True)
with col_head: st.title("Restholz-Tourenplaner")
with col_date: selected_date = st.date_input("📅 Planungswoche", value=datetime.today().date())
with col_status:
    st.toggle("✏️ Bearbeitungsmodus", key="edit_mode")
    if st.session_state.edit_mode: st.warning("⏸️ Refresh pausiert")
    else:
        st.success("✅ Live-Sync aktiv")
        st_autorefresh(interval=5000, key="datarefresh")

# ==========================================
# BERECHNUNGEN & UI
# ==========================================
today = datetime.now().date()
start_of_week = selected_date - timedelta(days=selected_date.weekday())
week_dates = [start_of_week + timedelta(days=i) for i in range(5)]

st.subheader("🏭 Bunker-Füllstände (%)")
c1, c2, c3, c4 = st.columns(4)
for col, lbl, key in zip([c1, c2, c3, c4], ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"], ["bunker_sm", "bunker_hs", "bunker_ri", "bunker_kp"]):
    with col:
        v = svs.vertical_slider(key=key, default_value=st.session_state.get(key, 50), step=10, min_value=0, max_value=100)
        if v is not None and v != st.session_state[key]: st.session_state[key] = v; save_persistent_data()
        st.success("Normal" if 10 < st.session_state[key] < 80 else ("GESPERRT" if st.session_state[key] <= 10 else "HOCH"))

tab_dispo, tab_fuhrpark, tab_kontingente, tab_abholungen, tab_kunden, tab_logbuch = st.tabs(["📅 Dispokalender", "🚛 Fuhrparkeinstellungen", "📋 Kontingente", "📦 Abholungen", "👥 Kundendatenbank", "📜 Logbuch"])

with tab_dispo:
    st.markdown("### 🛠️ Manuelle Verbuchung (Eigenfuhrpark)")
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_kunde_raw = m_col1.selectbox("Kunde", list(cust_duration_map.keys()) if cust_duration_map else ["-"], key="m_kunde_sel")
    m_prod = m_col2.selectbox("Produkt", PRODUCT_LIST, key="m_prod_sel")
    m_date = m_col3.date_input("Datum", value=selected_date, key="m_date_sel")
    m_truck = m_col4.selectbox("Fahrzeug", TRUCK_PRIO, key="m_truck_sel")
    if m_col5.button("⚡ Verbuchen", use_container_width=True, type="primary") and m_kunde_raw != "-":
        st.session_state.booked_trips.append({"id": f"man_{datetime.now().timestamp()}", "Datum": m_date.strftime("%Y-%m-%d"), "Fahrzeug": m_truck, "Zeitfenster": "Manuell", "Kunde": m_kunde_raw, "Produkt": m_prod, "Menge_m3": st.session_state.truck_cap, "dauer_h": cust_duration_map.get(m_kunde_raw, 2.0), "score": 99, "is_manual": True})
        save_persistent_data(); st.rerun()
    st.divider()

    # Algorithmus
    bunker_levels = {"1 - Sägemehl": st.session_state.bunker_sm, "2 - Hackschnitzel": st.session_state.bunker_hs, "3 - Rinde": st.session_state.bunker_ri, "4 - Kappholz": st.session_state.bunker_kp}
    remaining_quotas = {}
    for k, v in st.session_state.quotas_state.items():
        already_booked = sum(1 for b in st.session_state.booked_trips if b.get("Kunde") == k[0] and b.get("Produkt") == k[1])
        remaining_quotas[k] = max(0, v.get("soll", 0) - already_booked)

    schedule_by_day = {d.strftime("%Y-%m-%d"): {t: [] for t in TRUCK_PRIO} for d in week_dates}
    truck_used_hours = {d.strftime("%Y-%m-%d"): {t: 0.0 for t in TRUCK_PRIO} for d in week_dates}
    for b in st.session_state.booked_trips:
        if b.get("Datum") in schedule_by_day and b.get("Fahrzeug") in TRUCK_PRIO:
            schedule_by_day[b["Datum"]][b["Fahrzeug"]].append(b)
            truck_used_hours[b["Datum"]][b["Fahrzeug"]] += b.get("dauer_h", 2.0)

    for d_obj in week_dates:
        d_str = d_obj.strftime("%Y-%m-%d")
        if d_obj < today: continue
        active_trucks = [t for t in TRUCK_PRIO if st.session_state.truck_status_db.get(d_str, {}).get(t) != STATUS_AUSFALL]
        extra_d_list = [t for t in TRUCK_PRIO if st.session_state.truck_status_db.get(d_str, {}).get(t) == STATUS_AUSHILFE]
        truck_max_hours = {t: st.session_state.shift_hours + (4.0 if t in extra_d_list else 0.0) for t in active_trucks}
        candidates = []
        for (c_name, p_name), rem_qty in remaining_quotas.items():
            if rem_qty <= 0 or c_name in st.session_state.blocked_customers.get(d_str, []) or bunker_levels.get(p_name, 50) <= 10: continue
            q = st.session_state.quotas_state.get((c_name, p_name), {})
            score = q.get("prio", 3) * 10 + (30 if bunker_levels.get(p_name, 50) >= 80 else (15 if bunker_levels.get(p_name, 50) >= 60 else 0))
            candidates.append({"Kunde": c_name, "Produkt": p_name, "dauer_h": cust_duration_map.get(c_name, 2.0), "score": score, "rest_req": q.get("rest", "Keine")})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        for cand in candidates:
            c_key = (cand["Kunde"], cand["Produkt"])
            while remaining_quotas[c_key] > 0:
                for t in active_trucks:
                    if truck_used_hours[d_str][t] + cand["dauer_h"] <= truck_max_hours[t] + 0.1:
                        start_t = 6.0 + truck_used_hours[d_str][t]
                        schedule_by_day[d_str][t].append({"id": f"auto_{d_str}_{t}_{len(schedule_by_day[d_str][t])}", "Datum": d_str, "Fahrzeug": t, "Zeitfenster": f"{format_hours(start_t)} - {format_hours(start_t + cand['dauer_h'])} Uhr", "Kunde": cand["Kunde"], "Produkt": cand["Produkt"], "dauer_h": cand["dauer_h"], "is_manual": False})
                        truck_used_hours[d_str][t] += cand["dauer_h"]
                        remaining_quotas[c_key] -= 1
                        break
                else: break

    cal_cols = st.columns(5)
    for idx, d_obj in enumerate(week_dates):
        d_str = d_obj.strftime("%Y-%m-%d")
        with cal_cols[idx]:
            st.markdown(f"<div class='cal-day-header' style='background-color:{'#e0e0e0' if d_obj < today else '#f0f2f6'}'>{WEEKDAYS_GERMAN[d_obj.weekday()]}, {d_obj.strftime('%d.%m.')}</div>", unsafe_allow_html=True)
            for t in TRUCK_PRIO:
                status = st.session_state.truck_status_db.get(d_str, {}).get(t, STATUS_VERFUEGBAR)
                if status != STATUS_AUSFALL:
                    st.markdown(f"**🚛 {t}** {'🟢' if status == STATUS_AUSHILFE else '✅'} <small>({format_hours(truck_used_hours[d_str][t])}h)</small>", unsafe_allow_html=True)
                    for trip in schedule_by_day[d_str][t]:
                        st.markdown(f"<div class='{'cal-card-past' if d_obj < today else ('cal-card-manual' if trip.get('is_manual') else 'cal-card')}'><strong>{'🔒' if d_obj < today else ('🛠️' if trip.get('is_manual') else '🤖')} {trip.get('Zeitfenster', '').split(' ')[0]}</strong> | <b>{trip['Kunde']}</b><br><span style='color:#444;'>📦 {trip['Produkt'].split(' - ')[1] if ' - ' in trip['Produkt'] else trip['Produkt']}</span></div>", unsafe_allow_html=True)
                        if not trip.get('is_manual') and d_obj >= today and st.button("📌 Fixieren", key=f"fix_{trip['id']}"):
                            trip["is_manual"] = True
                            save_persistent_data(); st.rerun()

with tab_fuhrpark:
    truck_db = st.session_state.truck_status_db
    day_cols, date_strs = [f"{WEEKDAYS_GERMAN[d.weekday()]}, {d.strftime('%d.%m.')}" for d in week_dates], [d.strftime("%Y-%m-%d") for d in week_dates]
    df = pd.DataFrame([{"Fahrzeug": t, **{col: truck_db.get(d, {}).get(t, STATUS_VERFUEGBAR) for d, col in zip(date_strs, day_cols)}} for t in TRUCK_PRIO])
    edited = st.data_editor(df, use_container_width=True, hide_index=True, column_config={"Fahrzeug": st.column_config.TextColumn(disabled=True), **{c: st.column_config.SelectboxColumn(c, options=TRUCK_STATUS_OPTIONS) for c in day_cols}})
    for _, row in edited.iterrows():
        for d, col in zip(date_strs, day_cols):
            if truck_db.get(d, {}).get(row["Fahrzeug"]) != row[col]:
                if d not in truck_db: truck_db[d] = {}
                truck_db[d][row["Fahrzeug"]] = row[col]
    if st.button("Speichern"): save_persistent_data()

with tab_kontingente:
    # (Logik für Kontingente aus vorherigem Code übernehmen)
    st.write("Kontingent-Tabelle hier einfügen")

with tab_abholungen:
    # (Logik für Abholungen hier einfügen)
    st.write("Abholungen-Tabelle hier einfügen")

with tab_kunden:
    # (Logik für Kundendatenbank hier einfügen)
    st.write("Kundendatenbank hier einfügen")

with tab_logbuch:
    if st.session_state.booked_trips: st.dataframe(pd.DataFrame(st.session_state.booked_trips).sort_values(by="Datum", ascending=False), use_container_width=True, hide_index=True)
