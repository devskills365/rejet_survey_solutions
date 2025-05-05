import os
import ssaw as ss

# Configuration (utilisation des variables d'environnement pour éviter les informations sensibles)
API_USER = os.environ.get("SSAW_API_USER") or "https://evaluation.sindevstat.com/"
API_TOKEN = os.environ.get("SSAW_API_TOKEN") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjMyNGY1YTE1ODc0ZmZiOTljOWNhZmFiYWWAYOUR_TOKEN_HERE"
UTILISATEUR = os.environ.get("SSAW_UTILISATEUR") or "user_API"
MOT_DE_PASSE = os.environ.get("SSAW_MOT_DE_PASSE") or "user_API_password_01"
WORKSPACE = os.environ.get("SSAW_WORKSPACE") or "primary"

def test_connexion_ssaw():
    """Teste la connexion à l'API SSAW."""
    try:
        print("Initialisation du client SSAW...")
        client = ss.Client(
            url=API_USER,
            api_user=UTILISATEUR,
            api_password=MOT_DE_PASSE,
            token=API_TOKEN,
            workspace=WORKSPACE
        )

        print("Liste des attributs de 'client.session':", dir(client.session))

        # Tester la connexion en effectuant une requête GET à l'URL de base
        response = client.session.get(client.baseurl)
        if response.status_code == 200:
            print("Connexion réussie. Code d'état HTTP :", response.status_code)
            return client
        else:
            print(f"Échec de la connexion. Code d'état HTTP : {response.status_code}")
            return None

    except Exception as e:
        print(f"Erreur de connexion globale : {e}")
        return None

def afficher_interviews(client):
    """Affiche la liste des interviews en utilisant l'API SSAW."""
    try:
        print("Récupération des interviews...")

        # Récupérer la liste des interviews
        interviews_api = ss.InterviewsApi(client)
        fields = [
            'id',
            'questionnaire_id',
            'questionnaire_version',
            'assignment_id',
            'responsible_id',
            'errors_count',
            'status'
        ]
        interviews = interviews_api.get_list(fields=fields)

        # Afficher les interviews
        print("\nListe des interviews :")
        count = 0
        for interview in interviews:
            print(f"Interview ID: {interview.id}")
            print(f"Questionnaire ID: {interview.questionnaire_id}")
            print(f"Version: {interview.questionnaire_version}")
            print(f"Assignment ID: {interview.assignment_id}")
            print(f"Responsable ID: {interview.responsible_id}")
            print(f"Nombre d'erreurs: {interview.errors_count}")
            print(f"Statut: {interview.status}")
            print("-" * 50)
            count += 1

        if count == 0:
            print("Aucune interview trouvée dans le workspace spécifié.")
        else:
            print(f"Total des interviews affichées : {count}")

        return True

    except Exception as e:
        print(f"Erreur lors de la récupération des interviews : {e}")
        return False

if __name__ == "__main__":
    # Tester la connexion
    client = test_connexion_ssaw()
    if client:
        print("Test de connexion SSAW terminé avec succès.")
        # Afficher les interviews si la connexion est réussie
        if afficher_interviews(client):
            print("Récupération et affichage des interviews terminés avec succès.")
        else:
            print("Échec de la récupération des interviews.")
    else:
        print("Le test de connexion SSAW a échoué.")