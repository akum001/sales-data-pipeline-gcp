# 📊 Event-Driven Near Real-Time Sales Data Pipeline on GCP

This project implements a **scalable, event-driven ETL pipeline on Google Cloud Platform (GCP)** that:

* Simulates and uploads raw sales data
* Triggers a Cloud Function using Eventarc on GCS upload
* Runs a Spark job on Dataproc
* Loads processed data into **BigQuery**

Technologies used: **Cloud Storage**, **Pub/Sub**, **Eventarc**, **Cloud Functions**, **Dataproc**, **Spark**, **BigQuery**

---

## 🔧 1. Project Setup (One-Time)

### 1.1 Create a GCP Project and Link Billing

```bash
gcloud projects create spark-bq-pipeline-sales-101 --name="SparkBQPipeline"
gcloud auth application-default set-quota-project spark-bq-pipeline-sales-101
gcloud config set project spark-bq-pipeline-sales-101
gcloud beta billing accounts list
gcloud beta billing projects link spark-bq-pipeline-sales-101 --billing-account=YOUR_BILLING_ACCOUNT_ID
```

---

## ☁️ 2. Enable Required GCP APIs

```bash
gcloud services enable \
  compute.googleapis.com \
  dataproc.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  cloudfunctions.googleapis.com \
  eventarc.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com
```

---

## 🪣 3. Create Cloud Storage Buckets

```bash
gsutil mb -c STANDARD -l us-central1 gs://sales-data-bucket-sales-101
gsutil mb -c STANDARD -l us-central1 gs://spark-temp-bucket-sales-101
```

No need to manually create folders. GCS uses **object prefixes**, and your PySpark script will write to:

```
gs://sales-data-bucket-sales-101/raw/
gs://sales-data-bucket-sales-101/scripts/
```

---

## 🔐 4. IAM Setup for Dataproc & Eventarc

### 4.1 Create and Configure Service Account

```bash
PROJECT_ID="spark-bq-pipeline-sales-101"
SA_NAME="dataproc-spark-sa"

gcloud iam service-accounts create $SA_NAME --display-name "Dataproc Spark SA"
```

### 4.2 Grant Required Roles

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/dataproc.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/dataproc.worker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud storage buckets add-iam-policy-binding gs://spark-temp-bucket-sales-101 \
  --member=serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/storage.objectAdmin

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/eventarc.eventReceiver"
```

---

## 🗃️ 5. BigQuery Setup

### 5.1 Create Dataset and Table

```bash
bq mk --dataset --location=us sparkbqpipelinev1:sales_dataset
```

```bash
bq mk --table sales_dataset.sales_data \
product:STRING,price:FLOAT64,quantity:INT64,total:FLOAT64,ordered_at:TIMESTAMP,delivery_at:TIMESTAMP,processed_at:TIMESTAMP
```

---

## 🚀 6. Dataproc Cluster Setup

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

## 🧠 7. Upload PySpark Script to GCS

```bash
gsutil cp scripts/process_sales.py gs://sales-data-bucket-sales-101/scripts/
```

---

## ⚙️ 8. Deploy Cloud Function (Triggered by GCS Upload)

### 8.1 Prepare Environment Variables

| Key               | Value                                                       |
| ----------------- | ----------------------------------------------------------- |
| PROJECT\_ID       | spark-bq-pipeline-sales-101                                 |
| REGION            | us-central1                                                 |
| SCRIPT\_PATH      | gs\://sales-data-bucket-sales-101/scripts/process\_sales.py |
| CLUSTER\_NAME     | dataproc-sales-cluster                                      |
| TEMP\_GCS\_BUCKET | spark-temp-bucket-sales-101                                 |
| BQ\_DATASET       | sales\_dataset                                              |
| BQ\_TABLE         | sales\_data                                                 |

### 8.2 Zip the Function Files

```bash
cd scripts/
zip function.zip main.py requirements.txt
```

### 8.3 Deploy Cloud Function

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

## ⚠️ 9. Troubleshooting Eventarc IAM Error

When deploying the Cloud Function for the first time, you may see:

```
ERROR: (gcloud.functions.deploy) OperationError: Creating trigger failed...
```

This happens because **GCP hasn’t created required service accounts yet** (like `gs-project-accounts`).

### ✅ Solution

```bash
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

Then retry the function deployment.

---

## 🧪 10. Simulate Data Upload

```bash
python3 sales_data_simulator.py --gcs_bucket=sales-data-bucket-sales-101
```

This will:

* Generate sales data CSV locally every 10 mins (by default)
* Upload to `gs://sales-data-bucket-sales-101/raw/`
* Trigger Cloud Function → Dataproc job → Spark → BigQuery

---

## 📁 11. Project Structure

```
sales-data-pipeline-gcp/
│
├── scripts/
│   ├── process_sales.py         ← PySpark job
│   └── main.py                  ← Cloud Function handler
│
├── sales_data_simulator.py     ← Sales data simulator
```

---