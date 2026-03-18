FROM apache/airflow:2.8.1

USER root

# libaio é necessário para o oracledb em modo thick (opcional),
# mas o modo thin (padrão do python-oracledb) não precisa dele.
# Instalamos apenas o gcc para extensões nativas.
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Mapa versionado cliente -> schema Oracle usado pelo extrator Python
COPY config /opt/airflow/config

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
ENV AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
# Garante que o diretório de plugins está no PYTHONPATH
ENV PYTHONPATH="/opt/airflow/plugins:${PYTHONPATH}"

EXPOSE 8080 8793

CMD ["airflow", "standalone"]
