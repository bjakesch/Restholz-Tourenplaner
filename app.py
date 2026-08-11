import streamlit as st
import datetime

# ==========================================
# IMPORTE FÜR SPÄTER (Module, die wir noch bauen)
# ==========================================
# import database as db
# import logistics as log

# Seitenkonfiguration (muss als erstes aufgerufen werden)
st.set_page_config(
    page_title="Logistik & Tourenplanung",
    page_icon="🚛",
    layout="wide"
)

def main():
    # Sidebar für die Navigation
    st.sidebar.title("Navigation")
    menu_selection = st.sidebar.radio(
        "Gehe zu:", 
        ["Dashboard", "Kontingentplanung", "Tourenplanung"]
    )

    # Routing zu den entsprechenden Seiten
    if menu_selection == "Dashboard":
        render_dashboard()
    elif menu_selection == "Kontingentplanung":
        render_kontingentplanung()
    elif menu_selection == "Tourenplanung":
        render_tourenplanung()

def render_dashboard():
    st.title("🚛 Dashboard")
    st.markdown("Willkommen in der zentralen Logistik-Planung.")
    
    # Platzhalter für schnelle KPIs (Key Performance Indicators)
    st.subheader("Aktuelle Übersicht (Heute)")
    col1, col2, col3 = st.columns(3)
    
    # Später kommen diese Daten dynamisch aus der database.py
    col1.metric(label="Geplante Touren", value="12")
    col2.metric(label="Offenes Kontingent", value="450 t")
    col3.metric(label="Verfügbare LKW", value="8")
    
    st.divider()
    st.info("Nutze die Navigation auf der linken Seite, um Kontingente zu erfassen oder Touren zu planen.")

def render_kontingentplanung():
    st.title("📦 Kontingent- und Schichtplanung")
    st.markdown("Erfasse hier die verfügbaren Mengen und Ressourcen für die kommenden Schichten.")
    
    # Eingabeformular für Kontingente
    with st.form("form_kontingent"):
        col1, col2 = st.columns(2)
        
        with col1:
            datum = st.date_input("Planungsdatum", datetime.date.today())
            schicht = st.selectbox("Schicht", ["Frühschicht", "Spätschicht", "Nachtschicht"])
        
        with col2:
            menge = st.number_input("Zu transportierende Menge (t)", min_value=0.0, step=1.0)
            lkw_anzahl = st.number_input("Verfügbare LKW in dieser Schicht", min_value=0, step=1)
            
        bemerkung = st.text_input("Bemerkung (optional)")
        
        submit_btn = st.form_submit_button("Kontingent speichern")
        
        if submit_btn:
            # ==========================================
            # HIER KOMMT SPÄTER DIE DATENBANK-LOGIK REIN
            # db.save_quota(datum, schicht, menge, lkw_anzahl, bemerkung)
            # ==========================================
            st.success(f"Das Kontingent für den {datum.strftime('%d.%m.%Y')} ({schicht}) wurde erfolgreich gespeichert!")

def render_tourenplanung():
    st.title("🗺️ Tourenplanung")
    st.markdown("Berechne und verteile die optimalen Touren basierend auf den erfassten Kontingenten.")
    
    # Filter für die Planung
    plan_datum = st.date_input("Datum für die Tourenplanung wählen:", datetime.date.today())
    
    if st.button("Touren berechnen", type="primary"):
        with st.spinner("Berechne optimale Routen und LKW-Zuweisungen..."):
            # ==========================================
            # HIER KOMMT SPÄTER DIE LOGISTIK- & DATENBANK-LOGIK REIN
            # kontingente = db.get_quotas(plan_datum)
            # berechnete_touren = log.calculate_tours(kontingente)
            # ==========================================
            
            # Dummy-Tabelle, bis wir die Logik haben
            st.success("Berechnung abgeschlossen!")
            
            dummy_data = [
                {"Tour-ID": "T-01", "LKW": "LKW 1", "Schicht": "Frühschicht", "Menge": "25 t", "Status": "Zugewiesen"},
                {"Tour-ID": "T-02", "LKW": "LKW 2", "Schicht": "Frühschicht", "Menge": "24 t", "Status": "Zugewiesen"},
                {"Tour-ID": "T-03", "LKW": "LKW 1", "Schicht": "Spätschicht", "Menge": "25 t", "Status": "Ausstehend"},
            ]
            st.table(dummy_data)
            
        if st.button("Diesen Tourenplan speichern"):
            # db.save_tour_plan(berechnete_touren)
            st.success("Tourenplan wurde in der Datenbank gesichert.")

if __name__ == "__main__":
    main()
