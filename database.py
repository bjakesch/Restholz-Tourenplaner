import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ==========================================
# INITIALISIERUNG MIT SECRETS
# ==========================================
@st.cache_resource
from google.cloud.firestore_v1.services.firestore.transports.rest import FirestoreRestTransport

def init_db():
    if not firebase_admin._apps:
        key_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        
    # Wir zwingen Firestore, das robuste HTTP-Protokoll (REST) zu nutzen!
    transport = FirestoreRestTransport()
    return firestore.client(transport=transport)

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
