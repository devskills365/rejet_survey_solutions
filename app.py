from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
from ssaw import Client, InterviewsApi, WorkspacesApi, ExportApi, QuestionnairesApi
from ssaw.models import ExportJob
from typing import List, Dict, Optional, Tuple
import json
import ssaw.exceptions
from collections import defaultdict
import base64
import requests
import uuid
import logging
import re
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['DOWNLOAD_FOLDER'] = 'Downloads'  # Folder for downloaded files
app.secret_key = '12fgt334jhznbkioup@sF3#Hgdgdhdj'

# Create upload and download folders if they don't exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['DOWNLOAD_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Configure logging
logging.basicConfig(filename='download.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Existing functions (readable_to_server, add_comments_and_reject_from_excel, get_interview_stats)
def readable_to_server(readable_id: str, mapping: List[str]) -> Optional[str]:
    """Convertit un ID lisible en ID serveur si présent dans la liste de correspondance."""
    return readable_id if readable_id in mapping else None

def add_comments_and_reject_from_excel(client: Client, df: pd.DataFrame, mapping: List[str]) -> Tuple[Dict[str, int], List[str]]:
    stats = {'total': 0, 'commented': 0, 'rejected': 0, 'errors': 0}
    results = []
    interviews_to_reject = set()

    required_columns = ['interview__id', 'variable', 'comment']
    if not all(col in df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        results.append(f"Colonnes manquantes dans le fichier Excel : {', '.join(missing)}")
        stats['errors'] = 1
        return stats, results

    stats['total'] = len(df)

    interviews_api = InterviewsApi(client)

    for _, row in df.iterrows():
        readable_id = str(row['interview__id'])
        variable = str(row['variable'])
        comment = str(row['comment'])
        roster_vector = json.loads(row.get('roster_vector', '[]')) if 'roster_vector' in df.columns else []

        try:
            server_id = readable_to_server(readable_id, mapping)
            if not server_id:
                stats['errors'] += 1
                results.append(f"ID non trouvé dans la liste de correspondance : {readable_id}")
                continue

            interviews_api.comment(
                interview_id=server_id,
                variable=variable,
                comment=comment,
                roster_vector=roster_vector if roster_vector else None
            )
            stats['commented'] += 1
            results.append(f"Commentaire ajouté pour l'ID {server_id}, variable {variable}")
            interviews_to_reject.add(server_id)

        except Exception as e:
            stats['errors'] += 1
            results.append(f"Erreur lors du commentaire de l'ID {readable_id}, variable {variable} : {str(e)}")

    for server_id in interviews_to_reject:
        try:
            interviews_api.reject(server_id, 'Rejeté après commentaire')
            stats['rejected'] += 1
            results.append(f"Rejeté : ID serveur ({server_id})")
        except Exception as e:
            stats['errors'] += 1
            results.append(f"Erreur lors du rejet de l'ID {server_id} : {str(e)}")

    return stats, results

def get_interview_stats(client: Client) -> Dict:
    """Récupère les statistiques des interviews (nombre total, statuts, questionnaires)."""
    try:
        interviews_api = InterviewsApi(client)
        interviews = list(interviews_api.get_list(fields=['id', 'status', 'questionnaire_id']))

        total_interviews = len(interviews)
        status_counts = defaultdict(int)
        questionnaire_ids = set()

        for interview in interviews:
            status_counts[interview.status] += 1
            questionnaire_ids.add(interview.questionnaire_id)

        return {
            'total_interviews': total_interviews,
            'status_counts': dict(status_counts),
            'questionnaire_count': len(questionnaire_ids),
            'error': None
        }
    except Exception as e:
        return {
            'total_interviews': 0,
            'status_counts': {},
            'questionnaire_count': 0,
            'error': str(e)
        }

@app.route('/save_api_info', methods=['POST'])
def save_api_info():
    """Enregistre les informations de connexion à l'API dans la session après validation."""
    required_fields = ['api_user', 'utilisateur', 'mot_de_passe', 'workspace']
    form_data = {field: request.form.get(field) for field in required_fields}

    for field, value in form_data.items():
        if not value:
            flash(f"Le champ {field} est requis", 'error')
            return redirect(url_for('reject_and_comment'))

    try:
        client = Client(
            url=form_data['api_user'],
            api_user=form_data['utilisateur'],
            api_password=form_data['mot_de_passe'],
            workspace=form_data['workspace']
        )

        workspaces_api = WorkspacesApi(client)
        workspaces = workspaces_api.get_list()
        workspace_names = [ws.name for ws in workspaces]

        if form_data['workspace'] not in workspace_names:
            flash(f"Le workspace '{form_data['workspace']}' n'existe pas. Workspaces disponibles : {', '.join(workspace_names)}", 'error')
            return redirect(url_for('reject_and_comment'))

        session['api_info'] = form_data
        session.modified = True
        flash("Connexion au serveur Survey Solutions réussie ! Informations API enregistrées.", 'success')
        return redirect(url_for('reject_and_comment'))

    except ssaw.exceptions.SsawException as e:
        flash(f"Erreur de connexion : Identifiants incorrects ou serveur inaccessible ({str(e)})", 'error')
        return redirect(url_for('reject_and_comment'))
    except Exception as e:
        flash(f"Erreur inattendue lors de la connexion : {str(e)}", 'error')
        return redirect(url_for('reject_and_comment'))

@app.route('/download', methods=['POST'])
def download_data():
    """Handle the download request for Survey Solutions data and send the file to the browser."""
    if 'api_info' not in session:
        flash("Veuillez d'abord enregistrer les informations API", 'error')
        return redirect(url_for('reject_and_comment'))

    api_info = session['api_info']
    try:
        # Initialize client with session credentials
        client = Client(
            url=api_info['api_user'],
            api_user=api_info['utilisateur'],
            api_password=api_info['mot_de_passe'],
            workspace=api_info['workspace']
        )

        # Parameters from download.py
        variable_qx = 'Menage_VF2_ENA2024'
        download_type = 'STATA'
        download_status = 'All'

        # Get questionnaires
        questionnaires = []
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
        df_questionnaires = pd.DataFrame(questionnaires)

        if df_questionnaires.empty:
            flash(f"Aucun questionnaire trouvé pour variable_qx='{variable_qx}' et version=1", 'error')
            return redirect(url_for('reject_and_comment'))

        # Process the first questionnaire
        row = df_questionnaires.iloc[0]
        questionnaire_guid = row['questionnaire_id']
        version = row['version']
        q_title = row['title']

        # Validate GUID
        uuid.UUID(questionnaire_guid)
        questionnaire_identity = f"{questionnaire_guid}${version}"
        logging.info(f"Début du téléchargement pour {q_title} (ID: {questionnaire_identity})")

        # Create export job
        export_job_params = {
            "QuestionnaireId": questionnaire_identity,
            "ExportType": download_type,
            "InterviewStatus": download_status
        }
        export_job = ExportJob(**export_job_params)
        export_api = ExportApi(client)
        job = export_api.start(export_job=export_job, wait=True, show_progress=True)

        if not (job and job.has_export_file and job.links and job.links.download):
            status = job.status if job else "Inconnu"
            flash(f"Aucun fichier exporté généré pour {q_title} V{version}. Statut : {status}", 'error')
            logging.error(f"Aucun fichier exporté. Statut : {status}")
            return redirect(url_for('reject_and_comment'))

        # Download the file
        url = f"https://evaluation.sindevstat.com/primary/api/v2/export/{job.job_id}/file"
        download_name = f"Menage_VF2_ENA2024_1_STATA_All.zip"

        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{api_info["utilisateur"]}:{api_info["mot_de_passe"]}".encode()).decode()}'
        }
        response = requests.get(url, headers=headers, stream=True)

        # Parse Content-Disposition for filename
        if 'Content-Disposition' in response.headers:
            filename_match = re.search(r'filename="(.+)"', response.headers['Content-Disposition'])
            if filename_match:
                download_name = filename_match.group(1)
                logging.info(f"Nom de fichier détecté : {download_name}")

        if response.status_code != 200:
            flash(f"Échec du téléchargement pour {q_title} V{version}. Code HTTP : {response.status_code}", 'error')
            logging.error(f"Échec du téléchargement. Code HTTP : {response.status_code}, Réponse : {response.text[:500]}")
            return redirect(url_for('reject_and_comment'))

        # Save the file to a temporary NamedTemporaryFile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            temp_file_path = temp_file.name
            logging.info(f"Téléchargement réussi : {temp_file_path}")

        # Send the file to the browser
        try:
            return send_file(
                temp_file_path,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/zip'
            )
        finally:
            # Ensure the file is deleted after sending
            try:
                os.unlink(temp_file_path)
                logging.info(f"Fichier temporaire supprimé : {temp_file_path}")
            except Exception as e:
                logging.error(f"Erreur lors de la suppression du fichier temporaire {temp_file_path} : {e}")

    except Exception as e:
        flash(f"Erreur lors du téléchargement : {str(e)}", 'error')
        logging.error(f"Erreur lors du téléchargement : {e}")
        return redirect(url_for('reject_and_comment'))

@app.route('/', methods=['GET', 'POST'])
def reject_and_comment():
    """Traite un fichier Excel pour commenter les variables et rejeter les interviews."""
    stats = {'total': 0, 'commented': 0, 'rejected': 0, 'errors': 0}
    interview_stats = None

    if 'api_info' in session:
        try:
            api_info = session['api_info']
            client = Client(
                url=api_info['api_user'],
                api_user=api_info['utilisateur'],
                api_password=api_info['mot_de_passe'],
                workspace=api_info['workspace']
            )
            interview_stats = get_interview_stats(client)
            if interview_stats['error']:
                flash(f"Erreur lors de la récupération des statistiques : {interview_stats['error']}", 'error')
            else:
                flash("Statistiques des interviews chargées avec succès.", 'success')
        except Exception as e:
            flash(f"Erreur lors de la récupération des statistiques : {str(e)}", 'error')
            interview_stats = {'total_interviews': 0, 'status_counts': {}, 'questionnaire_count': 0, 'error': str(e)}

    if request.method == 'POST' and 'excel_file' in request.files:
        if 'api_info' not in session:
            flash("Veuillez d'abord enregistrer les informations API", 'error')
            return redirect(url_for('reject_and_comment'))

        file = request.files['excel_file']

        if file.filename == '':
            flash("Aucun fichier sélectionné", 'error')
            return redirect(url_for('reject_and_comment'))

        if file and file.filename.endswith('.xlsx'):
            try:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                df = pd.read_excel(file_path)

                api_info = session['api_info']
                client = Client(
                    url=api_info['api_user'],
                    api_user=api_info['utilisateur'],
                    api_password=api_info['mot_de_passe'],
                    workspace=api_info['workspace']
                )

                workspaces_api = WorkspacesApi(client)
                workspaces_api.get_list()

                interviews_api = InterviewsApi(client)
                id_mapping = [interview.id for interview in interviews_api.get_list(fields=['id'])]

                comment_stats, results = add_comments_and_reject_from_excel(client, df, id_mapping)
                stats.update(comment_stats)

                flash('\n'.join(results), 'success')

                os.remove(file_path)

                interview_stats = get_interview_stats(client)
                if interview_stats['error']:
                    flash(f"Erreur lors de la mise à jour des statistiques : {interview_stats['error']}", 'error')

            except ssaw.exceptions.SsawException as e:
                flash(f"Erreur lors du traitement : Connexion au serveur échouée ({str(e)})", 'error')
            except Exception as e:
                flash(f"Erreur lors du traitement : {str(e)}", 'error')

        else:
            flash("Veuillez sélectionner un fichier Excel (.xlsx)", 'error')

    return render_template('index.html', stats=stats, interview_stats=interview_stats)

if __name__ == '__main__':
    app.run(debug=True)