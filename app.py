import os
import ssaw as ss

# Configuration (NE PAS METTRE LES INFORMATIONS SENSIBLES EN DUR DANS LE CODE)
API_USER = os.environ.get("SSAW_API_USER") or "https://devskills365-demo.mysurvey.solutions"
API_TOKEN = os.environ.get("SSAW_API_TOKEN") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3NjMyNGY1YTE1ODc0ZmZiOTljOWNhZmFiYWQ0MjFlMCIsImp0aSI6IjZlZDljNDA4Zjg2MjQ5YjRiMmM3MWQ4YjU4OGJlYjc5IiwibmJmIjoxNzM3OTY3MzY2LCJleHAiOjE3NTM3MzUzNjYsImlzcyI6IlN1cnZleS5Tb2x1dGlvbnMiLCJhdWQiOiJBbGwifQ.WdgXK119PBz-QHUabKhCpebKVlDZybgF1EhGmcKnlJ8"
UTILISATEUR = os.environ.get("SSAW_UTILISATEUR") or "admin"
MOT_DE_PASSE = os.environ.get("SSAW_MOT_DE_PASSE") or "s+R94oxY93"
WORKSPACE = os.environ.get("SSAW_WORKSPACE") or "devskills365"

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

        return True
        
    except Exception as e:
        print(f"Erreur de connexion globale : {e}")
        return False

if __name__ == "__main__":
    if test_connexion_ssaw():
        print("Test de connexion SSAW terminé avec succès.")
    else:
        print("Le test de connexion SSAW a échoué.")