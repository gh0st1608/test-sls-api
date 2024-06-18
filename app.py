from flask import Flask, jsonify, make_response
import sys
import json
import tempfile
import os
import boto3
import mysql.connector
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
import requests
#import re
from tqdm import tqdm
from openai import OpenAI
import zipfile
from docx import Document
import io
import nltk
from nltk.corpus import stopwords
nltk.download('stopwords')
spanish_stopwords = stopwords.words('spanish')
from pdfminer.high_level import extract_text
s3=boto3.resource('s3')
import mysql.connector
import time
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

host=os.getenv("DB_HOST")
user=os.getenv("DB_USER")
password=os.getenv("DB_PASSWORD")
database=os.getenv("DB_DATABASE")


consulta_requerimiento = """
SELECT 
    r.objetivo_requerimiento, 
    r.nombre_requerimiento, 
    pe.descripcion AS descripcion_perfil_especialista, 
    est.descripcion AS descripcion_estado, 
    p.descripcion AS descripcion_prioridad, 
    GROUP_CONCAT(DISTINCT t.nombre_tecnologia SEPARATOR ', ') AS nombre_tecnologias, 
    tr.descripcion AS descripcion_tipo_requerimiento, 
    GROUP_CONCAT(DISTINCT ar.detalle SEPARATOR ', ') AS detalle_alcance_requerimiento
FROM requerimiento r
JOIN perfil_especialista pe ON r.id_perfil_especialista = pe.id_perfil_especialista
JOIN estado est ON r.id_estado = est.id_estado
JOIN prioridad p ON r.id_prioridad = p.id_prioridad
LEFT JOIN tecnologias t ON r.id_requerimiento = t.id_requerimiento
JOIN tipo_requerimiento tr ON r.id_tipo_requerimiento = tr.id_tipo_requerimiento
LEFT JOIN alcance_requerimiento ar ON r.id_requerimiento = ar.id_requerimiento
WHERE r.id_requerimiento = %s
GROUP BY r.id_requerimiento
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
    re.dias_tiempo_ejecucion,re.precio_rango_1,re.precio_rango_2,e.disponibilidad AS disponibilidad_especialista,
    asv.descripcion AS descripcion_alcance_servicio,ent.descripcion AS descripcion_entregables,fas.descripcion AS descripcion_fuera_alcance_servicio,
    tp.descripcion AS descripcion_tecnologia_propuesta,c.descripcion AS descripcion_consideraciones
FROM requerimiento r
JOIN requerimiento_especialista re ON r.id_requerimiento = re.id_requerimiento
JOIN especialista e ON re.id_especialista = e.id_especialista
LEFT JOIN alcance_servicio asv ON re.id_requerimiento_especialista = asv.id_requerimiento_especialista
LEFT JOIN entregables ent ON re.id_requerimiento_especialista = ent.id_requerimiento_especialista
LEFT JOIN fuera_alcance_servicio fas ON re.id_requerimiento_especialista = fas.id_requerimiento_especialista
LEFT JOIN tecnologias_propuestas tp ON re.id_requerimiento_especialista = tp.id_requerimiento_especialista
LEFT JOIN consideraciones c ON re.id_requerimiento_especialista = c.id_requerimiento_especialista
WHERE r.id_requerimiento = %s AND e.id_especialista= %s;
    """


# COLUMNAS
columnas_requerimiento = ['objetivo_requerimiento','nombre_requerimiento','descripcion_perfil_especialista', 
    'descripcion_estado','descripcion_prioridad','nombre_tecnologias','descripcion_tipo_requerimiento',
                        'detalle_alcance_requerimiento']
columnas_cv = ['id_especialista', 'nombre', 'url_cv']
columnas_cotizacion = ['dias_tiempo_ejecucion','precio_rango_1', 'precio_rango_2','disponibilidad',
                'descripcion_alcance_servicio', 'descripcion_entregables','descripcion_fuera_alcance_servicio',
                'descripcion_tecnologias_propuestas','descripcion_consideraciones']


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
    return df.apply(lambda row: ' '.join(row.values.astype(str)), axis=1)

def similitud(df_req,df_cot):
    req_texts = combine_row_text(df_req)
    cot_texts = combine_row_text(df_cot)
    vectorizer = TfidfVectorizer()
    req_vectors = vectorizer.fit_transform(req_texts)
    cot_vectors = vectorizer.transform(cot_texts)
    similarity_matrix = cosine_similarity(req_vectors, cot_vectors)
    similarity_df = pd.DataFrame(similarity_matrix, index=df_req.index, columns=df_cot.index)
    return similarity_df

@app.route('/test')
def test():
    return jsonify(message='test exitoso')

@app.route('/exec/<int:id>')
def exec(id):
    start_time = time.time()
    
    cv = query(consulta_cv,columnas_cv,id)

    new_data_list = []
    for index, row in cv.iterrows():
        # Extraer la variable deseada (por ejemplo, la columna 'A')
        variable = row['url_cv']
        response = requests.get(variable)
        pdf_filename = 'downloaded_cv.pdf'
        # Guardar el PDF en un archivo local
        with open(pdf_filename, 'wb') as f:
            f.write(response.content)
        # Extraer el texto del PDF
        text = extract_text(pdf_filename)
        # Convertir el texto en un array (lista) de líneas
        text_array_list = text.splitlines()
        text_array = [' '.join(filter(lambda x: x != '', text_array_list))]
        # Mostrar el resultado
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        client = OpenAI(api_key=OPENAI_API_KEY)

        completion = client.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=[
            {"role": "user", 
            'content': "puedes poner en una JSON para python (si no hay respuesta dejar vacio): nombre, profesion, proyectos, cantidad de lugares en que trabajo(solo numero entero), experiencia, correo, linkedin, skill tecnico, skill de gestioin, celular, eduacion postgrado, anos de experiencia (solo numero entero) y educacion tiene "+str(text_array),
            }
            ],
            max_tokens=700 #30
            )
        
        new_data_list.append(completion.choices[0].message.content)
        # Eliminar el archivo PDF descargado
        os.remove(pdf_filename)
        
    df=pd.DataFrame(new_data_list)
    cv_final = pd.concat([cv, df], axis=1)
    del cv_final["url_cv"]
    
    l = []
    for i in cv_final.id_especialista:
        #print(i)
        cotizacion = query(consulta_cotizacion,columnas_cotizacion,id,i)
        cotizacion1 = cotizacion.groupby(['dias_tiempo_ejecucion', 'precio_rango_1', 'precio_rango_2',
        'disponibilidad', 'descripcion_alcance_servicio',
        'descripcion_entregables', 'descripcion_fuera_alcance_servicio',
        'descripcion_consideraciones'])['descripcion_tecnologias_propuestas'].apply(list).reset_index()
        cotizacion1['descripcion_tecnologias_propuestas'] = cotizacion1['descripcion_tecnologias_propuestas'].astype(str)
        cotizacion2 = cotizacion1.groupby(['dias_tiempo_ejecucion', 'precio_rango_1', 'precio_rango_2',
            'disponibilidad', 'descripcion_alcance_servicio',
            'descripcion_entregables','descripcion_tecnologias_propuestas', 
            'descripcion_consideraciones'])['descripcion_fuera_alcance_servicio'].apply(list).reset_index()
        cotizacion2['descripcion_fuera_alcance_servicio'] = cotizacion2['descripcion_fuera_alcance_servicio'].astype(str)
        cotizacion3 = cotizacion2.groupby(['dias_tiempo_ejecucion', 'precio_rango_1', 'precio_rango_2',
            'disponibilidad', 'descripcion_alcance_servicio',
                'descripcion_fuera_alcance_servicio',
            'descripcion_tecnologias_propuestas', 'descripcion_consideraciones'])['descripcion_entregables'].apply(list).reset_index()
        cotizacion3['descripcion_entregables'] = cotizacion3['descripcion_entregables'].astype(str)
        cotizacion4 = cotizacion3.groupby(['dias_tiempo_ejecucion', 'precio_rango_1', 'precio_rango_2',
            'disponibilidad','descripcion_entregables', 'descripcion_fuera_alcance_servicio',
            'descripcion_tecnologias_propuestas', 'descripcion_consideraciones'])['descripcion_alcance_servicio'].apply(list).reset_index()
        cotizacion4['descripcion_alcance_servicio'] = cotizacion3['descripcion_alcance_servicio'].astype(str)
        l.append(np.array(cotizacion4))

    flattened_data = [item[0] for item in l]
    df_cotizacion = pd.DataFrame(flattened_data,columns=columnas_cotizacion)
    
    
    # DATA DE REQUERIMIENTO
    requerimiento = query(consulta_requerimiento,columnas_requerimiento,id)
    # DATA DE CV

    
    df_req = requerimiento
    df_cot = pd.concat([cv_final,df_cotizacion], axis=1) 
    
    sim_general = similitud(df_req,df_cot)
    sim_tiempo = similitud(df_req,df_cot[['dias_tiempo_ejecucion','disponibilidad',
                                        'descripcion_alcance_servicio','descripcion_entregables',
    #                                      'descripcion_consideraciones'
                                        ]])
    sim_costo = similitud(df_req,df_cot[[0,'precio_rango_1','precio_rango_2']])

    sim_perfil = similitud(df_req,df_cot[['descripcion_alcance_servicio',
                                        'descripcion_entregables',
                                        'descripcion_fuera_alcance_servicio',
                                        'descripcion_tecnologias_propuestas',
                                        'descripcion_consideraciones',]])


    # In[17]:


    df_final = pd.concat([df_cot[['id_especialista','nombre']],sim_general.T,sim_perfil.T,sim_tiempo.T,sim_costo.T ], axis=1)


    # In[18]:


    df_final = pd.concat([df_cot[['id_especialista','nombre']],sim_general.T], axis=1)
    df_final = df_final.rename(columns={0:'sim_general'})

    df_final = pd.concat([df_final,sim_perfil.T], axis=1)
    df_final = df_final.rename(columns={0:'sim_perfil'})

    df_final = pd.concat([df_final,sim_tiempo.T], axis=1)
    df_final = df_final.rename(columns={0:'sim_tiempo'})

    df_final = pd.concat([df_final,sim_costo.T], axis=1)
    df_final = df_final.rename(columns={0:'sim_costo'})


    # In[19]:


    df_final 
    # AQUI: MOSTRAR df_final EN EL POSTMAN


    # In[20]:
    df_json = df_final.to_json()

    end_time = time.time()

    execution_time = end_time - start_time
    print("Execution time:", execution_time, "seconds")
    print("el json respuesta es: ",df_json)
    return jsonify(message=df_json)


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error='Not found!'), 404)