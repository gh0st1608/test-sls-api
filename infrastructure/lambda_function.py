import sys
import os
efs_mount_path = '/mnt/efs/'
sys.path.append(efs_mount_path)
import json
import numpy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
import requests
from openai import OpenAI
from pdfminer.high_level import extract_text
import mysql.connector
import time
import io
import concurrent.futures
import re
import psycopg2

host=os.getenv("DB_HOST")
user=os.getenv("DB_USER")
password=os.getenv("DB_PASSWORD")
database=os.getenv("DB_DATABASE")


consulta_requerimiento = """
SELECT 
    r.objetivo_requerimiento, 
    r.nombre_requerimiento, 
    pe.descripcion AS descripcion_perfil_especialista,
    e.descripcion AS descripcion_estado,
    GROUP_CONCAT(t.nombre_tecnologia SEPARATOR ', ') AS nombre_tecnologia,
    tr.descripcion AS descripcion_tipo_requerimiento,
    p.descripcion AS descripcion_prioridad,
    r.alcance_requerimiento
FROM 
    requerimiento r
LEFT JOIN 
    perfil_especialista pe ON r.id_perfil_especialista = pe.id_perfil_especialista
LEFT JOIN 
    estado e ON r.id_estado = e.id_estado
LEFT JOIN 
    tecnologias t ON r.id_requerimiento = t.id_requerimiento
LEFT JOIN 
    tipo_requerimiento tr ON r.id_tipo_requerimiento = tr.id_tipo_requerimiento
LEFT JOIN 
    prioridad p ON r.id_prioridad = p.id_prioridad
WHERE 
    r.id_requerimiento = %s
GROUP BY 
    r.objetivo_requerimiento, 
    r.nombre_requerimiento, 
    pe.descripcion,
    e.descripcion,
    r.alcance_requerimiento,
    tr.descripcion,
    p.descripcion;
"""
consulta_cv = """
SELECT e.id_especialista,e.nombre,e.url_cv
FROM especialista e
JOIN requerimiento_especialista re ON e.id_especialista = re.id_especialista
JOIN requerimiento r ON re.id_requerimiento = r.id_requerimiento
WHERE r.id_requerimiento = %s; 
"""

consulta_cotizacion = """
SELECT 
    re.id_especialista,
    e.disponibilidad AS disponibilidad_especialista,
    MAX(re.dias_tiempo_ejecucion) AS dias_tiempo_ejecucion,
    MAX(re.precio_rango_1) AS precio_rango_1, 
    MAX(re.precio_rango_2) AS precio_rango_2,
    MAX(tm.descripcion) AS descripcion_tipo_moneda,
    GROUP_CONCAT(DISTINCT re.tecnologias_propuestas ORDER BY re.tecnologias_propuestas SEPARATOR '<br>') AS tecnologias_propuestas,
    GROUP_CONCAT(DISTINCT re.consideraciones ORDER BY re.consideraciones SEPARATOR '<br>') AS consideraciones,
    GROUP_CONCAT(DISTINCT re.alcance_servicio ORDER BY re.alcance_servicio SEPARATOR '<br>') AS alcance_servicio,
    GROUP_CONCAT(DISTINCT re.entregables ORDER BY re.entregables SEPARATOR '<br>') AS entregables,
    GROUP_CONCAT(DISTINCT re.fuera_alcance_servicio ORDER BY re.fuera_alcance_servicio SEPARATOR '<br>') AS fuera_alcance_servicio
FROM 
    requerimiento_especialista re
JOIN 
    tipo_moneda tm ON re.id_tipo_moneda = tm.id_tipo_moneda
JOIN
    especialista e ON re.id_especialista = e.id_especialista
WHERE 
    re.id_requerimiento = %s AND re.id_especialista = %s
GROUP BY 
    re.id_especialista;
"""


# COLUMNAS
columnas_requerimiento = ['objetivo_requerimiento','nombre_requerimiento','descripcion_perfil_especialista', 
    'descripcion_estado','nombre_tecnologias','descripcion_tipo_requerimiento',
    'descripcion_prioridad' , 'detalle_alcance_requerimiento']
columnas_cv = ['id_especialista', 'nombre', 'url_cv']
columnas_cotizacion = [
"id_especialista",
"disponibilidad",
"dias_tiempo_ejecucion",
"precio_rango_1",
"precio_rango_2",
"descripcion_tipo_moneda",
"tecnologias_propuestas",
"consideraciones",
"alcance_servicio",
"entregables",
"fuera_alcance_servicio",
]

def query(consulta, col, id_=None, id_1=None):
    db_connection = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        auth_plugin='mysql_native_password'
    )
    
    cursor = db_connection.cursor()    
    params = []
    if id_ is not None:
        params.append(id_)
    if id_1 is not None:
        params.append(id_1)    
    cursor.execute(consulta, params)
    resultados = cursor.fetchall()   
    df = pd.DataFrame(resultados, columns=col)    
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

def remove_html_tags(text):
    # Verificar si el texto no es nulo
    if pd.isna(text):
        return text
    # Eliminar cualquier contenido entre '<' y '>'
    while '<' in text and '>' in text:
        start = text.find('<')
        end = text.find('>', start)
        if start != -1 and end != -1:
            text = text[:start] + text[end+1:]
        else:
            break
    return text

def convertir_precio(row):
    # Verificar si hay dos precios para promediar
    if pd.notna(row['precio_rango_1']) and pd.notna(row['precio_rango_2']):
        precio = (row['precio_rango_1'] + row['precio_rango_2']) / 2
    elif pd.notna(row['precio_rango_1']):
        precio = row['precio_rango_1']
    else:
        precio = row['precio_rango_2']
    
    # Convertir de USD a PEN si es necesario
    if row['descripcion_tipo_moneda'] == 'USD':
        precio *= 3.7
        flag_conversion = 'D'
    else:
        flag_conversion = 'S'
    
    # Devolver el resultado como una cadena formateada
    return pd.Series([round(precio, 2), flag_conversion])

def remove_json_comments(json_string):
    lines = json_string.splitlines()
    cleaned_lines = []
    for line in lines:
        # Remover comentarios que comienzan con //
        if '//' in line:
            line = line.split('//')[0].strip()
        # Remover espacios en blanco adicionales
        if line.strip():
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def limpiar_texto(texto):
    # Convertir a minúsculas
    #texto = texto.lower()
    if isinstance(texto, str):
        texto = texto.lower()
    else:
        texto = str(texto).lower()

    texto = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\s\n\-\.:,()]', '', texto)
    ###
    texto = re.sub(r'(?<=\))([^\s])', r' \1', texto)
    texto = re.sub(r'(?<=\.)([^\s])', r' \1', texto)
    texto = re.sub(r'(?<=:)([^\s])', r' \1', texto)
    texto = re.sub(r'([a-z])(?=[A-Z])', r'\1 ', texto)
    texto = re.sub(r'(?<=\.\s)([A-Z])', r'\n\n\1', texto)
    texto = texto.replace("nbsp", "")
    ###

    stop_words = {'el', 'la', 'los', 'las', 'de', 'y', 'a', 'en', 'que', 'un', 'una', 'por', 'con', 'para', 'es', 'del',
                      'al', 'entre', 'desde', 'sin', 'sobre', 'tras', 'hacia', 'o', 'ni', 'pero', 'yo', 'tú', 'él', 'ella',
                      'nosotros', 'vosotros', 'ellos', 'mi', 'tu', 'su', 'nuestro', 'vuestro', 'haber', 'ser', 'estar',
                      'tener', 'hacer', 'ir', 'poder', 'muy', 'más', 'menos', 'ya', 'aún', 'todavía', 'siempre', 'nunca',
                      'también', 'tampoco', 'lo', 'me', 'te', 'se', 'nos', 'le', 'les',
                 }
    # Eliminar stopwords
    texto_limpio = ' '.join([word for word in texto.split() if word not in stop_words])
    
    return texto_limpio
    
def process_row(row):
    # Extraer la URL del CV
    variable = row['url_cv']
    response = requests.get(variable)
    pdf_content = io.BytesIO(response.content)
    # Extraer el texto del PDF
    text = extract_text(pdf_content)
    text_array_list = text.splitlines()
    text_array = ' '.join(filter(lambda x: x != '', text_array_list))
    # Llamar a la API de OpenAI
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": (
                    """                   Extrae la siguiente información del CV y devuélvela en un formato JSON. Si algún dato no está disponible, usa el valor 0. Asegúrate de que el JSON esté limpio, sin comentarios, y sigue el formato exacto de las claves que se proporcionan.

Información a extraer:
- nombre: El nombre completo de la persona.
- profesion: La profesión actual o más reciente de la persona.
- skill_tecnico: Habilidades técnicas mencionadas.

Devuelve el resultado en el siguiente formato JSON:
{
  "nombre": "Nombre completo aquí",
  "profesion": "Profesión aquí",
  "skill_tecnico": "Habilidades técnicas aquí",
} Texto del CV: """
                    + str(text_array)
                ),
            }
        ],
        temperature=0.0,
        top_p=0.1,
        max_tokens=700,
    )
    return completion.choices[0].message.content
        # Procesar y limpiar el JSON
    #     salida = completion.choices[0].message['content']
    #     inicio = salida.find('{')
    #     fin = salida.rfind('}') + 1
    #     data1 = salida[inicio:fin]

    #     clean_item = remove_json_comments(data1)
    #     data_dict = json.loads(clean_item)
    #     return data_dict
    
    # except Exception as e:
    #     print(f"Error processing row: {e}")
    #     return None

def aplicar_reglas(row):
    similarity_score = row['nota cotizacion']  # 'nota cotizacion'
    umbral_division = row['proporcion_palabras']     # 'proporcion_palabras'
    
    # Regla 1: Si el similarity_score es menor a 0.3, no aplicar ningún factor
    if similarity_score < 0.29:
        return similarity_score
    
    # Regla 2: Si el similarity_score está entre 0.3 y 0.6
    elif 0.29 <= similarity_score <= 0.6: # 0.6
        similarity_score *= 1.2  # Aplicar factor multiplicador
        if 0.2 < umbral_division <= 0.6:
            #similarity_score *= 1.2  # Multiplicar 1.2 adicional si el umbral es mayor a 0.2
            similarity_score *= (0.8 + umbral_division)
            similarity_score = min(similarity_score, 1)
        elif 0.6 < umbral_division <= 1:
            similarity_score *= (0.6 + umbral_division)
            similarity_score = min(similarity_score, 1)
        elif umbral_division > 1:
            similarity_score *= (1.5)
            similarity_score = min(similarity_score, 1)
        return similarity_score
    
    # Regla 3: Si el similarity_score es mayor a 0.6
    elif similarity_score > 0.6:
        similarity_score *= 1.2  # Aplicar factor multiplicador
        if 0.2 < umbral_division <= 0.6:
            similarity_score *= (1 + umbral_division)  # Sumar 1 al umbral y multiplicar
            similarity_score = min(similarity_score, 1)
        elif 0.6 < umbral_division <= 1:
            similarity_score *= (0.7 + umbral_division)
            similarity_score = min(similarity_score, 1)
        elif umbral_division > 1:
            similarity_score *= (1.5)
            similarity_score = min(similarity_score, 1)
        return similarity_score
    similarity_score = min(similarity_score, 1)
    return similarity_score

def lambda_handler(event, context):
    id = event["id"]
    cv = query(consulta_cv, columnas_cv, id)

    # Establecer el número de hilos
    NUM_THREADS = 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {executor.submit(process_row, row): index for index, row in cv.iterrows()}
        results = [(futures[future], future.result()) for future in concurrent.futures.as_completed(futures)]
    results.sort(key=lambda x: x[0])
    # Filtrar resultados nulos
    data_dicts = [json.loads(result) for index, result in results]

    # Crear DataFrame final
    df = pd.DataFrame(data_dicts)
    cv_final = pd.concat([cv, df], axis=1)
    del cv_final["url_cv"]

######
    l = [np.array(query(consulta_cotizacion, columnas_cotizacion, id, i)) for i in cv_final.id_especialista]
    flattened_data = [item[0] for item in l]
    df_cotizacion = pd.DataFrame(flattened_data, columns=columnas_cotizacion)
    
    requerimiento = query(consulta_requerimiento, columnas_requerimiento, id)
    df_req = requerimiento
    df_cot = pd.concat([cv_final, df_cotizacion], axis=1)
    
    # Limpiar HTML de las columnas seleccionadas
    columns_with_html = ['tecnologias_propuestas', 'consideraciones', 'alcance_servicio', 'entregables', 'fuera_alcance_servicio']
    df_cot[columns_with_html] = df_cot[columns_with_html].applymap(remove_html_tags)
    df_req['detalle_alcance_requerimiento'] = df_req['detalle_alcance_requerimiento'].apply(remove_html_tags)
    
    # Calcular similitudes
    df_req['detalle_alcance_requerimiento'] = df_req['detalle_alcance_requerimiento'].apply(limpiar_texto)
    df_req['objetivo_requerimiento'] = df_req['objetivo_requerimiento'].apply(limpiar_texto)
    df_cot['alcance_servicio'] = df_cot['alcance_servicio'].apply(limpiar_texto)
    df_cot['entregables'] = df_cot['entregables'].apply(limpiar_texto)
    df_cot['skill_tecnico'] = df_cot['skill_tecnico'].apply(limpiar_texto)
    df_cot['tecnologias_propuestas'] = df_cot['tecnologias_propuestas'].apply(limpiar_texto)
    
    sim_general = similitud(df_req[['objetivo_requerimiento','detalle_alcance_requerimiento']], df_cot[['alcance_servicio','entregables']])
    sim_perfil = similitud(df_req, df_cot[['skill_tecnico','tecnologias_propuestas']])

    # Crear DataFrame final
    df_final = pd.concat([df_cot[['id_especialista', 'nombre']], sim_general.T], axis=1).rename(columns={0: 'sim_general'})
    df_final = pd.concat([df_final, sim_perfil.T], axis=1).rename(columns={0: 'sim_perfil'})
    df_final = df_final.loc[:, ~df_final.columns.duplicated()]
    df_final[['sim_general', 'sim_perfil']] = df_final[['sim_general', 'sim_perfil']]
    
    # Filtrar y convertir a JSON
    df_merged = pd.merge(df_final, df_cotizacion, on='id_especialista')
    df_filtered = df_merged[df_merged['sim_general'] > -5]
    df_result = df_filtered[['id_especialista', 'nombre', 'disponibilidad', 'dias_tiempo_ejecucion', 'precio_rango_1', 'precio_rango_2', 'descripcion_tipo_moneda', 'sim_perfil','sim_general']]
    #df_result[['precio_convertido', 'flag_conversion']] = df_result.apply(convertir_precio, axis=1)
    
    proporcion_palabras = []
    for i in range(len(df_cot)): 
        cotizacion_proc = limpiar_texto(df_cot['alcance_servicio'][i])
        requerimiento_proc = limpiar_texto(df_req['detalle_alcance_requerimiento'][0])
        
        palabras_cotizacion = len(cotizacion_proc.split())
        palabras_requerimiento = len(requerimiento_proc.split())
        proporcion = palabras_cotizacion / palabras_requerimiento
        proporcion_palabras.append(proporcion)
    
    df_proporciones = pd.DataFrame(proporcion_palabras, columns=['proporcion_palabras'])
    df_result = pd.concat([df_result, df_proporciones], axis=1)
    
    df_json2 = df_result[['id_especialista','nombre','precio_convertido','flag_conversion','dias_tiempo_ejecucion', 'sim_perfil','sim_general','proporcion_palabras']].rename(columns={'precio_convertido': 'costo', 'dias_tiempo_ejecucion': 'tiempo', 'sim_perfil': 'nota perfil','sim_general':'nota cotizacion'})
    df_json2['adjusted_similarity_score'] = df_json2.apply(aplicar_reglas, axis=1)
    df_json2 = df_json2[['id_especialista','nombre','costo','flag_conversion','tiempo', 'nota perfil','adjusted_similarity_score']].rename(columns={'adjusted_similarity_score':'nota cotizacion'})
    df_json2['nota cotizacion'] = df_json2['nota cotizacion'].round(3)
    df_json2['nota perfil'] = df_json2['nota perfil'].round(3)
 
    df_dict = df_json2.to_dict(orient='records')

    return {
  
        #'body': {
            'result': df_dict
        #}
        }