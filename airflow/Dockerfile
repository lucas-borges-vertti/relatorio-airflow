FROM apache/airflow:2.8.1

USER root

# libaio é necessário para o oracledb em modo thick (opcional)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libaio1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.oci && chown -R airflow:root /root/.oci

USER airflow

# Install Python dependencies
# O arquivo requirements.txt está dentro de airflow/
COPY --chown=airflow:root airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Ajuste dos caminhos: a origem agora reflete a estrutura do seu repositório
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/
COPY --chown=airflow:root airflow/plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root airflow/config/ /opt/airflow/config/

# A pasta .secrets está na raiz do projeto
COPY --chown=airflow:root .secrets/ /opt/airflow/.secrets/

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
ENV AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
ENV PYTHONPATH="/opt/airflow/plugins:${PYTHONPATH}"

EXPOSE 8080 8793