import os
import json
import csv
import time
import requests
from datetime import datetime
from tqdm import tqdm

class APIResponseError(Exception):
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

def api_request_with_retry(method, url, request_name="", headers=None, retries=3, delay=2, **kwargs):
    """Make an API request with retry logic."""
    for attempt in range(retries):
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            return response
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise APIResponseError(f"Failed {request_name} after {retries} attempts: {e}")

def sign_in(login_url, email, password):
    payload = {"email": email, "password": password}
    headers = {"Content-Type": "application/json"}
    response = api_request_with_retry("POST", login_url, request_name="sign_in", headers=headers, json=payload)

    if response.status_code not in (200, 201):
        raise APIResponseError("Invalid response from sign_in", response.status_code, response)

    data = response.json()
    if not data.get("success"):
        raise APIResponseError(f"Sign in failed: {data}", response.status_code, response)

    return data["result"]["token"]

def get_active_realities(project_id, structure_id, snapshot_id, base_url, version_url, auth_token):
    """Return list of active reality IDs for a given snapshot."""
    url = f"{base_url}{version_url}/projects/{project_id}/structures/{structure_id}/snapshots"
    headers = {"authorization": f"Bearer {auth_token}", "Connection": "close"}
    response = api_request_with_retry("GET", url, request_name="get_all_snapshots", headers=headers)

    if response.status_code != 200:
        raise APIResponseError("Invalid response for get_all_snapshots", response.status_code, response)

    data = response.json()
    active_realities = []

    for snap in data.get("result", {}).get("mSnapshots", []):
        if snap["_id"] != snapshot_id:
            continue
        for reality in snap.get("reality", []):
            if reality.get("status", "").lower() == "active":
                active_realities.append(reality["_id"])
    return active_realities

def process_custom_snapshots(custom_folder, output_csv, base_url, version_url, auth_token):
    results = []

    json_files = []
    for root, _, files in os.walk(custom_folder):
        for filename in files:
            if filename.lower().endswith(".json"):
                json_files.append(os.path.join(root, filename))

    for filepath in tqdm(json_files, desc="Processing Snapshots"):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            project_id = data.get("project_id")
            structure_id = data.get("structure_id")
            snapshot_id = data.get("snapshot_id")

            if not all([project_id, structure_id, snapshot_id]):
                print(f"Skipping {filepath}: Missing fields")
                continue

            active_realities = get_active_realities(project_id, structure_id, snapshot_id, base_url, version_url, auth_token)
            for rid in active_realities:
                results.append({
                    "project_id": project_id,
                    "structure_id": structure_id,
                    "snapshot_id": snapshot_id,
                    "reality_id": rid
                })

        except Exception as e:
            print(f"Error processing {filepath}: {e}")

    # Save to CSV
    with open(output_csv, "w", newline="") as csvfile:
        fieldnames = ["project_id", "structure_id", "snapshot_id", "reality_id"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"✅ CSV saved to {output_csv}")

if __name__ == "__main__":
    base_url = "https://api.track3d.ai"
    version_url = "/api/v1"
    login_url = f"{base_url}{version_url}/users/signin"

    email = input("Enter email: ")
    password = input("Enter password: ")

    custom_folder = r""
    output_csv = r""

    print("🔑 Signing in...")
    token = sign_in(login_url, email, password)
    print("✅ Got token")

    process_custom_snapshots(custom_folder, output_csv, base_url, version_url, token)
