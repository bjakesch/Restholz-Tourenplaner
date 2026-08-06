import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# ==========================================
# PAGE CONFIG & PFADE
# ==========================================
st.set_page_config(page_title="Restholz-Tourenplaner Sägewerk", layout="wide", page_icon="🪵")

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
        "customer_db": st.session_state.customer_db.to_dict(orient="records"),
        "ext_terminal_db": st.session_state.ext_terminal_db.to_dict(orient="records"),
        "quotas_state": {f"{k[0]}|||{k[1]}": v for k, v in st.session_state.quotas_state.items()},
        "booked_trips": st.session_state.get("booked_trips", []),
        "ext_booked_trips": st.session_state.get("ext_booked_trips", [])
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

saved_data = load_persistent_data()

# ==========================================
# INITIALISIERUNG SESSION STATE
# ==========================================
if "booked_trips" not in st.session_state:
    st.session_state.booked_trips = saved_data.get("booked_trips", [])

if "ext_booked_trips" not in st.session_state:
    st.session_state.ext_booked_trips = saved_data.get("ext_booked_trips", [])

def parse_time_str(t_str):
    try:
        parts = str(t_str).strip().split(":")
        hrs = int(parts[0])
        mins = int(parts[1]) if len(parts) > 1 else 0
        return round(hrs + (mins / 60.0), 2)
    except Exception:
        return 2.0

# Stammdaten
if "customer_db" not in st.session_state:
    if "customer_db" in saved_data:
        st.session_state.customer_db = pd.DataFrame(saved_data["customer_db"])
    else:
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

# Fremdspeditionen
if "ext_terminal_db" not in st.session_state:
    if "ext_terminal_db" in saved_data:
        df_ext = pd.DataFrame(saved_data["ext_terminal_db"])
        st.session_state.ext_terminal_db = df_ext.reindex(columns=[c for c in EXT_COL_ORDER if c in df_ext.columns])
    else:
        st.session_state.ext_terminal_db = pd.DataFrame([
            {"Produkt / Artikel": "1 - Sägemehl", "Kunde": "SIAT Urmatt", "Frachtführer / Spedition": "Spedition Müller", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "", "Bemerkung / Uhrzeit": "Avisierung vorab"},
            {"Produkt / Artikel": "2 - Hackschnitzel", "Kunde": "Rheinspan Germersheim", "Frachtführer / Spedition": "TransHolz GmbH", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "Dienstag", "Bemerkung / Uhrzeit": "08:00 Uhr Zeitfenster"}
        ], columns=EXT_COL_ORDER)

# Kontingente
if "quotas_state" not in st.session_state:
    if "quotas_state" in saved_data:
        st.session_state.quotas_state = {tuple(k.split("|||")): v for k, v in saved_data["quotas_state"].items()}
    else:
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

shift_hours = st.sidebar.number_input("Max. Schichtzeit (Std./Tag)", value=float(st.session_state.get("shift_hours", saved_data.get("shift_hours", 9.0))), step=0.5, key="shift_hours", on_change=save_persistent_data)
truck_cap = st.sidebar.number_input("Kapazität Sattelzug (m³)", value=int(st.session_state.get("truck_cap", saved_data.get("truck_cap", 103))), step=1, key="truck_cap", on_change=save_persistent_data)

selected_day = st.sidebar.select_slider("Aktueller Planungstag / Ansicht", options=WEEKDAYS, value=st.session_state.get("selected_day", saved_data.get("selected_day", "Montag")), key="selected_day", on_change=save_persistent_data)
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
        bunker_sm = st.select_slider("1 - Sägemehl", options=pct_options, value=st.session_state.get("bunker_sm", saved_bunkers.get("bunker_sm", 50)), key="bunker_sm", on_change=save_persistent_data)
        st.progress(bunker_sm / 100)
        if bunker_sm <= 10: st.warning("⛔ GESPERRT")
        elif bunker_sm >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col2:
        bunker_hs = st.select_slider("2 - Hackschnitzel", options=pct_options, value=st.session_state.get("bunker_hs", saved_bunkers.get("bunker_hs", 50)), key="bunker_hs", on_change=save_persistent_data)
        st.progress(bunker_hs / 100)
        if bunker_hs <= 10: st.warning("⛔ GESPERRT")
        elif bunker_hs >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col3:
        bunker_ri = st.select_slider("3 - Rinde", options=pct_options, value=st.session_state.get("bunker_ri", saved_bunkers.get("bunker_ri", 50)), key="bunker_ri", on_change=save_persistent_data)
        st.progress(bunker_ri / 100)
        if bunker_ri <= 10: st.warning("⛔ GESPERRT")
        elif bunker_ri >= 80: st.error("🚨 HOCH")
        else: st.success("✅ Normal")
        
    with col4:
        bunker_kp = st.select_slider("4 - Kappholz", options=pct_options, value=st.session_state.get("bunker_kp", saved_bunkers.get("bunker_kp", 50)), key="bunker_kp", on_change=save_persistent_data)
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
    # Sicherstellen, dass die Spalten in der gewünschten Reihenfolge vorliegen
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

# ==========================================
# DISPOSITION & ALGORITHMUS
# ==========================================
def get_bunker_points(pct):
    if pct <= 10: return 0
    elif pct <= 30: return 1
    elif pct <= 50: return 2
    elif pct <= 70: return 3
    elif pct <= 90: return 5
    else: return 6

def get_short_route_bonus(duration_h, bunker_sm_pct, bunker_hs_pct):
    if bunker_sm_pct >= 60 and bunker_hs_pct >= 60:
        if duration_h < 2.0: return 2
        elif duration_h < 3.0: return 1
    return 0

def generate_all_requested_trips():
    trips = []
    blocked_by_bunker_trips = []
    
    for _, row in edited_quotas.iterrows():
        c_name = row["_Kunde_Raw"]
        c_dauer = float(row["_Dauer_h"])
        c_prio = int(row["Priorität (1-5)"])
        prod = row["_Produkt_Raw"]
        soll_anzahl = int(row["SOLL (Geplante Fuhren)"])
        
        pct_fill = bunker_states.get(prod, 50)
        
        if pct_fill <= 10:
            for _ in range(soll_anzahl):
                blocked_by_bunker_trips.append({
                    "kunde": c_name,
                    "produkt": prod,
                    "dauer_h": c_dauer,
                    "reason": f"Bunker {prod} gesperrt (<= 10%)"
                })
            continue
            
        b_pts = get_bunker_points(pct_fill)
        sr_bonus = get_short_route_bonus(c_dauer, bunker_states["1 - Sägemehl"], bunker_states["2 - Hackschnitzel"])
        base_score = b_pts + c_prio + sr_bonus
        
        for _ in range(soll_anzahl):
            trips.append({
                "kunde": c_name,
                "produkt": prod,
                "dauer_h": c_dauer,
                "cust_prio": c_prio,
                "bunker_pts": b_pts,
                "sr_bonus": sr_bonus,
                "base_score": base_score,
                "fill_pct": pct_fill
            })
    return trips, blocked_by_bunker_trips

all_requested_trips, bunker_blocked_trips = generate_all_requested_trips()
total_quota_trips = len(all_requested_trips) + len(bunker_blocked_trips)
total_booked_trips = len(st.session_state.booked_trips)

booked_counts = {}
for b in st.session_state.booked_trips:
    key = (b["Kunde"], b["Produkt"])
    booked_counts[key] = booked_counts.get(key, 0) + 1

remaining_trips_to_plan = []
temp_booked = booked_counts.copy()

for trip in all_requested_trips:
    key = (trip["kunde"], trip["produkt"])
    if temp_booked.get(key, 0) > 0:
        temp_booked[key] -= 1
    else:
        remaining_trips_to_plan.append(trip)

total_open_trips = len(remaining_trips_to_plan) + len(bunker_blocked_trips)

last_booked_product = None
if st.session_state.booked_trips:
    last_booked_product = st.session_state.booked_trips[-1].get("Produkt")

def optimize_schedule():
    schedule = {
        day: {
            truck: {
                "booked_tours": [],
                "planned_tours": [],
                "used_hours": 0.0,
                "max_hours": shift_hours + (4.0 if truck in extra_drivers[day] else 0.0),
                "has_extra_driver": truck in extra_drivers[day],
                "status": "ok"
            } for truck in TRUCK_PRIO
        } for day in WEEKDAYS
    }
    
    for b in st.session_state.booked_trips:
        b_day = b.get("Tag")
        b_truck = b.get("Fahrzeug")
        if b_day in schedule and b_truck in schedule[b_day]:
            schedule[b_day][b_truck]["booked_tours"].append({
                "kunde": b["Kunde"],
                "produkt": b["Produkt"],
                "dauer_h": b["dauer_h"],
                "total_score": 0,
                "is_manual": b.get("is_manual", False),
                "id": b.get("id")
            })
            schedule[b_day][b_truck]["used_hours"] += b["dauer_h"]

    planning_days = WEEKDAYS[selected_day_idx:]
    pool = remaining_trips_to_plan.copy()
    unassigned_trips = [f"{b['kunde']} ({b['produkt']}) ➔ {b['reason']}" for b in bunker_blocked_trips]

    for day in planning_days:
        avail_trucks = [t for t in TRUCK_PRIO if t not in blocked_trucks[day]]
        if not avail_trucks:
            continue
        
        while True:
            best_candidate_idx = -1
            best_total_score = -1
            best_assigned_truck = None
            best_trip_data = None
            
            for idx, trip in enumerate(pool):
                if trip["kunde"] in blocked_customers_by_day[day]:
                    continue
                
                for truck in avail_trucks:
                    truck_max_h = schedule[day][truck]["max_hours"]
                    if schedule[day][truck]["used_hours"] + trip["dauer_h"] > truck_max_h:
                        continue
                    
                    switch_bonus = 0
                    if last_booked_product == "2 - Hackschnitzel" and trip["produkt"] == "1 - Sägemehl":
                        switch_bonus = 1
                    elif last_booked_product == "1 - Sägemehl" and trip["produkt"] == "2 - Hackschnitzel":
                        switch_bonus = 1
                    
                    current_score = trip["base_score"] + switch_bonus
                    
                    if current_score > best_total_score:
                        best_total_score = current_score
                        best_candidate_idx = idx
                        best_assigned_truck = truck
                        best_trip_data = trip.copy()
                        best_trip_data["switch_bonus"] = switch_bonus
                        best_trip_data["total_score"] = current_score

            if best_candidate_idx != -1 and best_assigned_truck is not None:
                schedule[day][best_assigned_truck]["planned_tours"].append(best_trip_data)
                schedule[day][best_assigned_truck]["used_hours"] += best_trip_data["dauer_h"]
                pool.pop(best_candidate_idx)
            else:
                break

    for p in pool:
        reason = "Schichtzeit-Kapazität erschöpft"
        if p["kunde"] in selected_blocked_custs:
            reason = "Kunde gesperrt (Annahmestopp)"
        unassigned_trips.append(f"{p['kunde']} ({p['produkt']} | Umlauf: {p['dauer_h']}h) ➔ {reason}")

    for day in planning_days:
        for truck in TRUCK_PRIO:
            hrs = schedule[day][truck]["used_hours"]
            if 0 < hrs < 4.0 and len(schedule[day][truck]["booked_tours"]) == 0:
                freed_tours = schedule[day][truck]["planned_tours"]
                schedule[day][truck]["planned_tours"] = []
                schedule[day][truck]["used_hours"] = 0.0
                schedule[day][truck]["status"] = "under_4h"
                
                for f_trip in freed_tours:
                    reassigned = False
                    other_trucks = [t for t in TRUCK_PRIO if t != truck and t not in blocked_trucks[day]]
                    for ot in other_trucks:
                        if schedule[day][ot]["used_hours"] + f_trip["dauer_h"] <= schedule[day][ot]["max_hours"]:
                            schedule[day][ot]["planned_tours"].append(f_trip)
                            schedule[day][ot]["used_hours"] += f_trip["dauer_h"]
                            reassigned = True
                            break
                    if not reassigned:
                        unassigned_trips.append(f"{f_trip['kunde']} ({f_trip['produkt']}) ➔ Freigestellt (< 4h Schicht)")

    assigned_count = total_open_trips - len(unassigned_trips)
    return schedule, unassigned_trips, max(0, assigned_count)

computed_schedule, unassigned_trips, total_assigned = optimize_schedule()

# ==========================================
# SIDEBAR STATUS-ANZEIGE
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("📊 Kontingent-Status (Woche)")
st.sidebar.metric(label="📦 Soll Eigenfuhrpark", value=f"{total_quota_trips} Fuhren")
st.sidebar.metric(label="✅ Verbucht Eigenfuhrpark", value=f"{total_booked_trips} Fuhren")
st.sidebar.metric(label="🚛 Fremdspedition Soll", value=f"{total_ext_soll_trips} Fuhren")
st.sidebar.metric(label="⏳ Noch Offen / Unverbucht", value=f"{total_open_trips} Fuhren")

if unassigned_trips:
    st.sidebar.error(f"⚠️ **{len(unassigned_trips)} Fuhren nicht disponierbar!**")

# ==========================================
# ANSICHTEN & TABS
# ==========================================
tab_day, tab_week, tab_booked = st.tabs(["⏱️ Tages-Zeitleiste & Verbuchung", "📅 Dynamische Wochenübersicht", "📌 Verbuchte Touren & Fremdfuhren"])

with tab_day:
    st.subheader(f"⏱️ Schichtplan für {selected_day}")

    for truck in TRUCK_PRIO:
        truck_data = computed_schedule[selected_day][truck]
        has_extra = truck_data["has_extra_driver"]
        
        badge_extra = " 🟢 **[AUSHILFSFAHRER 17–21 UHR]**" if has_extra else ""
        st.markdown(f"#### 🚚 LKW: `{truck}`" + (" *(Springer)*" if truck == "RA KH 24" else "") + badge_extra)
        
        if truck in blocked_trucks[selected_day]:
            st.error(f"❌ **WERKSTATT / AUSFALL** am {selected_day}")
            st.divider()
            continue
            
        if has_extra:
            st.success(f"🟢 **Aushilfsfahrer aktiv:** Zeitfenster um 4 Stunden (17:00 – 21:00 Uhr) erweitert.")
            
        booked_tours = truck_data["booked_tours"]
        planned_tours = truck_data["planned_tours"]
        total_hrs = truck_data["used_hours"]
        max_hrs = truck_data["max_hours"]
        
        booked_hrs = sum(b.get("dauer_h", 0) for b in booked_tours)
        
        if truck_data["status"] == "under_4h" and not booked_tours:
            st.warning("🔄 **Anderweitiger Einsatz:** Fahrzeit war < 4,0 Std.")
            st.divider()
            continue
            
        if not planned_tours and not booked_tours:
            st.info(f"Keine Fuhren für {truck} an diesem Tag.")
            st.divider()
            continue
            
        st.caption(f"Arbeitszeit: **Gebucht {booked_hrs:.2f} / Geplant {total_hrs:.2f} Std.** *(Max. {max_hrs:.1f} Std.)*")
        
        start_hour, start_min = 6, 0
        
        for tour in booked_tours:
            end_min = start_min + int(tour["dauer_h"] * 60)
            end_hour = start_hour + (end_min // 60)
            rem_min = end_min % 60
            time_str = f"{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{rem_min:02d}"
            
            st.success(f"✅ **VERBUCHT** ({time_str}) | Kunde: **{tour['kunde']}** | Material: **{tour['produkt']}** ({truck_cap} m³)")
            start_hour, start_min = end_hour, rem_min

        for idx, tour in enumerate(planned_tours):
            end_min = start_min + int(tour["dauer_h"] * 60)
            end_hour = start_hour + (end_min // 60)
            rem_min = end_min % 60
            time_str = f"{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{rem_min:02d}"
            tour_id = f"{selected_day}_{truck}_{tour['kunde']}_{tour['produkt']}_{idx}"
            
            col_time, col_details, col_action = st.columns([1.5, 3.5, 1.5])
            col_time.markdown(f"🕒 **{time_str}**  \n`Dauer: {tour['dauer_h']:.2f}h`")
            col_details.markdown(f"**{tour['kunde']}**  \n📦 Material: **{tour['produkt']}** | 🚛 Vol: **{truck_cap} m³**  \n⭐ **Score: {tour['total_score']} Pkt.**")
            
            if col_action.button("📌 Verbuchen", key=f"btn_{tour_id}"):
                st.session_state.booked_trips.append({
                    "id": tour_id,
                    "Tag": selected_day,
                    "Fahrzeug": truck,
                    "Zeitfenster": time_str,
                    "Kunde": tour["kunde"],
                    "Produkt": tour["produkt"],
                    "Menge_m3": truck_cap,
                    "dauer_h": tour["dauer_h"],
                    "is_manual": False
                })
                save_persistent_data()
                st.rerun()
                
            start_hour, start_min = end_hour, rem_min
            
        st.divider()

    if unassigned_trips:
        st.error(f"⚠️ **{len(unassigned_trips)} Fuhren aus dem Wochen-Kontingent konnten nicht disponiert werden:**")
        for item in unassigned_trips:
            st.write(f"- {item}")

with tab_week:
    st.subheader("📅 Dynamische Wochenübersicht")
    week_summary = []
    for day in WEEKDAYS:
        day_row = {"Tag": day}
        for truck in TRUCK_PRIO:
            if truck in blocked_trucks[day]:
                day_row[truck] = "❌ WERKSTATT"
            else:
                t_data = computed_schedule[day][truck]
                b_tours = t_data["booked_tours"]
                p_tours = t_data["planned_tours"]
                t_hrs = t_data["used_hours"]
                has_ex = t_data["has_extra_driver"]
                
                ex_tag = "<br><span style='color:green; font-weight:bold;'>🟢 Aushilfe 17-21h</span>" if has_ex else ""
                
                if t_data["status"] == "under_4h" and not b_tours:
                    day_row[truck] = "🔄 Freigestellt (< 4h)" + ex_tag
                elif b_tours or p_tours:
                    parts = []
                    if b_tours:
                        parts.append("<span style='color:green; font-weight:bold;'>" + ", ".join([f"{t['kunde']} ({t['produkt']})" for t in b_tours]) + "</span>")
                    if p_tours:
                        parts.append(", ".join([f"{t['kunde']} ({t['produkt']})" for t in p_tours]))
                    day_row[truck] = f"[{t_hrs:.1f}h] " + " | ".join(parts) + ex_tag
                else:
                    day_row[truck] = "—" + ex_tag
        week_summary.append(day_row)
        
    df_week = pd.DataFrame(week_summary)
    st.write(df_week.to_html(escape=False, index=False), unsafe_allow_html=True)

with tab_booked:
    st.subheader("📌 Verbuchte Touren & Historie")
    col_h1, col_h2 = st.columns(2)
    
    with col_h1:
        st.markdown("##### 🚚 Eigene Flotte")
        if st.session_state.booked_trips:
            df_booked = pd.DataFrame(st.session_state.booked_trips)
            st.dataframe(df_booked[[c for c in df_booked.columns if c != "id"]], use_container_width=True)
            if st.button("🗑️ Eigene Historie zurücksetzen"):
                st.session_state.booked_trips = []
                save_persistent_data()
                st.rerun()
        else:
            st.info("Keine eigenen Touren verbucht.")
            
    with col_h2:
        st.markdown("##### 🚛 Fremdspeditionen")
        if st.session_state.ext_booked_trips:
            st.dataframe(pd.DataFrame(st.session_state.ext_booked_trips), use_container_width=True)
            if st.button("🗑️ Fremdfuhren-Historie zurücksetzen"):
                st.session_state.ext_booked_trips = []
                save_persistent_data()
                st.rerun()
        else:
            st.info("Keine Fremdfuhren verbucht.")