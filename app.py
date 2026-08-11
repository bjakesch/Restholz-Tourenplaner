import streamlit as st
import pandas as pd
import os
from datetime import datetime

import database as db

# ==========================================
# PAGE CONFIG & PFADE
# ==========================================
st.set_page_config(page_title="Restholz-Tourenplaner Sägewerk", layout="wide", page_icon="🪵")

# ==========================================
# CUSTOM CSS (FARBANPASSUNG & KALENDER-STYLES)
# ==========================================
st.markdown("""
    <style>
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] { background-color: #2e7d32 !important; color: white !important; }
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] span { color: white !important; }
    div[aria-label*="Aushilfsfahrer"] span[data-baseweb="tag"] svg { fill: white !important; }
    .cal-day-header { background-color: #f0f2f6; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 10px; border: 1px solid #dcdcdc; }
    .cal-card { border-left: 4px solid #1b5e20; background-color: #ffffff; padding: 6px 8px; border-radius: 4px; margin-bottom: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 0.85em; }
    .cal-card-manual { border-left: 4px solid #1976d2; background-color: #f5f9ff; }
    </style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# KONSTANTEN
# ==========================================
PRODUCT_LIST = ["1 - Sägemehl", "2 - Hackschnitzel", "3 - Rinde", "4 - Kappholz"]
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
WEEKDAYS_WITH_EMPTY = [""] + WEEKDAYS
TRUCK_PRIO = ["RA KH 14", "RA KH 92", "RA KH 24"]
EXT_COL_ORDER = ["Produkt / Artikel", "Kunde", "Frachtführer / Spedition", "SOLL (Fuhren)", "IST (Erfüllt)", "Einsatztag", "Bemerkung / Uhrzeit"]

# ==========================================
# FUNKTIONEN (Müssen vor dem Aufruf definiert werden!)
# ==========================================
def load_persistent_data():
    st.warning("⏳ Verbinde mit Firebase...") # DEBUG ANZEIGE
    data = db.load_app_state()
    st.success("✅ Firebase Antwort erhalten!") # DEBUG ANZEIGE
    return data

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
    db.save_app_state(data)

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
# CLOUD STATE-SYNC (Einmalig beim Start)
# ==========================================
if "firebase_loaded" not in st.session_state:
    st.info("🚀 Initialisiere Start-Prozess...")
    saved_data = load_persistent_data()

    st.session_state["shift_hours"] = float(saved_data.get("shift_hours", 9.0))
    st.session_state["truck_cap"] = int(saved_data.get("truck_cap", 103))
    st.session_state["selected_day"] = saved_data.get("selected_day", "Montag")
    st.session_state["booked_trips"] = saved_data.get("booked_trips", [])
    st.session_state["ext_booked_trips"] = saved_data.get("ext_booked_trips", [])

    b_saved = saved_data.get("bunkers", {})
    st.session_state["bunker_sm"] = b_saved.get("bunker_sm", 50)
    st.session_state["bunker_hs"] = b_saved.get("bunker_hs", 50)
    st.session_state["bunker_ri"] = b_saved.get("bunker_ri", 50)
    st.session_state["bunker_kp"] = b_saved.get("bunker_kp", 50)

    saved_blocked_trucks = saved_data.get("blocked_trucks", {})
    saved_extra_drivers = saved_data.get("extra_drivers", {})
    saved_blocked_custs = saved_data.get("blocked_customers", {})

    for day in WEEKDAYS:
        st.session_state[f"block_truck_{day}"] = saved_blocked_trucks.get(day, [])
        st.session_state[f"extra_driver_{day}"] = saved_extra_drivers.get(day, [])
        st.session_state[f"block_cust_{day}"] = saved_blocked_custs.get(day, [])

    if "customer_db" in saved_data and saved_data["customer_db"]:
        st.session_state["customer_db"] = pd.DataFrame(saved_data["customer_db"])
    else:
        st.session_state["customer_db"] = pd.DataFrame([
            {"Kunde": "SIAT Urmatt", "Umlaufzeit (hh:mm)": "03:55", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
            {"Kunde": "JRS Ettenheim", "Umlaufzeit (hh:mm)": "03:15", "1 - Sägemehl": True, "2 - Hackschnitzel": False, "3 - Rinde": False, "4 - Kappholz": False},
            {"Kunde": "Trendel", "Umlaufzeit (hh:mm)": "02:38", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False},
            {"Kunde": "Rheinspan Germersheim", "Umlaufzeit (hh:mm)": "04:03", "1 - Sägemehl": True, "2 - Hackschnitzel": True, "3 - Rinde": False, "4 - Kappholz": False}
        ])

    if "ext_terminal_db" in saved_data and saved_data["ext_terminal_db"]:
        df_ext = pd.DataFrame(saved_data["ext_terminal_db"])
        st.session_state["ext_terminal_db"] = df_ext.reindex(columns=[c for c in EXT_COL_ORDER if c in df_ext.columns])
    else:
        st.session_state["ext_terminal_db"] = pd.DataFrame([
            {"Produkt / Artikel": "1 - Sägemehl", "Kunde": "SIAT Urmatt", "Frachtführer / Spedition": "Spedition Müller", "SOLL (Fuhren)": 0, "IST (Erfüllt)": 0, "Einsatztag": "", "Bemerkung / Uhrzeit": "Avisierung vorab"}
        ], columns=EXT_COL_ORDER)

    if "quotas_state" in saved_data and saved_data["quotas_state"]:
        st.session_state["quotas_state"] = {tuple(k.split("|||")): v for k, v in saved_data["quotas_state"].items()}
    else:
        st.session_state["quotas_state"] = {
            ("Rheinspan Germersheim", "2 - Hackschnitzel"): {"soll": 0, "rest": "Zwingend Dienstag 07:00 Uhr", "prio": 4}
        }
        
    st.session_state["firebase_loaded"] = True

# ==========================================
# RESET-LOGIK (CALLBACK)
# ==========================================
def perform_global_reset():
    clean_quotas = {f"{k[0]}|||{k[1]}": {"soll": 0, "rest": v.get("rest", "Keine"), "prio": v.get("prio", 3)} for k, v in st.session_state.quotas_state.items()}
    clean_ext_terminal = st.session_state.ext_terminal_db.copy()
    clean_ext_terminal["SOLL (Fuhren)"] = 0
    clean_ext_terminal["IST (Erfüllt)"] = 0
    
    reset_data = {
        "shift_hours": 9.0, "truck_cap": 103, "selected_day": "Montag",
        "blocked_trucks": {day: [] for day in WEEKDAYS},
        "extra_drivers": {day: [] for day in WEEKDAYS},
        "blocked_customers": {day: [] for day in WEEKDAYS},
        "bunkers": {"bunker_sm": 50, "bunker_hs": 50, "bunker_ri": 50, "bunker_kp": 50},
        "customer_db": st.session_state.customer_db.to_dict(orient="records"),
        "ext_terminal_db": clean_ext_terminal.to_dict(orient="records"),
        "quotas_state": clean_quotas, "booked_trips": [], "ext_booked_trips": []
    }
    db.save_app_state(reset_data)
    st.rerun()

# ==========================================
# HEADER & SIDEBAR
# ==========================================
col_head, col_logo = st.columns([4, 1])
with col_head:
    st.title("🪵 Restholz-Tourenplaner Sägewerk")
    st.markdown("Automatisierte Schichtplanung mit **Firebase Cloud Speicherung**")

st.sidebar.header("⚙️ Fahrzeuge & Schichtzeit")
shift_hours = st.sidebar.number_input("Max. Schichtzeit (Std./Tag)", step=0.5, key="shift_hours", on_change=save_persistent_data)
truck_cap = st.sidebar.number_input("Kapazität Sattelzug (m³)", step=1, key="truck_cap", on_change=save_persistent_data)
selected_day = st.sidebar.select_slider("Aktueller Planungstag", options=WEEKDAYS, key="selected_day", on_change=save_persistent_data)
selected_day_idx = WEEKDAYS.index(selected_day)

st.sidebar.divider()
st.sidebar.subheader("🚛 Fahrzeugverfügbarkeit")
blocked_trucks = {}
extra_drivers = {}

for day in WEEKDAYS:
    st.sidebar.markdown(f"**{day}:**")
    blocked_trucks[day] = st.sidebar.multiselect(f"❌ Ausfall am {day}:", options=TRUCK_PRIO, key=f"block_truck_{day}", on_change=save_persistent_data)
    avail_for_extra = [t for t in TRUCK_PRIO if t not in st.session_state.get(f"block_truck_{day}", [])]
    extra_drivers[day] = st.sidebar.multiselect(f"🟢 Aushilfe (17–21 Uhr) am {day}:", options=avail_for_extra, key=f"extra_driver_{day}", on_change=save_persistent_data)

st.sidebar.divider()
st.sidebar.button("💥 Alles zurücksetzen (Reset)", use_container_width=True, type="secondary", on_click=perform_global_reset)
if st.sidebar.button("🔄 Planung neu berechnen", use_container_width=True, type="primary"):
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
            "_Produkt_Raw": None, "_Kunde_Raw": None, "_Dauer_h": None,
            "Produkt / Artikel": st.column_config.TextColumn("Produkt / Artikel", width="medium"),
            "Kunde": st.column_config.TextColumn("Kunde (Umlaufzeit)", width="medium"),
            "SOLL (Geplante Fuhren)": st.column_config.NumberColumn("SOLL", min_value=0, max_value=50, step=1),
            "IST (Gebucht)": st.column_config.NumberColumn("IST", min_value=0, max_value=50),
            "Fix-Termine / Restriktionen": st.column_config.TextColumn("Restriktionen", width="large"),
            "Priorität (1-5)": st.column_config.NumberColumn("Prio", min_value=1, max_value=5, step=1)
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

    st.markdown("#### 🚫 Kundensperren / Annahmestopp")
    all_customer_names = [str(r["Kunde"]).strip() for _, r in edited_cust_db.iterrows() if str(r["Kunde"]).strip()]
    blocked_customers_by_day = {day: set() for day in WEEKDAYS}
    
    selected_blocked_custs = st.multiselect(
        f"Annahmestopp ab {selected_day}:",
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
            "Produkt / Artikel": st.column_config.SelectboxColumn("Produkt", options=PRODUCT_LIST, default="1 - Sägemehl"),
            "Kunde": st.column_config.TextColumn("Kunde (Freitext)", default="", required=True),
            "Frachtführer / Spedition": st.column_config.TextColumn("Spedition", default="", required=True),
            "SOLL (Fuhren)": st.column_config.NumberColumn("SOLL", min_value=0, max_value=100, step=1, default=0),
            "IST (Erfüllt)": st.column_config.NumberColumn("IST", min_value=0, max_value=100, step=1, default=0),
            "Einsatztag": st.column_config.SelectboxColumn("Tag", options=WEEKDAYS_WITH_EMPTY, default=""),
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
            "id": m_id, "Tag": m_day, "Fahrzeug": m_truck, "Zeitfenster": "Manuell eingeplant",
            "Kunde": m_kunde_raw, "Produkt": m_prod, "Menge_m3": truck_cap, "dauer_h": m_dauer,
            "score": 99, "is_manual": True
        })
        save_persistent_data()
        st.success("Tour manuell verbucht!")
        st.rerun()

st.divider()

# ==========================================
# PLANUNGS-ALGORITHMUS INKL. SCORE-BERECHNUNG
# ==========================================
bunker_levels = {
    "1 - Sägemehl": st.session_state.bunker_sm,
    "2 - Hackschnitzel": st.session_state.bunker_hs,
    "3 - Rinde": st.session_state.bunker_ri,
    "4 - Kappholz": st.session_state.bunker_kp,
}

remaining_quotas = {}
for k, v in st.session_state.quotas_state.items():
    already_booked = sum(1 for b in st.session_state.booked_trips if b.get("Kunde") == k[0] and b.get("Produkt") == k[1])
    remaining_quotas[k] = max(0, v.get("soll", 0) - already_booked)

schedule_by_day = {day: {t: [] for t in TRUCK_PRIO} for day in WEEKDAYS}
truck_used_hours = {day: {t: 0.0 for t in TRUCK_PRIO} for day in WEEKDAYS}

for b in st.session_state.booked_trips:
    b_day, b_truck = b.get("Tag"), b.get("Fahrzeug")
    if b_day in WEEKDAYS and b_truck in TRUCK_PRIO:
        if "score" not in b: b["score"] = 99
        schedule_by_day[b_day][b_truck].append(b)
        truck_used_hours[b_day][b_truck] += b.get("dauer_h", 2.0)

for day in WEEKDAYS:
    active_trucks = [t for t in TRUCK_PRIO if t not in blocked_trucks.get(day, [])]
    extra_d_list = extra_drivers.get(day, [])
    truck_max_hours = {t: shift_hours + (4.0 if t in extra_d_list else 0.0) for t in active_trucks}

    candidates = []
    for (c_name, p_name), rem_qty in remaining_quotas.items():
        if rem_qty <= 0 or c_name in blocked_customers_by_day.get(day, set()): continue
        if bunker_levels.get(p_name, 50) <= 10: continue
            
        dur = cust_duration_map.get(c_name, 2.0)
        q_info = st.session_state.quotas_state.get((c_name, p_name), {})
        b_level = bunker_levels.get(p_name, 50)
        
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
                if truck_used_hours[day][t] + cand["dauer_h"] <= truck_max_hours[t] + 0.1:
                    start_t = 6.0 + truck_used_hours[day][t]
                    schedule_by_day[day][t].append({
                        "id": f"auto_{day}_{t}_{len(schedule_by_day[day][t])}", "Tag": day, "Fahrzeug": t,
                        "Zeitfenster": f"{format_hours(start_t)} - {format_hours(start_t + cand['dauer_h'])} Uhr",
                        "Kunde": cand["Kunde"], "Produkt": cand["Produkt"], "Menge_m3": truck_cap,
                        "dauer_h": cand["dauer_h"], "score": cand["score"], "is_manual": False, "Bemerkung": cand["rest_req"]
                    })
                    truck_used_hours[day][t] += cand["dauer_h"]
                    remaining_quotas[c_key] -= 1
                    assigned = True
                    break
            if not assigned: break

# ==========================================
# BEREICH 6: WOCHENKALENDER & TAGESANSICHT
# ==========================================
st.header("🗓️ Tourenplanung & Kalenderansicht")
tab_outlook_cal, tab_tageskacheln = st.tabs(["📅 Wochenkalender", "📌 Tagesansicht"])

with tab_outlook_cal:
    cal_cols = st.columns(5)
    for idx, day in enumerate(WEEKDAYS):
        with cal_cols[idx]:
            st.markdown(f"<div class='cal-day-header'>{day}</div>", unsafe_allow_html=True)
            for t in TRUCK_PRIO:
                is_blocked, is_extra = t in blocked_trucks.get(day, []), t in extra_drivers.get(day, [])
                if is_blocked:
                    st.markdown(f"**🚛 {t}** <span style='color:red;'>❌ Ausfall</span>", unsafe_allow_html=True)
                else:
                    badge = "🟢" if is_extra else "✅"
                    st.markdown(f"**🚛 {t}** {badge} <small>({format_hours(truck_used_hours[day][t])}h)</small>", unsafe_allow_html=True)
                    for trip in schedule_by_day[day][t]:
                        is_man = trip.get("is_manual", False)
                        card_class, tag_type = ("cal-card-manual", "🛠️") if is_man else ("cal-card", "🤖")
                        st.markdown(f"""
                        <div class="{card_class}">
                            <strong>{tag_type} {trip.get('Zeitfenster', '').split(' ')[0]}</strong> | <b>{trip['Kunde']}</b><br>
                            <span style="color:#444;">📦 {trip['Produkt'].split(' - ')[1] if ' - ' in trip['Produkt'] else trip['Produkt']}</span>
                        </div>""", unsafe_allow_html=True)

with tab_tageskacheln:
    st.subheader(f"Detailplan für {selected_day}")
    cols_truck = st.columns(len(TRUCK_PRIO))
    for idx, t in enumerate(TRUCK_PRIO):
        with cols_truck[idx]:
            if t in st.session_state.blocked_trucks.get(selected_day, []):
                st.error(f"🚛 **{t}**\n\n❌ **FAHRZEUGAUSFALL**")
            else:
                extra_badge = " 🟢 (Aushilfe)" if t in st.session_state.extra_drivers.get(selected_day, []) else ""
                max_h = shift_hours + (4.0 if t in st.session_state.extra_drivers.get(selected_day, []) else 0.0)
                st.success(f"🚛 **{t}**{extra_badge}\n\n⏱️ **{format_hours(truck_used_hours[selected_day][t])} / {format_hours(max_h)} Std.**")
                for trip_idx, trip in enumerate(schedule_by_day[selected_day][t]):
                    is_man = trip.get("is_manual", False)
                    badge = "🛠️ [Manuell]" if is_man else "🤖 [Vorschlag]"
                    st.markdown(f"""
                    <div style="border:1px solid #ccc; padding:10px; border-radius:6px; margin-bottom:10px;">
                        <span style="font-size:0.85em; color:#555;">{badge} <strong>{trip.get('Zeitfenster', '')}</strong></span><br>
                        <span style="font-size:1.1em; font-weight:bold; color:#1b5e20;">{trip.get('Kunde', '')}</span><br>
                        <span style="color:#333;">📦 {trip.get('Produkt', '')}</span><br>
                        <span style="font-size:0.85em; font-weight:bold; color:#2e7d32;">⭐ Dispo-Score: {trip.get('score', 0)} Pkt.</span>
                    </div>""", unsafe_allow_html=True)
                    if not is_man and st.button(f"📌 Tour fest verbuchen", key=f"btn_book_{selected_day}_{t}_{trip_idx}"):
                        trip["is_manual"] = True
                        st.session_state.booked_trips.append(trip)
                        save_persistent_data()
                        st.rerun()

st.divider()
st.header("📜 Historie & Logbuch aller Fuhren")
tab_hist_eigen, tab_hist_fremd = st.tabs(["🚛 Eigenfuhrpark (Verbucht)", "🌐 Fremdfuhren (Logbuch)"])

with tab_hist_eigen:
    if st.session_state.booked_trips:
        df_booked = pd.DataFrame(st.session_state.booked_trips)
        st.dataframe(df_booked, use_container_width=True, hide_index=True)
        c_del1, c_del2 = st.columns([3, 1])
        selected_del_id = c_del1.selectbox("Tour stornieren:", options=[b.get("id") for b in st.session_state.booked_trips if "id" in b], key="del_trip_select_box")
        if c_del2.button("❌ Löschen", use_container_width=True, type="secondary"):
            st.session_state.booked_trips = [b for b in st.session_state.booked_trips if b.get("id") != selected_del_id]
            save_persistent_data()
            st.rerun()

with tab_hist_fremd:
    if st.session_state.ext_booked_trips:
        st.dataframe(pd.DataFrame(st.session_state.ext_booked_trips), use_container_width=True, hide_index=True)
