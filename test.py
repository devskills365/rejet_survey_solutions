from ssaw import Client, InterviewsApi
import ssaw.exceptions as ssaw_exceptions

try:
    # Connexion au serveur Survey Solutions avec le workspace 'primary'
    client = Client(
        url='https://evaluation.sindevstat.com',
        api_user='user_API',
        api_password='user_API_password_01',
        workspace='primary'  # Spécifier le workspace ici
    )

    # Initialisation de l'API pour les interviews
    interviews_api = InterviewsApi(client)

    # Lister les interviews sans passer le paramètre workspace à get_list
    interviews = interviews_api.get_list(fields=['id'])
    
    # Vérifier si des interviews existent et afficher les interview__id
    interview_found = False
    print("Liste des interview__id dans le workspace 'primary' :")
    for interview in interviews:
        print(interview.id)
        interview_found = True
    
    if not interview_found:
        print("Aucune interview trouvée dans le workspace 'primary'.")

except ssaw_exceptions.SsawException as e:
    print(f"Erreur lors de la connexion ou de la récupération des interviews : {e}")
except Exception as e:
    print(f"Une erreur inattendue s'est produite : {e}")