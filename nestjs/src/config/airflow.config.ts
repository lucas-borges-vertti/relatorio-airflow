export const airflowConfig = {
  baseUrl: process.env.AIRFLOW_BASE_URL || 'http://localhost:8080',
  dagId: process.env.AIRFLOW_DAG_ID || 'report_generation_dag',
  apiUser: process.env.AIRFLOW_API_USER || 'airflow',
  apiPassword: process.env.AIRFLOW_API_PASSWORD || 'airflow',
};
