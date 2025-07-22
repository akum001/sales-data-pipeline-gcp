import argparse
import csv
import random
import time

from datetime import datetime, timedelta
from google.cloud import storage
from pathlib import Path

# Define product categories and price ranges
GCS_BUCKET_NAME = 'sales-data-bucket-ashu-1752175621'
SALES_CSV_DIR = Path(__file__).resolve().parent / "data"
products = ['Mobile Phones', 'Laptops', 'Tablets', 'Smart Watches', 'Headphones']

price_range = {
    'Mobile Phones': (10000, 150000),
    'Laptops': (30000, 200000),
    'Tablets': (5000, 50000),
    'Smart Watches': (2000, 30000),
    'Headphones': (500, 10000)
}

# Possible ordered dates to sample from
ordered_date = [
    datetime(2023, 1, 1),
    datetime(2023, 2, 1),
    datetime(2023, 3, 1),
    datetime(2023, 4, 1),
    datetime(2023, 5, 1),
    datetime(2023, 6, 1),
    datetime(2023, 7, 1),
    datetime(2023, 8, 1),
    datetime(2023, 9, 1),
    datetime(2023, 10, 1)
]

# Generate delivery date
def generate_delivery_date(start_date):
    random_days = random.randint(0, 10)
    return start_date + timedelta(days=random_days)

# Generate fake sales records
def generate_sales_data(num_records):
    sales_data = []
    for i in range(num_records):
        quantity = None
        total = None
        price = None
        product = random.choice(products)
        if i % 5 != 0:  # Introduce nulls for some rows
            price = random.randint(*price_range[product])
            if i % 2 == 0:
                quantity = random.randint(1, 10)
            if quantity:
                total = price * quantity
            else:
                total = price * random.randint(1, 10)
        ordered_at = generate_delivery_date(random.choice(ordered_date))
        delivery_at = generate_delivery_date(ordered_at)
        sales_data.append({
            'product': product,
            'price': price,
            'quantity': quantity,
            'total': total,
            'ordered_at': ordered_at.strftime('%Y-%m-%d %H:%M:%S'),
            'delivery_at': delivery_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return sales_data

# Save locally and upload to GCS
def save_and_upload_to_gcs(bucket_name, destination_folder='raw', num_records=100):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"sales_data_{timestamp}.csv"
    # Local temp file
    local_path = f"{SALES_CSV_DIR}/{filename}"
    # Destination in GCS
    gcs_path = f"{destination_folder}/{filename}"

    # Write CSV locally
    with open(local_path, mode='w', newline='') as csvfile:
        fieldnames = ['product', 'price', 'quantity', 'total', 'ordered_at', 'delivery_at']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        sales_data = generate_sales_data(num_records)
        writer.writerows(sales_data)

    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)

    print(f"Uploaded {filename} to gs://{bucket_name}/{gcs_path}")

# Run
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--gcs_bucket', required=True, help="GCS bucket name to use")
    parser.add_argument('--num_records', type=int, default=100, help="Number of records to be generated each time")
    parser.add_argument('--interval_min', type=int, default=10, help="Interval in minutes between uploads")

    args = parser.parse_args()

    print(f"Starting uploader to bucket: {args.gcs_bucket}, every {args.interval_min} minutes...")

    try:
        while True:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Generating and uploading data...")
            save_and_upload_to_gcs(bucket_name=args.gcs_bucket, num_records=args.num_records)
            print("Upload complete. Sleeping...\n")
            time.sleep(args.interval_min * 60)
    except KeyboardInterrupt:
        print("Stopped by user.")