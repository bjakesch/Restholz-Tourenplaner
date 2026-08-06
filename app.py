import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ==========================================
# PAGE CONFIG & PFADE
# ==========================================
st.set_page_config(page_title="Restholz-Tourenplaner Sägewerk", layout="wide", page_icon="🪵")

# Auto-Refresh alle 2000 ms (2 Sekunden)
st_autorefresh(interval=2000, key="auto_reload")

# ==========================================
# CUSTOM CSS (FARBANPASSUNG AUSHILFSFAHRER)
# ==========================================
st.markdown("""
    <style>
    /* MultiSelect-Badges für Aushilfsfahrer grün einfärben */
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] {
        background-color: #2e7d32 !important; /* Dunkelgrün */
        color: white !important;
    }
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] span {
        color: white !important;
    }
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] svg {
        fill: white !important;
    }
    </style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "KELLERHOLZ-CMYK.png")
STATE_FILE = os.path.join(BASE_DIR, "app_state.json")

# ==========================================
# KONSTANTEN
# ==========================================
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
WEEKDAYS_WITH_EMPTY = [""] + WEEKDAYS
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
EXT_COL_ORDER = ["Produkt / Artikel", "Kunde", "Frachtführer / Spedition", "SOLL (Fuhren)", "IST (Erfüllt)", "Einsatztag", "Bemerkung / Uhrzeit"]

# ==========================================
# PERSISTENZ-FUNKTIONEN
# ==========================================
def load_persistent_data():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_persistent_data():
    data = {
        "shift_hours": st.session_state.get("shift_hours", 9.0),
        "truck_cap": st.session_state.get("truck_cap", 103),
        "selected_day": st.session_state.get("selected_day", "Montag"),
        "blocked_trucks": {day: st.session_state.get(f"block_truck_{day}", []) for day in WEEKDAYS},
        "extra_drivers": {day: st.session_state.get(f"extra_driver_{day}", []) for day in WEEKDAYS},
        "blocked_customers": {day: st.session_state.get(f"block_cust_{day}", []) for day in WEEKDAYS},
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
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        hrs = int(parts[0])
        mins = int(parts[1]) if len(parts) > 1 else 0
        return round(hrs + (mins / 60.0), 2)
    except Exception:
        return 2.0

def format_hours(hours_float):
    hrs = int(hours_float)
    mins = int(round((hours_float - hrs) * 60))
    if mins == 60:
        hrs += 1
        mins = 0
    return f"{hrs:02d}:{mins:02d}"

# ==========================================
# ECHTER STATE-SYNC BEI JEDEM RERUN
# ==========================================
saved_data = load_persistent_data()

# Basic Settings
st.session_state["shift_hours"] = float(saved_data.get("shift_hours", 9.0))
st.session_state["truck_cap"] = int(saved_data.get("truck_cap", 103))
st.session_state["selected_day"] = saved_data.get("selected_day", "Montag")

# Touren & Fremdfuhren
st.session_state["booked_trips"] = saved_data.get("booked_trips", [])
st.session_state["ext_booked_trips"] = saved_data.get("ext_booked_trips", [])

# Bunker-Füllstände
b_saved = saved_data.get("bunkers", {})
st.session_state["bunker_sm"] = b_saved.get("bunker_sm", 50)
st.session_state["bunker_hs"] = b_saved.get("bunker_hs", 50)
st.session_state["bunker_ri"] = b_saved.get("bunker_ri", 50)
st.session_state["bunker_kp"] = b_saved.get("bunker_kp", 50)

# Ausfälle, Aushilfen & Kundensperren
saved_blocked_trucks = saved_data.get("blocked_trucks", {})
saved_extra_drivers = saved_data.get("extra_drivers", {})
saved_blocked_custs = saved_data.get("blocked_customers", {})

for day in WEEKDAYS:
    st.session_state[f"block_truck_{day}"] = saved_blocked_trucks.get(day, [])
    st.session_state[f"extra_driver_{day}"] = saved_extra_drivers.get(day, [])
    st.session_state[f"block_cust_{day}"] = saved_blocked_custs.get(day, [])

# Stammdaten
if "customer_db" in saved_data and saved_data["customer_db"]:
    st.session_state["customer_db"] = pd.DataFrame(saved_data["customer_db"])
elif "customer_db" not in st.session_state:
    st.session_state["customer_db"] = pd.DataFrame([
        {"Kunde": "SIAT Urmatt", "Umlaufzeit (hh:mm)": "03:55", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "JRS Ettenheim", "Umlaufzeit (hh:mm)": "03:15", "1 - Sägemehl": True, "2 - Hackschnitzel": False, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Trendel", "Umlaufzeit (hh:mm)": "02:38", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Rheinspan Germersheim", "Umlaufzeit (hh:mm)": "04:03", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Roquette Beinheim", "Umlaufzeit (hh:mm)": "02:50", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Baden-Airpark", "Umlaufzeit (hh:mm)": "02:15", "1 - Sägemehl": False, "2 - Hackschnitzel": False, "3 - Rinde": True, "4 - Kappholz": False},
        {"Kunde": "OCO H. Weber", "Umlaufzeit (hh:mm)": "02:23", "1 - Sägemehl": True, "2 - Hackschnitzel": False, "3 - Rinde": True, "4 - Kappholz": True},
        {"Kunde": "OCO Energy", "Umlaufzeit (hh:mm)": "02:23", "1 - Sägemehl": False, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Zollikofer Auenheim", "Umlaufzeit (hh:mm)": "01:50", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
        {"Kunde": "Vogel Weitenung", "Umlaufzeit (hh:mm)": "01:45", "1 - Sägemehl": False, "2 - Hackschnitzel": False, "3 - Rinde": True, "4 - Kappholz": True},
        {"Kunde": "Treyer Bad Peterstal", "Umlaufzeit (hh:mm)": "02:57", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
    ])

# Fremdspeditionen
if "ext_terminal_db" in saved_data and saved_data["ext_terminal_db"]:
    df_ext = pd.DataFrame(saved_data["ext_terminal_db"])
    st.session_state["ext_terminal_db"] = df_ext.reindex(columns=[c for c in EXT_COL_ORDER if c in df_ext.columns])
elif "ext_terminal_db" not in st.session_state:
    st.session_state["ext_terminal_db"] = pd.DataFrame([
        {"Produkt / Artikel": "1 - Sägemehl", "Kunde": "SIAT Urmatt", "Frachtführer / Spedition": "Spedition Müller", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "", "Bemerkung / Uhrzeit": "Avisierung vorab"},
        {"Produkt / Artikel": "2 - Hackschnitzel", "Kunde": "Rheinspan Germersheim", "Frachtführer / Spedition": "TransHolz GmbH", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "Dienstag", "Bemerkung / Uhrzeit": "08:00 Uhr Zeitfenster"}
    ], columns=EXT_COL_ORDER)

# Kontingente
if "quotas_state" in saved_data and saved_data["quotas_state"]:
    st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in saved_data["quotas_state"].items()}
elif "quotas_state" not in st.session_state:
    st.session_state["quotas_state"] = {
        ("Rheinspan Germersheim", "2 - Hackschnitzel"): {"soll": 0, "rest": "Zwingend Dienstag 07:00 Uhr", "prio": 4},
        ("Rheinspan Germersheim", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 4},
        ("JRS Ettenheim", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 3},
        ("Baden-Airpark", "3 - Rinde"): {"soll": 0, "rest": "Nur Nachmittags ab 13:00 Uhr", "prio": 2},
        ("SIAT Urmatt", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 3},
    }

# ==========================================
# RESET-LOGIK (CALLBACK)
# ==========================================
def perform_global_reset():
    clean_quotas = {}
    for k, v in st.session_state.quotas_state.items():
        clean_quotas[f"{k[0]}|||{k[1]}"] = {"soll": 0, "rest": v.get("rest", "Keine"), "prio": v.get("prio", 3)}
        
    clean_ext_terminal = st.session_state.ext_terminal_db.copy()
    clean_ext_terminal["SOLL (Fuhren)"] = 0
    clean_ext_terminal["IST (Erfüllt)"] = 0
    clean_ext_terminal = clean_ext_terminal.reindex(columns=EXT_COL_ORDER)
    
    reset_data = {
        "shift_hours": 9.0,
        "truck_cap": 103,
        "selected_day": "Montag",
        "blocked_trucks": {day: [] for day in WEEKDAYS},
        "extra_drivers": {day: [] for day in WEEKDAYS},
        "blocked_customers": {day: [] for day in WEEKDAYS},
        "bunkers": {
            "bunker_sm": 50,
            "bunker_hs": 50,
            "bunker_ri": 50,
            "bunker_kp": 50
        },
        "customer_db": st.session_state.customer_db.to_dict(orient="records"),
        "ext_terminal_db": clean_ext_terminal.to_dict(orient="records"),
        "quotas_state": clean_quotas,
        "booked_trips": [],
        "ext_booked_trips": []
    }
    
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(reset_data, f, ensure_ascii=False, indent=4)

    st.session_state["shift_hours"] = 9.0
    st.session_state["truck_cap"] = 103
    st.session_state["selected_day"] = "Montag"
    st.session_state["bunker_sm"] = 50
    st.session_state["bunker_hs"] = 50
    st.session_state["bunker_ri"] = 50
    st.session_state["bunker_kp"] = 50
    st.session_state["booked_trips"] = []
    st.session_state["ext_booked_trips"] = []
    st.session_state["ext_terminal_db"] = clean_ext_terminal
    st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in clean_quotas.items()}

    for day in WEEKDAYS:
        st.session_state[f"block_truck_{day}"] = []
        st.session_state[f"extra_driver_{day}"] = []
        st.session_state[f"block_cust_{day}"] = []

# ==========================================
# HEADER
# ==========================================
col_head, col_logo = st.columns([4, 1])
with col_head:
    st.title("🪵 Restholz-Tourenplaner Sägewerk")
    st.markdown("Automatisierte Schichtplanung mit **voller Zustandsspeicherung**")

with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.caption("📷 *[KELLERHOLZ-CMYK.png nicht gefunden]*")

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.header("⚙️ Fahrzeuge & Schichtzeit")

shift_hours = st.sidebar.number_input(
    "Max. Schichtzeit (Std./Tag)", 
    step=0.5, 
    key="shift_hours", 
    on_change=save_persistent_data
)

truck_cap = st.sidebar.number_input(
    "Kapazität Sattelzug (m³)", 
    step=1, 
    key="truck_cap", 
    on_change=save_persistent_data
)

selected_day = st.sidebar.select_slider(
    "Aktueller Planungstag / Ansicht", 
    options=WEEKDAYS, 
    key="selected_day", 
    on_change=save_persistent_data
)
selected_day_idx = WEEKDAYS.index(selected_day)

st.sidebar.divider()
st.sidebar.subheader("🚛 Fahrzeugverfügbarkeit")

blocked_trucks = {}
extra_drivers = {}

for day in WEEKDAYS:
    st.sidebar.markdown(f"**{day}:**")
    blocked_trucks[day] = st.sidebar.multiselect(
        f"❌ Ausfall am {day}:",
        options=TRUCK_PRIO,
        key=f"block_truck_{day}",
        on_change=save_persistent_data
    )
    
    avail_for_extra = [t for t in TRUCK_PRIO if t not in st.session_state.get(f"block_truck_{day}", [])]
    extra_drivers[day] = st.sidebar.multiselect(
        f"🟢 Aushilfsfahrer (17–21 Uhr) am {day}:",
        options=avail_for_extra,
        key=f"extra_driver_{day}",
        on_change=save_persistent_data
    )

st.sidebar.divider()
st.sidebar.button("💥 Alles zurücksetzen (Reset)", use_container_width=True, type="secondary", on_click=perform_global_reset)

col_title, col_btn = st.columns([3, 1])
with col_btn:
    if st.button("🔄 Planung neu berechnen", use_container_width=True, type="primary"):
        save_persistent_data()
        st.rerun()

# ==========================================
# BEREICH 1: BUNKER-FÜLLSTÄNDE
# ==========================================
with st.expander("1. 🏭 Aktuelle Bunker-Füllstände (%)", expanded=True):
    st.caption("Füllstände fließen direkt in die Dispo-Punktevergabe ein.")
    pct_options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bunker_sm = st.select_slider("1 - Sägemehl", options=pct_options, key="bunker_sm", on_change=save_persistent_data)
        st.progress(bunker_sm / 100)
        if bunker_sm <= 10: st.warning("⛔ GESPERRT")
        elif bunker_sm >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col2:
        bunker_hs = st.select_slider("2 - Hackschnitzel", options=pct_options, key="bunker_hs", on_change=save_persistent_data)
        st.progress(bunker_hs / 100)
        if bunker_hs <= 10: st.warning("⛔ GESPERRT")
        elif bunker_hs >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col3:
        bunker_ri = st.select_slider("3 - Rinde", options=pct_options, key="bunker_ri", on_change=save_persistent_data)
        st.progress(bunker_ri / 100)
        if bunker_ri <= 10: st.warning("⛔ GESPERRT")
        elif bunker_ri >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col4:
        bunker_kp = st.select_slider("4 - Kappholz", options=pct_options, key="bunker_kp", on_change=save_persistent_data)
        st.progress(bunker_kp / 100)
        if bunker_kp <= 10: st.warning("⛔ GESPERRT")
        elif bunker_kp >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")

# ==========================================
# BEREICH 2: KUNDEN-STAMMDATEN
# ==========================================
with st.expander("2. 👥 Kundendatenbank (Stammdaten)", expanded=False):
    edited_cust_db = st.data_editor(
        st.session_state.customer_db,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Kunde": st.column_config.TextColumn("Kundenname", required=True),
            "Umlaufzeit (hh:mm)": st.column_config.TextColumn("Umlaufzeit (hh:mm)", default="02:00", required=True),
            "1 - Sägemehl": st.column_config.CheckboxColumn("1 - Sägemehl", default=False),
            "2 - Hackschnitzel": st.column_config.CheckboxColumn("2 - Hackschnitzel", default=False),
            "3 - Rinde": st.column_config.CheckboxColumn("3 - Rinde", default=False),
            "4 - Kappholz": st.column_config.CheckboxColumn("4 - Kappholz", default=False),
        },
        hide_index=True,
        key="customer_editor"
    )
    if not edited_cust_db.equals(st.session_state.customer_db):
        st.session_state.customer_db = edited_cust_db
        save_persistent_data()

edited_cust_db = st.session_state.customer_db

# ==========================================
# BEREICH 3: KONTINGENTPLANUNG & SPERREN
# ==========================================
with st.expander("3. 📋 Wochen-Kontingente Interner Fuhrpark", expanded=True):
    booked_counts_by_cust_prod = {}
    for b in st.session_state.booked_trips:
        key = (b.get("Kunde"), b.get("Produkt"))
        booked_counts_by_cust_prod[key] = booked_counts_by_cust_prod.get(key, 0) + 1

    initial_quota_rows = []
    for p_name in PRODUCT_LIST:
        for _, c_row in edited_cust_db.iterrows():
            c_name = str(c_row["Kunde"]).strip()
            if not c_name: continue
            
            t_str = str(c_row.get("Umlaufzeit (hh:mm)", "02:00"))
            c_dur = parse_time_str(t_str)
            
            if c_row.get(p_name, False):
                key = (c_name, p_name)
                prev = st.session_state.quotas_state.get(key, {"soll": 0, "rest": "Keine", "prio": 3})
                current_prio = min(5, max(1, prev.get("prio", 3)))
                ist = booked_counts_by_cust_prod.get(key, 0)
                
                initial_quota_rows.append({
                    "Produkt / Artikel": p_name,
                    "Kunde": f"{c_name} ({t_str})",
                    "SOLL (Geplante Fuhren)": prev["soll"],
                    "IST (Gebucht)": ist,
                    "Fix-Termine / Restriktionen": prev["rest"],
                    "Priorität (1-5)": current_prio,
                    "_Produkt_Raw": p_name,
                    "_Kunde_Raw": c_name,
                    "_Dauer_h": c_dur
                })

    df_quotas_init = pd.DataFrame(initial_quota_rows)

    edited_quotas = st.data_editor(
        df_quotas_init,
        use_container_width=True,
        num_rows="fixed",
        disabled=["Produkt / Artikel", "Kunde", "IST (Gebucht)", "_Produkt_Raw", "_Kunde_Raw", "_Dauer_h"],
        column_config={
            "_Produkt_Raw": None,
            "_Kunde_Raw": None,
            "_Dauer_h": None,
            "Produkt / Artikel": st.column_config.TextColumn("Produkt / Artikel", width="medium"),
            "Kunde": st.column_config.TextColumn("Kunde (Umlaufzeit hh:mm)", width="medium"),
            "SOLL (Geplante Fuhren)": st.column_config.NumberColumn("SOLL (Geplanned)", min_value=0, max_value=50, step=1),
            "IST (Gebucht)": st.column_config.NumberColumn("IST (Gebucht)", min_value=0, max_value=50),
            "Fix-Termine / Restriktionen": st.column_config.TextColumn("Fix-Termine / Restriktionen", width="large"),
            "Priorität (1-5)": st.column_config.NumberColumn("Priorität (1-5)", min_value=1, max_value=5, step=1)
        },
        hide_index=True,
        key="quotas_editor"
    )

    quotas_changed = False
    for _, row in edited_quotas.iterrows():
        k = (row["_Kunde_Raw"], row["_Produkt_Raw"])
        new_val = {
            "soll": int(row["SOLL (Geplante Fuhren)"]),
            "rest": str(row["Fix-Termine / Restriktionen"]),
            "prio": int(row["Priorität (1-5)"])
        }
        if st.session_state.quotas_state.get(k) != new_val:
            st.session_state.quotas_state[k] = new_val
            quotas_changed = True

    if quotas_changed:
        save_persistent_data()

    # KUNDENSPERREN
    st.markdown("#### 🚫 Kundensperren / Annahmestopp")
    all_customer_names = [str(r["Kunde"]).strip() for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()]
    
    blocked_customers_by_day = {day: set() for day in WEEKDAYS}
    
    selected_blocked_custs = st.multiselect(
        f"Kunden mit Annahmestopp ab {selected_day} (gilt automatisch für den Rest der Woche):",
        options=all_customer_names,
        key=f"block_cust_{selected_day}",
        on_change=save_persistent_data
    )

    for future_day_idx in range(selected_day_idx, len(WEEKDAYS)):
        future_day = WEEKDAYS[future_day_idx]
        for c_name in selected_blocked_custs:
            blocked_customers_by_day[future_day].add(c_name)

# ==========================================
# BEREICH 4: FREMDSPEDITIONEN-TERMINAL
# ==========================================
with st.expander("4. 🚛 Fremdspeditionen-Terminal (Manuelle Liste)", expanded=True):
    ext_df_display = st.session_state.ext_terminal_db.reindex(columns=EXT_COL_ORDER)

    edited_ext_db = st.data_editor(
        ext_df_display,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Produkt / Artikel": st.column_config.SelectboxColumn("Produkt / Artikel", options=PRODUCT_LIST, default="1 - Sägemehl"),
            "Kunde": st.column_config.TextColumn("Kunde (Freitext)", default="", required=True),
            "Frachtführer / Spedition": st.column_config.TextColumn("Frachtführer / Spedition", default="", required=True),
            "SOLL (Fuhren)": st.column_config.NumberColumn("SOLL (Fuhren)", min_value=0, max_value=100, step=1, default=0),
            "IST (Erfüllt)": st.column_config.NumberColumn("IST (Erfüllt)", min_value=0, max_value=100, step=1, default=0),
            "Einsatztag": st.column_config.SelectboxColumn("Einsatztag", options=WEEKDAYS_WITH_EMPTY, default=""),
            "Bemerkung / Uhrzeit": st.column_config.TextColumn("Bemerkung / Uhrzeit", default="")
        },
        hide_index=True,
        key="ext_terminal_editor_manual"
    )

    if not edited_ext_db.equals(st.session_state.ext_terminal_db):
        st.session_state.ext_terminal_db = edited_ext_db
        save_persistent_data()

    if not edited_ext_db.empty:
        col_sel, col_btn_ext = st.columns([3, 1])
        ext_options = []
        for idx, row in edited_ext_db.iterrows():
            prod = str(row.get("Produkt / Artikel", ""))
            cust = str(row.get("Kunde", "")).strip() or "Unbekannter Kunde"
            sped = str(row.get("Frachtführer / Spedition", "")).strip() or "Unbekannte Spedition"
            soll = row.get("SOLL (Fuhren)", 0)
            ist = row.get("IST (Erfüllt)", 0)
            ext_options.append(f"Zeile {idx+1}: {prod} ➔ {cust} ({sped}) | IST: {ist}/{soll}")
        
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
                "Einsatztag": booked_row.get("Einsatztag") or "Keiner",
                "Bemerkung": booked_row.get("Bemerkung / Uhrzeit")
            })
            
            save_persistent_data()
            st.success("Fremdfuhre verbucht!")
            st.rerun()

# ==========================================
# BEREICH 5: MANUELLE VERBUCHUNG
# ==========================================
with st.expander("5. 🛠️ Manuelle Verbuchung (Eigenfuhrpark)", expanded=False):
    cust_duration_map = {str(r["Kunde"]).strip(): parse_time_str(r["Umlaufzeit (hh:mm)"]) for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()}
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_kunde_raw = m_col1.selectbox("Kunde", list(cust_duration_map.keys()) if cust_duration_map else ["-"], key="m_kunde_sel")
    m_prod = m_col2.selectbox("Produkt", PRODUCT_LIST, key="m_prod_sel")
    m_day = m_col3.selectbox("Tag", WEEKDAYS, index=WEEKDAYS.index(selected_day), key="m_day_sel")
    m_truck = m_col4.selectbox("Fahrzeug", TRUCK_PRIO, key="m_truck_sel")
    m_dauer = cust_duration_map.get(m_kunde_raw, 2.0)
    
    if m_col5.button("⚡ Manuell Verbuchen", use_container_width=True, type="primary") and m_kunde_raw != "-":
        m_id = f"manual_{m_day}_{m_truck}_{m_kunde_raw}_{m_prod}_{len(st.session_state.booked_trips)}"
        st.session_state.booked_trips.append({
            "id": m_id,
            "Tag": m_day,
            "Fahrzeug": m_truck,
            "Zeitfenster": "Manuell eingeplant",
            "Kunde": m_kunde_raw,
            "Produkt": m_prod,
            "Menge_m3": truck_cap,
            "dauer_h": m_dauer,
            "is_manual": True
        })
        save_persistent_data()
        st.success("Tour manuell verbucht!")
        st.rerun()

st.divider()

# ==========================================
# BEREICH 6: AUTOMATISCHE PLANUNGS-ENGINE
# ==========================================
bunker_levels = {
    "1 - Sägemehl": st.session_state.bunker_sm,
    "2 - Hackschnitzel": st.session_state.bunker_hs,
    "3 - Rinde": st.session_state.bunker_ri,
    "4 - Kappholz": st.session_state.bunker_kp,
}

# Quoten-Soll & -Ist abgleichen
remaining_quotas = {}
for k, v in st.session_state.quotas_state.items():
    cust_name, prod_name = k
    already_booked = sum(1 for b in st.session_state.booked_trips if b.get("Kunde") == cust_name and b.get("Produkt") == prod_name)
    soll = v.get("soll", 0)
    remaining_quotas[k] = max(0, soll - already_booked)

schedule_by_day = {day: {t: [] for t in TRUCK_PRIO} for day in WEEKDAYS}
truck_used_hours = {day: {t: 0.0 for t in TRUCK_PRIO} for day in WEEKDAYS}

# Manuell gebuchte Touren im Fahrplan verankern
for b in st.session_state.booked_trips:
    b_day = b.get("Tag")
    b_truck = b.get("Fahrzeug")
    if b_day in WEEKDAYS and b_truck in TRUCK_PRIO:
        schedule_by_day[b_day][b_truck].append(b)
        truck_used_hours[b_day][b_truck] += b.get("dauer_h", 2.0)

# Automatische Verteilung für offene Kontingente
for day in WEEKDAYS:
    active_trucks = [t for t in TRUCK_PRIO if t not in blocked_trucks.get(day, [])]
    extra_d_list = extra_drivers.get(day, [])
    
    # Verfügbare Restzeit pro LKW berechnen
    truck_max_hours = {}
    for t in active_trucks:
        max_h = shift_hours + (4.0 if t in extra_d_list else 0.0)
        truck_max_hours[t] = max_h

    # Offene Aufträge nach Dringlichkeit sortieren (Bunker-Status + Priorität)
    candidates = []
    for (c_name, p_name), rem_qty in remaining_quotas.items():
        if rem_qty <= 0:
            continue
        if c_name in blocked_customers_by_day.get(day, set()):
            continue
        if bunker_levels.get(p_name, 50) <= 10:
            continue
            
        dur = cust_duration_map.get(c_name, 2.0)
        q_info = st.session_state.quotas_state.get((c_name, p_name), {})
        prio = q_info.get("prio", 3)
        b_level = bunker_levels.get(p_name, 50)
        
        # Prio-Score berechnen
        score = prio * 10
        if b_level >= 80: score += 30
        elif b_level >= 60: score += 15
        
        candidates.append({
            "Kunde": c_name,
            "Produkt": p_name,
            "dauer_h": dur,
            "score": score,
            "rest_req": q_info.get("rest", "Keine")
        })
        
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Touren auf LKWs verteilen
    for cand in candidates:
        c_key = (cand["Kunde"], cand["Produkt"])
        while remaining_quotas[c_key] > 0:
            assigned = False
            for t in active_trucks:
                current_h = truck_used_hours[day][t]
                max_h = truck_max_hours[t]
                if current_h + cand["dauer_h"] <= max_h + 0.1: # 6 Min Toleranz
                    start_t = 6.0 + current_h
                    end_t = start_t + cand["dauer_h"]
                    
                    time_slot_str = f"{format_hours(start_t)} - {format_hours(end_t)} Uhr"
                    
                    schedule_by_day[day][t].append({
                        "id": f"auto_{day}_{t}_{len(schedule_by_day[day][t])}",
                        "Tag": day,
                        "Fahrzeug": t,
                        "Zeitfenster": time_slot_str,
                        "Kunde": cand["Kunde"],
                        "Produkt": cand["Produkt"],
                        "Menge_m3": truck_cap,
                        "dauer_h": cand["dauer_h"],
                        "is_manual": False,
                        "Bemerkung": cand["rest_req"]
                    })
                    
                    truck_used_hours[day][t] += cand["dauer_h"]
                    remaining_quotas[c_key] -= 1
                    assigned = True
                    break
            if not assigned:
                break # Wenn an diesem Tag kein LKW mehr frei ist, abbrechen und nächsten Tag probieren

# ==========================================
# BEREICH 7: WOCHENPLAN-VISUALISIERUNG
# ==========================================
st.header("📅 Wochen- & Tages-Fahrpläne")

tab_tag, tab_woche = st.tabs(["📌 Tagesansicht (Detail)", "🗓️ Wochenübersicht (Gesamter Fuhrpark)"])

with tab_tag:
    st.subheader(f"Detailplan für {selected_day}")
    
    cols_truck = st.columns(len(TRUCK_PRIO))
    for idx, t in enumerate(TRUCK_PRIO):
        with cols_truck[idx]:
            is_blocked = t in blocked_trucks.get(selected_day, [])
            is_extra = t in extra_drivers.get(selected_day, [])
            
            if is_blocked:
                st.error(f"🚛 **{t}**\n\n❌ **FAHRZEUGAUSFALL**")
            else:
                extra_badge = " 🟢 (Aushilfe)" if is_extra else ""
                used_h = truck_used_hours[selected_day][t]
                max_h = shift_hours + (4.0 if is_extra else 0.0)
                
                st.success(f"🚛 **{t}**{extra_badge}\n\n⏱️ **{format_hours(used_h)} / {format_hours(max_h)} Std.**")
                
                trips = schedule_by_day[selected_day][t]
                if not trips:
                    st.info("Keine Touren eingeplant.")
                else:
                    for trip in trips:
                        is_man = trip.get("is_manual", False)
                        badge = "🛠️ [Manuell]" if is_man else "🤖 [Auto]"
                        
                        st.markdown(f"""
                        <div style="border:1px solid #ddd; padding:8px; border-radius:5px; margin-bottom:8px; background-color:#f9f9f9;">
                            <small>{badge} {trip.get('Zeitfenster', '')}</small><br>
                            <strong>{trip['Kunde']}</strong><br>
                            <span style="color:#666;">📦 {trip['Produkt']} ({trip['Menge_m3']} m³)</span>
                        </div>
                        """, unsafe_allow_html=True)

with tab_woche:
    st.subheader("Wochenübersicht Auslastung & Tourenanzahl")
    
    wochen_summary = []
    for day in WEEKDAYS:
        row_data = {"Tag": day}
        total_day_trips = 0
        total_day_hours = 0.0
        
        for t in TRUCK_PRIO:
            t_trips = schedule_by_day[day][t]
            t_hours = truck_used_hours[day][t]
            row_data[f"{t} (Fuhren)"] = len(t_trips)
            row_data[f"{t} (Std.)"] = f"{format_hours(t_hours)}"
            total_day_trips += len(t_trips)
            total_day_hours += t_hours
            
        row_data["Gesamt Fuhren"] = total_day_trips
        row_data["Gesamt Stunden"] = f"{format_hours(total_day_hours)}"
        wochen_summary.append(row_data)
        
    df_woche = pd.DataFrame(wochen_summary)
    st.dataframe(df_woche, use_container_width=True, hide_index=True)

# ==========================================
# BEREICH 8: HISTORIE & GEBUCHTE TOUREN
# ==========================================
with st.expander("📝 Verbuchte Touren verwalten & Stornieren", expanded=False):
    st.caption("Hier siehst du alle bereits fest verbuchten Touren des Eigenfuhrparks.")
    if st.session_state.booked_trips:
        df_booked = pd.DataFrame(st.session_state.booked_trips)
        cols_to_show = [c for c in ["id", "Tag", "Fahrzeug", "Kunde", "Produkt", "Menge_m3", "dauer_h", "Zeitfenster"] if c in df_booked.columns]
        st.dataframe(df_booked[cols_to_show], use_container_width=True, hide_index=True)
        
        del_col1, del_col2 = st.columns([3, 1])
        trip_to_del_id = del_col1.selectbox("Tour zum Stornieren auswählen:", options=[b["id"] for b in st.session_state.booked_trips], key="del_trip_select")
        if del_col2.button("❌ Tour Stornieren / Löschen", use_container_width=True):
            st.session_state.booked_trips = [b for b in st.session_state.booked_trips if b["id"] != trip_to_del_id]
            save_persistent_data()
            st.success("Tour entfernt!")
            st.rerun()
    else:
        st.info("Bisher wurden keine Touren manuell fest verbucht.")

# ==========================================
# BEREICH 9: KPI & AUSWERTUNG
# ==========================================
st.divider()
st.subheader("📊 Wochen-Kennzahlen & Auswertung")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

total_eigen_trips = sum(len(schedule_by_day[d][t]) for d in WEEKDAYS for t in TRUCK_PRIO)
total_volume_m3 = total_eigen_trips * truck_cap
total_ext_trips = sum(r.get("IST (Erfüllt)", 0) for _, r in st.session_state.ext_terminal_db.iterrows()) if not st.session_state.ext_terminal_db.empty else 0

kpi1.metric("Transportiertes Volumen (Eigenfuhrpark)", f"{total_volume_m3:,} m³".replace(",", "."))
kpi2.metric("Geplante Eigen-Fuhren", f"{total_eigen_trips} Fuhren")
kpi3.metric("Erfüllte Fremdfuhren", f"{total_ext_trips} Fuhren")

soll_total = sum(v.get("soll", 0) for v in st.session_state.quotas_state.values())
fulfillment = round((total_eigen_trips / soll_total * 100), 1) if soll_total > 0 else 100.0
kpi4.metric("Soll-Erfüllungsgrad Fuhrpark", f"{fulfillment}%")
