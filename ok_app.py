from ssaw import InterviewsApi
import pandas as pd
import ssaw
import os
# Charger les données depuis un fichier Excel
df = pd.read_excel("data.xlsx")
list_id_readable = df["interview__id"]  # Liste d'ID lisibles à traiter

# Table de correspondance entre ID lisibles et ID serveur
id_mapping = [
    "e720b0c2c85844d091bf36742a66c0b1",
    "c47b6f849e1c4c9ab2320d3a94eb8412",
    "cd51cab346a1497eb0dace9b296163dc",
    # Ajoutez d'autres IDs ici...
]

# Remplacez par l'URL de votre serveur et votre token API
API_USER = os.environ.get("SSAW_API_USER") or "https://devskills365-demo.mysurvey.solutions"
API_TOKEN = os.environ.get("SSAW_API_TOKEN") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjMyNGY1YTE1ODc0ZmZiOTljOWNhZmFiYWQ0MjFlMCIsImp0aSI6IjZlZDljNDA4Zjg2MjQ5YjRiMmM3MWQ4YjU4OGJlYjc5IiwibmJmIjoxNzM3OTY3MzY2LCJleHAiOjE3NTM3MzUzNjYsImlzcyI6IlN1cnZleS5Tb2x1dGlvbnMiLCJhdWQiOiJBbGwifQ.WdgXK119PBz-QHUabKhCpebKVlDZybgF1EhGmcKnlJ8"
UTILISATEUR = os.environ.get("SSAW_UTILISATEUR") or "admin"
MOT_DE_PASSE = os.environ.get("SSAW_MOT_DE_PASSE") or "s+R94oxY93"
WORKSPACE = os.environ.get("SSAW_WORKSPACE") or "devskills365"

# Initialiser le client
clientA = ssaw.Client(url=API_USER, api_user=UTILISATEUR, api_password=MOT_DE_PASSE, token=API_TOKEN, workspace=WORKSPACE)

# Fonction pour trouver l'ID serveur correspondant à un ID lisible
# Fonction pour trouver l'ID serveur correspondant à un ID lisible
def readable_to_server(readable_id, mapping):
    """
    Recherche un ID serveur correspondant à un ID lisible dans une liste.
    Si l'ID lisible est présent dans la liste, il est considéré comme valide.
    """
    return readable_id if readable_id in mapping else None

# Rejeter les interviews
for readable_id in list_id_readable:
    try:
        server_id = readable_to_server(readable_id, id_mapping)  # Vérifie la correspondance
        if server_id:
            InterviewsApi(clientA).reject(server_id, 'Raison du rejet')  # Rejeter l'interview
            print(f"Rejeté : ID serveur ({server_id})")
        else:
            print(f"ID non trouvé dans la liste de correspondance : {readable_id}")
    except Exception as e:
        print(f"Erreur lors du rejet de l'ID lisible ({readable_id}) : {e}")