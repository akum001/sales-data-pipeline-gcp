# 📊 GCP Sales Data Streaming & Batch Pipeline

This project implements an **end-to-end GCP data pipeline** that simulates, ingests, cleans, and stores sales data into BigQuery using Cloud Functions, Pub/Sub, Cloud Storage, Dataproc, and Spark. You can use this project to demonstrate your cloud data engineering skills using real-time and batch data processing.

---

## 🔧 Project Setup (One-Time)

### 1. **Create GCP Project & Link Billing**
```bash
gcloud projects create spark-bq-pipeline-sales-101 --name="SparkBQPipeline"
gcloud config set project spark-bq-pipeline-sales-101
gcloud beta billing projects link spark-bq-pipeline-sales-101 --billing-account=YOUR_BILLING_ACCOUNT_ID
gcloud auth application-default set-quota-project spark-bq-pipeline-sales-101
```

### 2. **Enable Required APIs**
```bash
gcloud services enable \
  compute.googleapis.com \
  dataproc.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  cloudfunctions.googleapis.com \
  eventarc.googleapis.com \
  eventarc-publishing.googleapis.com \
  eventarcpublishing.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com
```

### 3. **Create Buckets**
```bash
gsutil mb -c STANDARD -l us-central1 gs://sales-data-bucket-sales-101
gsutil mb -c STANDARD -l us-central1 gs://spark-temp-bucket-sales-101
```

Structure:
```
gs://sales-data-bucket-sales-101/raw/
gs://sales-data-bucket-sales-101/scripts/
```

---

## 🧱 IAM Setup (Required for Function + Eventarc)

### 4. **Create service account and give access to all services**
```bash
PROJECT_ID="spark-bq-pipeline-sales-101"
SA_NAME="dataproc-spark-sa"

gcloud iam service-accounts create $SA_NAME --display-name "Dataproc Spark SA"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/dataproc.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/dataproc.worker"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/bigquery.jobUser"

gcloud storage buckets add-iam-policy-binding gs://spark-temp-bucket-sales-101 \
  --member=serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \                              --role=roles/storage.objectAdmin

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" --role="roles/eventarc.eventReceiver"

PROJECT_NUMBER=$(gcloud projects describe spark-bq-pipeline-sales-101 --format="value(projectNumber)")

gsutil iam ch serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-eventarc.iam.gserviceaccount.com:roles/storage.objectViewer gs://sales-data-bucket-sales-101

gsutil iam ch serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com:roles/storage.objectViewer gs://sales-data-bucket-sales-101

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:service-271445855234@gcp-sa-eventarc.iam.gserviceaccount.com" \
  --role="roles/eventarc.serviceAgent"

# Give permission to access Pub/Sub
gcloud projects add-iam-policy-binding spark-bq-pipeline-sales-101 \
  --member="serviceAccount:service-271445855234@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```
---

## 🗃️ BigQuery Setup

### 6. **Create Dataset and Table**
```bash
bq mk --dataset --location=us sparkbqpipelinev1:sales_dataset
```
```bash
bq mk --table sales_dataset.sales_data product:STRING,price:FLOAT64,quantity:INT64,total:FLOAT64,ordered_at:TIMESTAMP,delivery_at:TIMESTAMP,processed_at:TIMESTAMP
```

## 🚀 Dataproc Cluster Setup

### 7. **Create Dataproc Cluster**
```bash
gcloud dataproc clusters create dataproc-sales-cluster \
    --region=us-central1 \  
    --zone=us-central1-a \ 
    --single-node \ 
    --master-boot-disk-size=50GB \  
    --image-version=2.1-debian11 \   
    --enable-component-gateway \  
    --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com
```

---
## 🧪 Deploy Cloud Function (Trigger on GCS Upload)

### 8. **Prepare Environment Variables**

| Key              | Value                                                           |
|------------------|-----------------------------------------------------------------|
| PROJECT_ID       | spark-bq-pipeline-sales-101                                     |
| REGION           | us-central1                                                     |
| SCRIPT_PATH      | gs://sales-data-bucket-sales-101/scripts/process_sales.py       |
| CLUSTER_NAME     | dataproc-sales-cluster                                          |
| RAW_PREFIX       | raw/                                                            |

### 9. **Zip main.py and requirements.txt together**
```bash
cd scripts/
zip function.zip main.py requirements.txt
```
### 9. **Deploy Cloud Function**
```bash
gcloud functions deploy trigger_dataproc_on_upload \
    --runtime python311 \
    --trigger-resource sales-data-bucket-sales-101 \
    --trigger-event google.storage.object.finalize \
    --entry-point gcs_trigger \
    --source . \
    --region us-central1 \
    --memory 512MB \
    --timeout 120s \
    --set-env-vars \
    PROJECT_ID=spark-bq-pipeline-sales-101,REGION=us-central1,SCRIPT_PATH=gs://sales-data-bucket-sales-101/scripts/process_sales.py,CLUSTER_NAME=dataproc-sales-cluster,TEMP_GCS_BUCKET=spark-temp-bucket-sales-101,BQ_DATASET=sales_dataset,BQ_TABLE=sales_data
```

---

## 🧠 Upload PySpark Script to GCS
```bash
gsutil cp scripts/process_sales.py gs://sales-data-bucket-sales-101/scripts/
```

---
## 🧪 Testing the Pipeline

### 10. **Simulate CSV Upload**
```bash
python3 sales_data_simulator.py  --gcs_bucket=sales-data-bucket-sales-101
```
This script:
- Generates sales CSV data in `../data`
- Uploads to `gs://sales-data-bucket-sales-101/raw/`

Once uploaded:
- Cloud Function triggers
- Dataproc job runs `process_sales.py`
- Spark job loads data to BigQuery

---

## 📂 Repository Structure

```
sales-data-pipeline-gcp/
│
├── scripts/
│   ├── process_sales.py         ← PySpark job
│   └── gcs_trigger.py           ← Cloud Function handler
│
├── sales_data_simulator.py     ← Local simulator for generating/uploading sales data
```
