import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# INITIALISIERUNG
# ==========================================
@st.cache_resource
def init_db():
    """Initialisiert die Verbindung zu Firestore."""
    if not firebase_admin._apps:
        # Erwarte die Datei 'firebase_key.json' im selben Verzeichnis
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_db()

# ==========================================
# KONTINGENT-FUNKTIONEN
# ==========================================
def save_quota(datum, schicht, menge, lkw_anzahl, bemerkung):
    """Speichert ein neues Kontingent in der Collection 'quotas'."""
    data = {
        "datum": datum.isoformat(),
        "schicht": schicht,
        "menge": menge,
        "lkw_anzahl": lkw_anzahl,
        "bemerkung": bemerkung,
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    db.collection("quotas").add(data)

def get_quotas(datum):
    """Holt alle Kontingente für ein bestimmtes Datum."""
    date_str = datum.isoformat()
    docs = db.collection("quotas").where("datum", "==", date_str).stream()
    return [doc.to_dict() for doc in docs]

# ==========================================
# TOUREN-FUNKTIONEN
# ==========================================
def save_tour_plan(touren_liste):
    """Speichert eine Liste von Touren in der Collection 'tours'."""
    batch = db.batch()
    for tour in touren_liste:
        doc_ref = db.collection("tours").document() # Erzeugt eine neue ID
        batch.set(doc_ref, tour)
    batch.commit()

def get_tours(datum):
    """Holt alle geplanten Touren für ein Datum."""
    date_str = datum.isoformat()
    docs = db.collection("tours").where("datum", "==", date_str).stream()
    return [doc.to_dict() for doc in docs]

# ==========================================
# ZUSTANDS-FUNKTIONEN (für den app-weiten State)
# ==========================================
def save_app_state(state_dict):
    """Speichert den globalen Zustand der App (z.B. blocked_trucks)."""
    db.collection("config").document("app_state").set(state_dict)

def load_app_state():
    """Lädt den globalen Zustand."""
    doc = db.collection("config").document("app_state").get()
    return doc.to_dict() if doc.exists else {}
