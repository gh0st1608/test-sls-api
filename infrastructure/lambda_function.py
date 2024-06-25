import sys
efs_mount_path = '/mnt/efs/'
sys.path.append(efs_mount_path)
import json
import os
import numpy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
import requests
from openai import OpenAI
from pdfminer.high_level import extract_text
import mysql.connector




def lambda_handler(event, context):
    
    #cv = query(consulta_cv,columnas_cv,1)
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('cargo exitoso')
    }