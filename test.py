
from ssaw import InterviewsApi
import pandas as pd
import ssaw
import os

# Charger les données depuis un fichier Excel
df = pd.read_excel("data.xlsx")
list_id = df["interview__id"]

# Remplacez par l'URL de votre serveur et votre token API
API_USER = os.environ.get("SSAW_API_USER") or "https://devskills365-demo.mysurvey.solutions"
API_TOKEN = os.environ.get("SSAW_API_TOKEN") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjMyNGY1YTE1ODc0ZmZiOTljOWNhZmFiYWQ0MjFlMCIsImp0aSI6IjZlZDljNDA4Zjg2MjQ5YjRiMmM3MWQ4YjU4OGJlYjc5IiwibmJmIjoxNzM3OTY3MzY2LCJleHAiOjE3NTM3MzUzNjYsImlzcyI6IlN1cnZleS5Tb2x1dGlvbnMiLCJhdWQiOiJBbGwifQ.WdgXK119PBz-QHUabKhCpebKVlDZybgF1EhGmcKnlJ8"
UTILISATEUR = os.environ.get("SSAW_UTILISATEUR") or "admin"
MOT_DE_PASSE = os.environ.get("SSAW_MOT_DE_PASSE") or "s+R94oxY93"
WORKSPACE = os.environ.get("SSAW_WORKSPACE") or "devskills365"

# Initialiser le client
clientA = ssaw.Client(url=API_USER, api_user=UTILISATEUR, api_password=MOT_DE_PASSE, token=API_TOKEN, workspace=WORKSPACE)

# Afficher les ID des entretiens disponibles sur le serveur
try:
    available_interviews = InterviewsApi(clientA).get_list()
    available_ids = [interview['id'] for interview in available_interviews]
    print("ID des entretiens disponibles sur le serveur :")
    for interview_id in available_ids:
        print(interview_id)
except Exception as e:
    print(f"Erreur lors de la récupération des entretiens : {e}")

# Rejeter les interviews
for idn in list_id:
    try:
        if idn in available_ids:
            InterviewsApi(clientA).reject(idn, 'comment')
            print(f"Rejeté {idn}")
        else:
            print(f"Interview dont se trouvantnon trouvée {idn}")
    except Exception as e:
        print(f"Non rejeté {idn} : {e}")
