import os
from google.cloud import firestore

def test_firestore():
    os.environ["GOOGLE_CLOUD_PROJECT"] = "heartbyte-7f626"
    print("Initializing Firestore Client...")
    try:
        db = firestore.Client()
        print("Writing test document...")
        doc_ref = db.collection('test_collection').document('test_doc')
        doc_ref.set({'status': 'working'})
        print("Successfully wrote to Firestore!")
    except Exception as e:
        print(f"Firestore Error: {e}")

if __name__ == "__main__":
    test_firestore()
