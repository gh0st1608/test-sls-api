FROM python:3.8-slim

# Crear un directorio para el layer
RUN mkdir -p /layer/python/lib/python3.8/site-packages/

# Instalar psycopg2
RUN pip install psycopg2-binary -t /layer/python/lib/python3.8/site-packages/

# Copiar site-packages a un directorio que se montará como un volumen
RUN cp -r /layer/python/lib/python3.8/site-packages /data

# Crear el ZIP del layer
WORKDIR /layer
#CMD ["sh", "-c", "zip -r mylayer.zip python"]
CMD ["bin", "bash"]