import sys
import os
efs_mount_path = '/mnt/efs/'
sys.path.append(efs_mount_path)
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import requests
from openai import OpenAI
from pdfminer.high_level import extract_text
import io
import concurrent.futures
import psycopg2

DB_HOST=os.getenv("DB_HOST")
DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")
DB_DATABASE=os.getenv("DB_DATABASE")
DB_PORT=os.getenv("DB_PORT")
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
#CONSULTAS
consulta_postEsp = """
SELECT 
    tp.id AS postulation_id,
    tp.registration_date,
    tp.evaluation_date,
    tps.first_name AS specialist_first_name,
    tps.last_name AS specialist_last_name,
    tps.email AS specialist_email,
    tpp.id_years_experience AS years_experience,
    tpp.profession,
    tpp.salary AS salary,
    tpp.cost_hour AS cost_hour,
    tpp.professional_summary,
    tpp.cv_url AS cv_url,
    tpo.id AS opportunity_id,
    tpo.position AS opportunity_position,
    tpo.code_opportunity AS opportunity_code,
    tpsp.value AS postulation_status
FROM 
    tb_postulation tp
LEFT JOIN 
    tb_specialist tps ON tp.id_specialist = tps.id
LEFT JOIN 
    tb_professional_profile tpp ON tps.id = tpp.id
LEFT JOIN 
    tb_opportunity tpo ON tp.id_opportunity = tpo.id
LEFT JOIN 
    tc_postulation_status tpsp ON tp.id_postulation_status = tpsp.id
WHERE 
    tpo.id = %s
    """
consulta_oport = """
SELECT 
    tpo.id AS opportunity_id,
    tpo.code_opportunity AS opportunity_code,
    tpo.position AS position_name,
    tpo.area_account,
    tpo.nro_vacancies,
    tpo.tentative_entry_date,
    tpo.age,
    tpo.main_functions,
    tpo.variable_compensation,
    tpo.lower_salary,
    tpo.max_salary,
    tpo.hide_salary,
    tpo.status,
    tpo.publication_date,
    tpo.proposal_deadline,
    tpo.sent_massively,
    tco.value AS opportunity_type,
    tcp.value AS profile_value,
    tci.name AS company_name,
    tcs.value AS status_process,
    tcm.value AS work_modality
FROM 
    tb_opportunity tpo
LEFT JOIN 
    tc_opportunity tco ON tpo.id_type_opportunity = tco.id
LEFT JOIN 
    tc_profile tcp ON tpo.id_profile = tcp.id
LEFT JOIN 
    tb_company tci ON tpo.id_company = tci.id
LEFT JOIN 
    tc_quote_status tcs ON tpo.id_status_process = tcs.id
LEFT JOIN 
    tc_work_modality tcm ON tpo.id_work_modality = tcm.id
WHERE 
    tpo.id = %s
    """

col_postEsp = ['postulation_id', 'registration_date','evaluation_date','specialist_first_name','specialist_last_name', 'specialist_email','years_experience','profession','salary','cost_hour','professional_summary','cv_url','opportunity_id','opportunity_position','opportunity_code','postulation_status']
col_oport = ['opportunity_id', 'opportunity_code','position_name','area_account', 'nro_vacancies', 'tentative_entry_date','age','main_functions','variable_compensation','lower_salary','max_salary','hide_salary','status','publication_date','proposal_deadline','sent_massively','opportunity_type','profile_value','company_name','status_process','work_modality']

def query(consulta, col, id_=None, id_1=None):
    # Conectar a la base de datos PostgreSQL
    db_connection = psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        port=DB_PORT
    )
    
    cursor = db_connection.cursor()    
    params = []
    
    # Si hay parámetros para la consulta, se agregan
    if id_ is not None:
        params.append(id_)
    if id_1 is not None:
        params.append(id_1)
    
    # Ejecutar la consulta SQL con parámetros si es necesario
    cursor.execute(consulta, params)
    # Obtener los resultados de la consulta
    resultados = cursor.fetchall()
    # Convertir los resultados a un DataFrame de pandas
    df = pd.DataFrame(resultados, columns=col)
    # Cerrar el cursor y la conexión
    cursor.close()
    db_connection.close()
    return df

def combine_row_text(df):
    def convert_to_string(value):
        if isinstance(value, list):
            return ' '.join(map(str, value))
        return str(value)
    
    return df.apply(lambda row: ' '.join(convert_to_string(value) for value in row.values), axis=1)

def similitud(df_req,df_cot):
    req_texts = combine_row_text(df_req)
    cot_texts = combine_row_text(df_cot)
    vectorizer = TfidfVectorizer()
    req_vectors = vectorizer.fit_transform(req_texts)
    cot_vectors = vectorizer.transform(cot_texts)
    similarity_matrix = cosine_similarity(req_vectors, cot_vectors)
    similarity_df = pd.DataFrame(similarity_matrix, index=df_req.index, columns=df_cot.index)
    return similarity_df

def process_row(row):
    
    # Extraer la URL del CV
    variable = row['cv_url']
    response = requests.get(variable)
    pdf_content = io.BytesIO(response.content)

    # Extraer el texto del PDF
    text = extract_text(pdf_content)
    print("Texto extraído del PDF:", text)

    # Convertir el texto en un array (lista) de líneas
    text_array_list = text.splitlines()
    text_array = ' '.join(filter(lambda x: x != '', text_array_list))

    # Llamar a la API de OpenAI
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
#                     "puedes poner en una JSON para python (si no hay respuesta poner el numero 0 y que la respuesta sea limpio en un JSON sin comentarios): "
#                     "nombre, profesion, proyectos,  cantidad de proyectos (solo numero entero), cantidad de lugares en que trabajo(solo numero entero), "
#                     "cantidad de experiencia (solo numero entero), skill tecnico, skill tecnico (solo numero entero),  skill de gestion, cantidad de eduacion postgrado(solo numero entero), "
#                     "anos de experiencia (solo numero entero) y cantidad de educacion (solo numero entero) "
#                     "con las siguientes claves para JSON "
#                     "['nombre', 'profesion', 'proyectos', 'cantidad_proyectos', 'cantidad_lugares_trabajo', 'cantidad_experiencia', 'skill_tecnico', 'skill_tecnico_numerico', 'skill_gestion', 'cantidad_educacion_postgrado', 'anos_experiencia', 'cantidad_educacion']"
                   ######
"""                   Extrae la siguiente información del CV y devuélvela en un formato JSON. Si algún dato no está disponible, usa el valor 0. Asegúrate de que el JSON esté limpio, sin comentarios, y sigue el formato exacto de las claves que se proporcionan.

Información a extraer:
- nombre: El nombre completo de la persona.
- profesion: La profesión actual o más reciente de la persona.
- proyectos: Lista de los principales proyectos mencionados en el CV.
- cantidad_proyectos: El número total de proyectos mencionados en el CV (solo número entero).
- cantidad_lugares_trabajo: El número total de lugares en los que la persona ha trabajado (solo número entero).
- cantidad_experiencia: La cantidad total de experiencia laboral en años (solo número entero).
- skill_tecnico: Habilidades técnicas mencionadas.
- skill_tecnico_numerico: Un valor numérico asociado con las habilidades técnicas (solo número entero).
- skill_gestion: Habilidades de gestión mencionadas.
- cantidad_educacion_postgrado: El número total de títulos o certificaciones de postgrado mencionados (solo número entero).
- anos_experiencia: El número total de años de experiencia laboral (solo número entero).
- cantidad_educacion: El número total de títulos o certificaciones educativas mencionadas (solo número entero).

Devuelve el resultado en el siguiente formato JSON:
{
  "nombre": "Nombre completo aquí",
  "profesion": "Profesión aquí",
  "proyectos": ["Proyecto 1", "Proyecto 2", ...],
  "cantidad_proyectos": Número entero,
  "cantidad_lugares_trabajo": Número entero,
  "cantidad_experiencia": Número entero,
  "skill_tecnico": "Habilidades técnicas aquí",
  "skill_tecnico_numerico": Número entero,
  "skill_gestion": "Habilidades de gestión aquí",
  "cantidad_educacion_postgrado": Número entero,
  "anos_experiencia": Número entero,
  "cantidad_educacion": Número entero
} Texto del CV: """
                   ###### 
                    + str(text_array)
                ),
            }
        ],
        temperature=0.0,
        top_p=0.1,
        max_tokens=700,
    )
    return completion.choices[0].message.content




def lambda_handler(event, context):
    ID = event["id"]
    #cv = query(consulta_cv, columnas_cv, id)
    postEsp = query(consulta_postEsp, col_postEsp, id_=ID, id_1=None)
    oport = query(consulta_oport, col_oport, id_=ID, id_1=None)

    # Establecer el número de hilos
    NUM_THREADS = 5
    i = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
    #print(i)
        futures = {executor.submit(process_row, row): index for index, row in postEsp.iterrows()}
        results = [(futures[future], future.result()) for future in concurrent.futures.as_completed(futures)]

    results.sort(key=lambda x: x[0])
    data_dicts = [json.loads(result) for index, result in results]

    df = pd.DataFrame(data_dicts)
    cv_final = pd.concat([postEsp, df], axis=1)
    del cv_final["cv_url"]

    sim_general = similitud(oport, cv_final)
    df_final = pd.concat([cv_final[['specialist_first_name', 'specialist_last_name']], sim_general.T], axis=1).rename(columns={'specialist_first_name':'Nombre','specialist_last_name':'Apellido' ,0: 'sim_general'})
    df = df_final.to_json()

    return {
            'result': df
        }