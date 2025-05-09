from flask import Flask, render_template, request, flash, redirect, url_for, session, send_file, Response, jsonify
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
app.config['DOWNLOAD_FOLDER'] = 'Downloads'
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
        membres_menage__id = int(row['membres_menage__id']) if pd.notna(row.get('membres_menage__id')) else None
        roster_vector = json.loads(row.get('roster_vector', '[]')) if 'roster_vector' in df.columns else []

        try:
            server_id = readable_to_server(readable_id, mapping)
            if not server_id:
                stats['errors'] += 1
                results.append(f"ID non trouvé dans la liste de correspondance : {readable_id}")
                continue

            roster_name = 'membres_menage'
            is_roster_variable = variable in ['s3q02', 's3q03', 'A6_Age_Indiv', 'A7_sexe', 'A10_Lien_CM']

            if is_roster_variable and membres_menage__id is not None:
                if membres_menage__id <= 0:
                    stats['errors'] += 1
                    results.append(f"membres_menage__id {membres_menage__id} invalide pour ID {readable_id}, variable {variable}")
                    continue
                roster_vector = [membres_menage__id - 1]
                logging.info(f"Commentaire pour ID {readable_id}, variable {variable}, membres_menage__id {membres_menage__id}, roster_vector {roster_vector}")
            else:
                roster_vector = None
                logging.info(f"Commentaire pour ID {readable_id}, variable {variable}, hors roster")

            interviews_api.comment(
                interview_id=server_id,
                variable=variable,
                comment=comment,
                roster_vector=roster_vector
            )
            stats['commented'] += 1
            results.append(f"Commentaire ajouté pour l'ID {server_id}, variable {variable}, membre {membres_menage__id or 'N/A'}")
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

@app.route('/api_config', methods=['GET', 'POST'])
def api_config():
    """Gère la configuration des informations API."""
    if request.method == 'POST':
        required_fields = ['api_user', 'utilisateur', 'mot_de_passe', 'workspace']
        form_data = {field: request.form.get(field, '').strip() for field in required_fields}

        # Vérifier les champs vides
        for field, value in form_data.items():
            if not value:
                flash(f"Le champ '{field}' est requis.", 'error')
                return render_template('api_config.html', form_data=form_data)

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
                return render_template('api_config.html', form_data=form_data)

            session['api_info'] = form_data
            session.modified = True
            flash("Connexion au serveur Survey Solutions réussie ! Informations API enregistrées.", 'success')
            return redirect(url_for('reject_and_comment'))

        except ssaw.exceptions.UnauthorizedError:
            flash("Erreur de connexion : Nom d'utilisateur ou mot de passe incorrect. Veuillez vérifier vos identifiants.", 'error')
            return render_template('api_config.html', form_data=form_data)
        except ssaw.exceptions.ForbiddenError:
            flash("Erreur : Accès interdit. Vérifiez que l'utilisateur a les autorisations nécessaires pour le workspace spécifié.", 'error')
            return render_template('api_config.html', form_data=form_data)
        except Exception as e:
            flash(f"Erreur inattendue : {str(e)}. Veuillez réessayer.", 'error')
            return render_template('api_config.html', form_data=form_data)

    # GET request: afficher le formulaire avec les données de session si disponibles
    form_data = session.get('api_info', {})
    return render_template('api_config.html', form_data=form_data)

@app.route('/download', methods=['POST'])
def download_data():
    """Handle the download request for Survey Solutions data and send the file to the browser."""
    if 'api_info' not in session:
        flash("Veuillez configurer les informations API.", 'error')
        return redirect(url_for('api_config'))

    api_info = session['api_info']
    try:
        client = Client(
            url=api_info['api_user'],
            api_user=api_info['utilisateur'],
            api_password=api_info['mot_de_passe'],
            workspace=api_info['workspace']
        )

        # Récupérer le format d'exportation et le statut des interviews
        export_type = request.form.get('export_type')
        interview_status = request.form.get('interview_status')
        valid_export_types = ['Tabular', 'STATA', 'SPSS', 'Binary', 'DDI', 'Paradata']
        valid_interview_statuses = [
            'All', 'SupervisorAssigned', 'InterviewerAssigned', 'Completed',
            'RejectedBySupervisor', 'ApprovedBySupervisor', 'RejectedByHeadquarters', 'ApprovedByHeadquarters'
        ]

        if export_type not in valid_export_types:
            flash("Format d'exportation invalide. Veuillez choisir un format valide.", 'error')
            return redirect(url_for('reject_and_comment'))

        if interview_status not in valid_interview_statuses:
            flash("Statut des interviews invalide. Veuillez choisir un statut valide.", 'error')
            return redirect(url_for('reject_and_comment'))

        variable_qx = 'Menage_VF2_ENA2024'

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

        row = df_questionnaires.iloc[0]
        questionnaire_guid = row['questionnaire_id']
        version = row['version']
        q_title = row['title']

        uuid.UUID(questionnaire_guid)
        questionnaire_identity = f"{questionnaire_guid}${version}"
        logging.info(f"Début du téléchargement pour {q_title} (ID: {questionnaire_identity}, Format: {export_type}, Statut: {interview_status})")

        # Create export job
        export_job_params = {
            "QuestionnaireId": questionnaire_identity,
            "ExportType": export_type,
            "InterviewStatus": interview_status
        }
        export_job = ExportJob(**export_job_params)
        export_api = ExportApi(client)
        job = export_api.start(export_job=export_job, wait=True, show_progress=True)

        # Stocker l'ID du job dans la session
        session['export_job_id'] = job.job_id
        session.modified = True

        if not (job and job.has_export_file and job.links and job.links.download):
            status = job.status if job else "Inconnu"
            flash(f"Aucun fichier exporté généré pour {q_title} V{version}. Statut : {status}", 'error')
            logging.error(f"Aucun fichier exporté. Statut : {status}")
            # Supprimer l'ID du job de la session
            session.pop('export_job_id', None)
            session.modified = True
            return redirect(url_for('reject_and_comment'))

        # Download the file
        url = f"https://evaluation.sindevstat.com/primary/api/v2/export/{job.job_id}/file"
        # Ajuster le nom du fichier en fonction du format
        extension_map = {
            'STATA': '.dta.zip',
            'SPSS': '.sav.zip',
            'Tabular': '.csv.zip',
            'Binary': '.zip',
            'DDI': '.xml.zip',
            'Paradata': '.zip'
        }
        download_name = f"Menage_VF2_ENA2024_1_{export_type}_{interview_status}{extension_map.get(export_type, '.zip')}"

        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{api_info["utilisateur"]}:{api_info["mot_de_passe"]}".encode()).decode()}'
        }
        response = requests.get(url, headers=headers, stream=True)

        if 'Content-Disposition' in response.headers:
            filename_match = re.search(r'filename="(.+)"', response.headers['Content-Disposition'])
            if filename_match:
                download_name = filename_match.group(1)
                logging.info(f"Nom de fichier détecté : {download_name}")

        if response.status_code != 200:
            flash(f"Échec du téléchargement pour {q_title} V{version}. Code HTTP : {response.status_code}", 'error')
            logging.error(f"Échec du téléchargement. Code HTTP : {response.status_code}, Réponse : {response.text[:500]}")
            # Supprimer l'ID du job de la session
            session.pop('export_job_id', None)
            session.modified = True
            return redirect(url_for('reject_and_comment'))

        # Save the file to a temporary NamedTemporaryFile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            temp_file_path = temp_file.name
            logging.info(f"Téléchargement réussi : {temp_file_path}")

        try:
            # Envoyer le fichier
            response = send_file(
                temp_file_path,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/zip'
            )
            # Ajouter un message flash pour confirmer le succès
            flash(f"Téléchargement réussi : {download_name}", 'success')
            # Supprimer l'ID du job de la session après succès
            session.pop('export_job_id', None)
            session.modified = True
            return response
        finally:
            try:
                os.unlink(temp_file_path)
                logging.info(f"Fichier temporaire supprimé : {temp_file_path}")
            except Exception as e:
                logging.error(f"Erreur lors de la suppression du fichier temporaire {temp_file_path} : {e}")

    except ssaw.exceptions.UnauthorizedError:
        flash("Erreur lors du téléchargement : Identifiants API invalides. Veuillez reconfigurer les informations API.", 'error')
        logging.error("Erreur d'authentification lors du téléchargement")
        session.pop('export_job_id', None)
        session.modified = True
        return redirect(url_for('api_config'))
    except ssaw.exceptions.ForbiddenError:
        flash("Erreur lors du téléchargement : Accès interdit au workspace. Vérifiez les autorisations.", 'error')
        logging.error("Erreur de permission lors du téléchargement")
        session.pop('export_job_id', None)
        session.modified = True
        return redirect(url_for('api_config'))
    except Exception as e:
        flash(f"Erreur lors du téléchargement : {str(e)}", 'error')
        logging.error(f"Erreur lors du téléchargement : {e}")
        session.pop('export_job_id', None)
        session.modified = True
        return redirect(url_for('reject_and_comment'))

@app.route('/cancel_export', methods=['POST'])
def cancel_export():
    """Cancel an ongoing export job."""
    if 'api_info' not in session or 'export_job_id' not in session:
        return jsonify({'success': False, 'message': 'Aucun job d\'exportation en cours.'})

    api_info = session['api_info']
    job_id = session['export_job_id']

    try:
        client = Client(
            url=api_info['api_user'],
            api_user=api_info['utilisateur'],
            api_password=api_info['mot_de_passe'],
            workspace=api_info['workspace']
        )
        export_api = ExportApi(client)
        export_api.cancel(job_id)
        logging.info(f"Job d'exportation {job_id} annulé avec succès")
        
        # Supprimer l'ID du job de la session
        session.pop('export_job_id', None)
        session.modified = True
        return jsonify({'success': True, 'message': 'Job d\'exportation annulé avec succès.'})
    except ssaw.exceptions.UnauthorizedError:
        logging.error("Erreur d'authentification lors de l'annulation du job")
        return jsonify({'success': False, 'message': 'Identifiants API invalides.'})
    except ssaw.exceptions.ForbiddenError:
        logging.error("Erreur de permission lors de l'annulation du job")
        return jsonify({'success': False, 'message': 'Accès interdit au workspace.'})
    except Exception as e:
        logging.error(f"Erreur lors de l'annulation du job {job_id} : {str(e)}")
        return jsonify({'success': False, 'message': f"Erreur lors de l'annulation : {str(e)}"})

@app.route('/', methods=['GET', 'POST'])
def reject_and_comment():
    """Traite un fichier Excel pour commenter les variables et rejeter les interviews."""
    if 'api_info' not in session:
        flash("Veuillez configurer les informations API.", 'error')
        return redirect(url_for('api_config'))

    stats = {'total': 0, 'commented': 0, 'rejected': 0, 'errors': 0}
    interview_stats = None

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
    except ssaw.exceptions.UnauthorizedError:
        flash("Erreur : Identifiants API invalides. Veuillez reconfigurer les informations API.", 'error')
        return redirect(url_for('api_config'))
    except ssaw.exceptions.ForbiddenError:
        flash("Erreur : Accès interdit au workspace. Vérifiez les autorisations de l'utilisateur.", 'error')
        return redirect(url_for('api_config'))
    except Exception as e:
        flash(f"Erreur lors de la récupération des statistiques : {str(e)}", 'error')
        interview_stats = {'total_interviews': 0, 'status_counts': {}, 'questionnaire_count': 0, 'error': str(e)}

    if request.method == 'POST' and 'excel_file' in request.files:
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

            except ssaw.exceptions.UnauthorizedError:
                flash("Erreur lors du traitement : Identifiants API invalides. Veuillez reconfigurer les informations API.", 'error')
                return redirect(url_for('api_config'))
            except ssaw.exceptions.ForbiddenError:
                flash("Erreur lors du traitement : Accès interdit au workspace. Vérifiez les autorisations.", 'error')
                return redirect(url_for('api_config'))
            except Exception as e:
                flash(f"Erreur lors du traitement : {str(e)}", 'error')

        else:
            flash("Veuillez sélectionner un fichier Excel (.xlsx)", 'error')

    return render_template('index.html', stats=stats, interview_stats=interview_stats)

if __name__ == '__main__':
    print("Démarrage de l'application Flask sur le port 5003...")
    app.run(debug=True, port=5003)