import ssaw
from ssaw import Client, QuestionnairesApi

# === Paramètres ===
url_api = 'https://evaluation.sindevstat.com'
user = 'user_API'
password = 'user_API_password_01'
workspace = 'primary'

# === Connexion à l’API ===
try:
    client = Client(url_api, api_user=user, api_password=password, workspace=workspace)
    print("Connexion à l'API réussie.")

    # === Récupération et affichage des questionnaires ===
    print("\nListe des questionnaires disponibles :")
    print("-------------------------------------")
    questionnaires = QuestionnairesApi(client).get_list()
    
    if not questionnaires:
        print("Aucun questionnaire trouvé dans l'espace de travail.")
    else:
        for q in questionnaires:
            print(f"Variable: {q.variable}, Version: {q.version}, Titre: {q.title}, ID: {q.questionnaire_id}")

except Exception as e:
    print(f"Erreur lors de la connexion ou de la récupération des questionnaires : {e}")