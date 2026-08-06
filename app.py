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

# 1. AUTO-REFRESH AKTIVIEREN (alle 2 Sekunden)
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
# CONSTANTS
# ==========================================
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
WEEKDAYS_WITH_EMPTY = [""] + WEEKDAYS
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
EXT_COL_ORDER = ["Produkt / Artikel", "Kunde", "Frachtführer / Spedition", "SOLL (Fuhren)", "IST (Erfüllt)", "Einsatztag", "Bemerkung / Uhrzeit"]

# ==========================================
# PERSISTENZ (SPEICHERN & LADEN)
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

# ✅ BEI JEDEM REFRESH DIE DATEN NEU EINLESEN UND DEM SESSION STATE ÜBERGEBEN
saved_data = load_persistent_data()

st.session_state.booked_trips = saved_data.get("booked_trips", [])
st.session_state.ext_booked_trips = saved_data.get("ext_booked_trips", [])

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        hrs = int(parts[0])
        mins = int(parts[1]) if len(parts) > 1 else 0
        return round(hrs + (mins / 60.0), 2)
    except Exception:
        return 2.0

# Stammdaten bei jedem Durchlauf synchronisieren
if "customer_db" in saved_data and saved_data["customer_db"]:
    st.session_state.customer_db = pd.DataFrame(saved_data["customer_db"])
elif "customer_db" not in st.session_state:
    st.session_state.customer_db = pd.DataFrame([
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

# Fremdspeditionen bei jedem Durchlauf synchronisieren
if "ext_terminal_db" in saved_data and saved_data["ext_terminal_db"]:
    df_ext = pd.DataFrame(saved_data["ext_terminal_db"])
    st.session_state.ext_terminal_db = df_ext.reindex(columns=[c for c in EXT_COL_ORDER if c in df_ext.columns])
elif "ext_terminal_db" not in st.session_state:
    st.session_state.ext_terminal_db = pd.DataFrame([
        {"Produkt / Artikel": "1 - Sägemehl", "Kunde": "SIAT Urmatt", "Frachtführer / Spedition": "Spedition Müller", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "", "Bemerkung / Uhrzeit": "Avisierung vorab"},
        {"Produkt / Artikel": "2 - Hackschnitzel", "Kunde": "Rheinspan Germersheim", "Frachtführer / Spedition": "TransHolz GmbH", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "Dienstag", "Bemerkung / Uhrzeit": "08:00 Uhr Zeitfenster"}
    ], columns=EXT_COL_ORDER)

# Kontingente bei jedem Durchlauf synchronisieren
if "quotas_state" in saved_data and saved_data["quotas_state"]:
    st.session_state.quotas_state = {tuple(k.split("|||")): v for k, v in saved_data["quotas_state"].items()}
elif "quotas_state" not in st.session_state:
    st.session_state.quotas_state = {
        ("Rheinspan Germersheim", "2 - Hackschnitzel"): {"soll": 0, "rest": "Zwingend Dienstag 07:00 Uhr", "prio": 4},
        ("Rheinspan Germersheim", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 4},
        ("JRS Ettenheim", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 3},
        ("Baden-Airpark", "3 - Rinde"): {"soll": 0, "rest": "Nur Nachmittags ab 13:00 Uhr", "prio": 2},
        ("SIAT Urmatt", "1 - Sägemehl"): {"soll": 0, "rest": "Keine", "prio": 3},
    }

# ==========================================
# RESET-LOGIK (ALS CALLBACK)
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

shift_hours = st.sidebar.number_input("Max. Schichtzeit (Std./Tag)", value=float(saved_data.get("shift_hours", 9.0)), step=0.5, key="shift_hours", on_change=save_persistent_data)
truck_cap = st.sidebar.number_input("Kapazität Sattelzug (m³)", value=int(saved_data.get("truck_cap", 103)), step=1, key="truck_cap", on_change=save_persistent_data)

selected_day = st.sidebar.select_slider("Aktueller Planungstag / Ansicht", options=WEEKDAYS, value=saved_data.get("selected_day", "Montag"), key="selected_day", on_change=save_persistent_data)
selected_day_idx = WEEKDAYS.index(selected_day)

st.sidebar.divider()
st.sidebar.subheader("🚛 Fahrzeugverfügbarkeit")

saved_blocked_trucks = saved_data.get("blocked_trucks", {})
saved_extra_drivers = saved_data.get("extra_drivers", {})

blocked_trucks = {}
extra_drivers = {}

for day in WEEKDAYS:
    st.sidebar.markdown(f"**{day}:**")
    blocked_trucks[day] = st.sidebar.multiselect(
        f"❌ Ausfall am {day}:",
        options=TRUCK_PRIO,
        default=saved_blocked_trucks.get(day, []),
        key=f"block_truck_{day}",
        on_change=save_persistent_data
    )
    
    avail_for_extra = [t for t in TRUCK_PRIO if t not in blocked_trucks[day]]
    extra_drivers[day] = st.sidebar.multiselect(
        f"🟢 Aushilfsfahrer (17–21 Uhr) am {day}:",
        options=avail_for_extra,
        default=[t for t in saved_extra_drivers.get(day, []) if t in avail_for_extra],
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
    saved_bunkers = saved_data.get("bunkers", {})
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bunker_sm = st.select_slider("1 - Sägemehl", options=pct_options, value=saved_bunkers.get("bunker_sm", 50), key="bunker_sm", on_change=save_persistent_data)
        st.progress(bunker_sm / 100)
        if bunker_sm <= 10: st.warning("⛔ GESPERRT")
        elif bunker_sm >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col2:
        bunker_hs = st.select_slider("2 - Hackschnitzel", options=pct_options, value=saved_bunkers.get("bunker_hs", 50), key="bunker_hs", on_change=save_persistent_data)
        st.progress(bunker_hs / 100)
        if bunker_hs <= 10: st.warning("⛔ GESPERRT")
        elif bunker_hs >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col3:
        bunker_ri = st.select_slider("3 - Rinde", options=pct_options, value=saved_bunkers.get("bunker_ri", 50), key="bunker_ri", on_change=save_persistent_data)
        st.progress(bunker_ri / 100)
        if bunker_ri <= 10: st.warning("⛔ GESPERRT")
        elif bunker_ri >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col4:
        bunker_kp = st.select_slider("4 - Kappholz", options=pct_options, value=saved_bunkers.get("bunker_kp", 50), key="bunker_kp", on_change=save_persistent_data)
        st.progress(bunker_kp / 100)
        if bunker_kp <= 10: st.warning("⛔ GESPERRT")
        elif bunker_kp >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")

    bunker_states = {
        "1 - Sägemehl": bunker_sm,
        "2 - Hackschnitzel": bunker_hs,
        "3 - Rinde": bunker_ri,
        "4 - Kappholz": bunker_kp
    }

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
            "SOLL (Geplante Fuhren)": st.column_config.NumberColumn("SOLL (Geplant)", min_value=0, max_value=50, step=1),
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
    saved_blocked_custs = saved_data.get("blocked_customers", {})
    
    blocked_customers_by_day = {day: set() for day in WEEKDAYS}
    
    selected_blocked_custs = st.multiselect(
        f"Kunden mit Annahmestopp ab {selected_day} (gilt automatisch für den Rest der Woche):",
        options=all_customer_names,
        default=saved_blocked_custs.get(selected_day, []),
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

    total_ext_soll_trips = int(st.session_state.ext_terminal_db["SOLL (Fuhren)"].sum()) if not st.session_state.ext_terminal_db.empty else 0

# ==========================================
# BEREICH 5: MANUELLE VERBUCHUNG
# ==========================================
with st.expander("5. 🛠️ Manuelle Verbuchung (Eigenfuhrpark)", expanded=False):
    cust_duration_map = {str(r["Kunde"]).strip(): parse_time_str(r["Umlaufzeit (hh:mm)"]) for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()}
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_kunde_raw = m_col1.selectbox("Kunde", list(cust_duration_map.keys()) if cust_duration_map else ["-"])
    m_prod = m_col2.selectbox("Produkt", PRODUCT_LIST)
    m_day = m_col3.selectbox("Tag", WEEKDAYS, index=WEEKDAYS.index(selected_day))
    m_truck = m_col4.selectbox("Fahrzeug", TRUCK_PRIO)
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
