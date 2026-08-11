import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

def init_db():
    # Prüfen, ob Firebase schon initialisiert wurde (verhindert Abstürze)
    if not firebase_admin._apps:
        key_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def load_app_state():
    db = init_db()
    # Dokument aus Firestore abrufen
    doc = db.collection("config").document("app_state").get()
    
    if doc.exists:
        return doc.to_dict()
    return {}

def save_app_state(data):
    db = init_db()
    # Dokument in Firestore schreiben (erstellt es automatisch, falls es nicht existiert)
    db.collection("config").document("app_state").set(data)
