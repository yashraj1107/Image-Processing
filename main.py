from flask import Flask, request, jsonify
import pandas as pd
import requests
import os
import uuid
import psycopg2
from PIL import Image
from io import BytesIO

from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Requests


# Database Connection (PostgreSQL)
DB_HOST = "localhost"
DB_NAME = "image"
DB_USER = "postgres"
DB_PASS = "postgres"

# Function to Connect to Database
def connect_db():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)

# Create the Table if not exists
def init_db():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            request_id VARCHAR(50) PRIMARY KEY,
            status VARCHAR(20),
            input_file VARCHAR(255),
            output_file VARCHAR(255),
            webhook_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Initialize database when server starts

# Function to Update Processing Status
def update_request_status(request_id, status, output_file=None):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE requests SET status = %s, output_file = %s WHERE request_id = %s",
                (status, output_file, request_id))
    conn.commit()
    conn.close()

# Image Processing Function
def process_images(request_id, csv_data, webhook_url):
    output_data = []

    for _, row in csv_data.iterrows():
        serial_number = row["no"]
        product_name = row["name"]
        input_urls = row["url"].split(", ")  # Convert comma-separated URLs to list

        output_urls = []
        
        for img_url in input_urls:
            try:
                response = requests.get(img_url)  # Download Image
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    
                    # Compress Image (50% quality)
                    output_path = f"processed_images/{uuid.uuid4()}.jpg"
                    img.save(output_path, "JPEG", quality=50)

                    # Simulate Hosted URL
                    output_urls.append(f"http://localhost:5000/{output_path}")
            except Exception as e:
                print(f"Error processing {img_url}: {e}")
                continue

        output_data.append([serial_number, product_name, ", ".join(input_urls), ", ".join(output_urls)])

    # Save results as CSV
    output_csv_path = f"processed_images/{request_id}.csv"
    output_df = pd.DataFrame(output_data, columns=["no", "name", "Input Image Urls", "Output Image Urls"])
    output_df.to_csv(output_csv_path, index=False)

    # Update request status in the database
    update_request_status(request_id, "Completed", output_csv_path)

    # Trigger Webhook if provided
    if webhook_url:
        webhook_data = {
            "request_id": request_id,
            "status": "Completed",
            "output_file": output_csv_path
        }
        try:
            response = requests.post(webhook_url, json=webhook_data)
            print(f"Webhook triggered: {response.status_code}")
        except Exception as e:
            print(f"Webhook failed: {e}")

# Upload API
@app.route('/upload', methods=['POST'])
def upload_csv():
    """Accept and validate CSV upload"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    webhook_url = request.form.get("webhook_url", "")

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Invalid file format. Please upload a CSV file."}), 400

    try:
        # Read CSV
        df = pd.read_csv(file, encoding="utf-8-sig", sep=",", engine="python", skipinitialspace=True)
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Check for required columns
        expected_columns = {"no", "name", "url"}
        if not expected_columns.issubset(set(df.columns)):
            return jsonify({"error": "Invalid CSV format. Missing required columns.", "detected_columns": df.columns.tolist()}), 400

        #  Generate unique request ID
        request_id = str(uuid.uuid4())

        #  Store request in database
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO requests (request_id, status, input_file, webhook_url) VALUES (%s, %s, %s, %s)",
                    (request_id, "Processing", file.filename, webhook_url))
        conn.commit()
        conn.close()

        #  Process images (Sequential Processing)
        process_images(request_id, df, webhook_url)

        return jsonify({"message": "Processing started", "request_id": request_id}), 202

    except Exception as e:
        return jsonify({"error": f"Error reading CSV file: {str(e)}"}), 400

# Status API
@app.route('/status/<request_id>', methods=['GET'])
def check_status(request_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT status, output_file FROM requests WHERE request_id = %s", (request_id,))
    result = cur.fetchone()
    conn.close()

    if result:
        return jsonify({"status": result[0], "output_file": result[1]})
    else:
        return jsonify({"error": "Invalid request ID"}), 404

if __name__ == '__main__':
    app.run(debug=True)
