import ssaw
import pandas as pd
import os
from ssaw import Client, ExportApi, QuestionnairesApi
from ssaw.models import ExportJob
from zipfile import ZipFile
import traceback
import uuid
import requests
import base64
import re
import logging

# === Paramètres ===
url_api = 'https://evaluation.sindevstat.com'
user = 'user_API'
password = 'user_API_password_01'
workspace = 'primary'
variable_qx = 'Menage_VF2_ENA2024'
download_path = os.path.join("Database", "v2")
download_type = 'STATA'
download_status = 'All'

# === Configuration du logging ===
logging.basicConfig(filename='download.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Connexion à l’API ===
client = None
try:
    print(f"Tentative de connexion à : {url_api}")
    client = Client(url_api, api_user=user, api_password=password, workspace=workspace)
    print("Connexion réussie.")
    logging.info("Connexion réussie à l'API.")
except Exception as conn_err:
    print(f"Erreur lors de la connexion initiale à l'API : {conn_err}")
    logging.error(f"Erreur de connexion : {conn_err}")
    exit()

# === Création du dossier de téléchargement ===
os.makedirs(download_path, exist_ok=True)

# === Récupération des questionnaires ===
questionnaires = []
df_questionnaires = pd.DataFrame()
try:
    print("Récupération de la liste des questionnaires...")
    q_api = QuestionnairesApi(client)
    for q in q_api.get_list():
        if q.variable and q.variable.strip().lower() == variable_qx.strip().lower() and q.version == 1:
            questionnaires.append({
                "id": q.id,
                "questionnaire_id": q.questionnaire_id,
                "version": q.version,
                "title": q.title,
                "variable": q.variable
            })
except Exception as q_err:
    print(f"Erreur lors de la récupération des questionnaires : {q_err}")
    logging.error(f"Erreur lors de la récupération des questionnaires : {q_err}")
else:
    df_questionnaires = pd.DataFrame(questionnaires)

if df_questionnaires.empty:
    print(f"Aucun questionnaire trouvé pour variable_qx='{variable_qx}' et version=1")
    logging.warning(f"Aucun questionnaire trouvé pour variable_qx='{variable_qx}' et version=1")
else:
    print(f"Questionnaires trouvés : \n{df_questionnaires}")
    logging.info(f"Questionnaires trouvés : {df_questionnaires.to_dict()}")

# === Fonction de téléchargement ===
def download_data(questionnaire_guid, version, q_title):
    versioned_path = os.path.join(download_path, f"{q_title}_V{version}".replace(" ", "_"))
    os.makedirs(versioned_path, exist_ok=True)

    try:
        # Vérification GUID
        try:
            uuid.UUID(questionnaire_guid)
        except ValueError:
            print(f"Erreur interne : {questionnaire_guid} n'est pas un GUID valide.")
            logging.error(f"GUID invalide : {questionnaire_guid}")
            return

        questionnaire_identity = f"{questionnaire_guid}${version}"
        print(f"\n--- Début du téléchargement pour {q_title} (ID: {questionnaire_identity}) ---")
        logging.info(f"Début du téléchargement pour {q_title} (ID: {questionnaire_identity})")

        export_job_params = {
            "QuestionnaireId": questionnaire_identity,
            "ExportType": download_type,
            "InterviewStatus": download_status
        }
        export_job = ExportJob(**export_job_params)
        print(f"Paramètres ExportJob: {export_job.dict(by_alias=True, exclude_none=True)}")
        logging.info(f"Paramètres ExportJob: {export_job.dict(by_alias=True, exclude_none=True)}")

        export_api = ExportApi(client)
        print("Démarrage du job d'exportation...")
        job = export_api.start(export_job=export_job, wait=True, show_progress=True)

        if job and job.has_export_file and job.links and job.links.download:
            print(f"Job d'exportation terminé avec succès (Job ID: {job.job_id}).")
            logging.info(f"Job d'exportation terminé (Job ID: {job.job_id})")
            url = f"https://evaluation.sindevstat.com/primary/api/v2/export/{job.job_id}/file"
            download_url_to_use = url

            print(f"URL de téléchargement utilisée : {download_url_to_use}")
            logging.info(f"URL de téléchargement : {download_url_to_use}")

            # Fallback filename
            output_filename = os.path.join(versioned_path, f"export_job_{job.job_id}.zip")

            try:
                # Use requests.get with Basic Auth
                headers = {
                    'Authorization': f'Basic {base64.b64encode(f"{user}:{password}".encode()).decode()}'
                }
                response = requests.get(download_url_to_use, headers=headers, stream=True)

                # Parse Content-Disposition for filename
                if 'Content-Disposition' in response.headers:
                    filename_match = re.search(r'filename="(.+)"', response.headers['Content-Disposition'])
                    if filename_match:
                        output_filename = os.path.join(versioned_path, filename_match.group(1))
                        logging.info(f"Nom de fichier détecté : {output_filename}")

                if response.status_code == 200:
                    # Check if file already exists
                    if os.path.exists(output_filename):
                        print(f"Fichier déjà existant : {output_filename}. Passer au suivant.")
                        logging.info(f"Fichier déjà existant : {output_filename}")
                        return

                    with open(output_filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"Téléchargement réussi : {output_filename}")
                    logging.info(f"Téléchargement réussi : {output_filename}")

                    # Extraction du fichier Zip
                    try:
                        with ZipFile(output_filename, 'r') as zip_file:
                            print(f"Extraction de {output_filename} vers {versioned_path}...")
                            zip_file.extractall(path=versioned_path)
                        print(f"Extraction réussie.")
                        logging.info(f"Extraction réussie : {output_filename}")
                        # Supprimer le fichier zip
                        os.remove(output_filename)
                        print(f"Fichier zip supprimé : {output_filename}")
                        logging.info(f"Fichier zip supprimé : {output_filename}")
                    except Exception as zip_err:
                        print(f"Erreur lors de l'extraction du fichier zip {output_filename} : {zip_err}")
                        logging.error(f"Erreur d'extraction : {zip_err}")
                else:
                    print(f"Échec du téléchargement pour {q_title} V{version}. Code HTTP : {response.status_code}")
                    print(f"Réponse du serveur : {response.text[:500]}")
                    logging.error(f"Échec du téléchargement. Code HTTP : {response.status_code}, Réponse : {response.text[:500]}")
                    return

            except requests.exceptions.ConnectionError as e:
                print(f"Erreur de Connexion lors de la tentative de téléchargement depuis {download_url_to_use} : {e}")
                print("Vérifiez DNS, pare-feu ou contactez l'admin serveur.")
                logging.error(f"Erreur de connexion : {e}")
            except Exception as download_err:
                print(f"Erreur pendant le téléchargement/extraction pour {q_title} V{version} : {download_err}")
                logging.error(f"Erreur de téléchargement : {download_err}")
                traceback.print_exc()

        else:
            status = job.status if job else "Inconnu"
            print(f"Aucun fichier exporté généré pour {q_title} V{version}. Statut du job : {status}")
            logging.error(f"Aucun fichier exporté. Statut : {status}")
            if job and job.error_message:
                print(f"Message d'erreur du job : {job.error_message}")
                logging.error(f"Message d'erreur du job : {job.error_message}")

    except Exception as e:
        print(f"Erreur inattendue pour {q_title} V{version} : {e}")
        logging.error(f"Erreur inattendue : {e}")
        traceback.print_exc()

# === Lancement du téléchargement ===
if not df_questionnaires.empty:
    print("\n=== Démarrage des téléchargements ===")
    logging.info("Démarrage des téléchargements")
    for _, row in df_questionnaires.drop_duplicates(subset=['questionnaire_id', 'version']).iterrows():
        download_data(row["questionnaire_id"], row["version"], row["title"])
    print("\n=== Tous les téléchargements tentés ===")
    logging.info("Tous les téléchargements tentés")
else:
    print("Aucun questionnaire à télécharger.")
    logging.warning("Aucun questionnaire à télécharger")