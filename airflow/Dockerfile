FROM apache/airflow:2.8.1

USER root

# libaio é necessário para o oracledb em modo thick (opcional),
# mas o modo thin (padrão do python-oracledb) não precisa dele.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libaio1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.oci && chown -R airflow:root /root/.oci

USER airflow

# Install Python dependencies
COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Mapa versionado cliente -> schema Oracle usado pelo extrator Python
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/
COPY --chown=airflow:root .secrets/ /opt/airflow/.secrets/

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
ENV AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
# Garante que o diretório de plugins está no PYTHONPATH
ENV PYTHONPATH="/opt/airflow/plugins:${PYTHONPATH}"

EXPOSE 8080 8793

#CMD ["airflow", "standalone"]
