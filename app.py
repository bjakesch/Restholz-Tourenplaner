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
# FUNKTIONEN
# ==========================================
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

def sync_from_db():
    # Nur synchronisieren, wenn NICHT im Bearbeitungsmodus
    if not st.session_state.get("edit_mode", False):
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
        
        st.session_state["booked_trips"] = saved.get("booked_trips", [])
        st.session_state["ext_booked_trips"] = saved.get("ext_booked_trips", [])
        
        if "customer_db" in saved: st.session_state["customer_db"] = pd.DataFrame(saved["customer_db"])
        if "ext_terminal_db" in saved: st.session_state["ext_terminal_db"] = pd.DataFrame(saved["ext_terminal_db"])
        if "quotas_state" in saved: st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in saved["quotas_state"].items()}

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        return round(int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60.0, 2)
    except Exception: return 2.0

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
sync_from_db() # Einmaliger Initial-Sync

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
# UI
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
    # (Manuelle Buchung & Kalender wie gehabt hier einfügen)
    pass # [Hinweis: Hier den bewährten Algorithmus-Block aus dem vorherigen Code einsetzen!]

# ... (Rest der Tabs bleibt wie in der letzten Version, da der Sync jetzt zentral über sync_from_db() gelöst ist)
