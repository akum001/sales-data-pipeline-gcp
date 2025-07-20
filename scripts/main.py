import os
import googleapiclient.discovery

def gcs_trigger(event, context):
    bucket = event['bucket']
    file_name = event['name']
    file_path = f"gs://{bucket}/{file_name}"

    # Get config from environment variables
    raw_prefix = os.environ.get("RAW_PREFIX", "raw/")
    script_path = os.environ.get("SCRIPT_PATH")
    project_id = os.environ.get("PROJECT_ID")
    region = os.environ.get("REGION", "us-central1")
    cluster_name = os.environ.get("CLUSTER_NAME")

    # Validate required env vars
    if not script_path or not project_id or not cluster_name:
        raise ValueError("Missing one or more required environment variables: SCRIPT_PATH, PROJECT_ID, CLUSTER_NAME")

    # Skip files that don't match expected pattern
    if not file_name.endswith(".csv") or not file_name.startswith(raw_prefix):
        print(f"Ignored file: {file_name} (not a CSV or doesn't start with prefix '{raw_prefix}')")
        return "Not a valid raw CSV file"

    dataproc = googleapiclient.discovery.build("dataproc", "v1")

    job_details = {
        "projectId": project_id,
        "region": region,
        "job": {
            "placement": {"clusterName": cluster_name},
            "pysparkJob": {
                "mainPythonFileUri": script_path,
                "args": [
                    file_path,
                    "--temp_gcs_bucket", os.environ.get("TEMP_GCS_BUCKET"),
                    "--project_id", project_id,
                    "--bq_dataset", os.environ.get("BQ_DATASET"),
                    "--bq_table", os.environ.get("BQ_TABLE")
                ]
            }
        }
    }

    result = dataproc.projects().regions().jobs().submit(
        projectId=project_id,
        region=region,
        body=job_details
    ).execute()

    job_id = result['reference']['jobId']
    print(f"Submitted Dataproc job: {job_id} for file: {file_path}")

    return f"Job {job_id} submitted for {file_path}"
