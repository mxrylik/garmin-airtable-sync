import os
from pathlib import Path
from datetime import date, timedelta

import requests
from cryptography.fernet import Fernet
from garminconnect import Garmin


# -----------------------------
# Airtable configuration
# -----------------------------

BASE_ID = "appODzOniZ5mtshz8"
TABLE_ID = "tbl2taugvLTe4rHue"

FIELD_DATE = "fldFVpDGxDIh2iUk6"
FIELD_SLEEP = "fld56za0QTFKgLovu"
FIELD_RHR = "fldSFaBuHjmMbwyfv"
FIELD_HRV = "fldQIk0FsKIZrNxYK"
FIELD_SYNC_STATUS = "fldhSqNrsqEArDJiY"

AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"


# -----------------------------
# Garmin token handling
# -----------------------------

def decrypt_token_store():
    key = os.environ["GARMIN_TOKEN_KEY"].encode()

    encrypted_path = Path("garmin_tokens.enc")
    token_dir = Path.home() / ".garminconnect"
    token_dir.mkdir(parents=True, exist_ok=True)

    token_path = token_dir / "garmin_tokens.json"

    encrypted = encrypted_path.read_bytes()
    decrypted = Fernet(key).decrypt(encrypted)
    token_path.write_bytes(decrypted)

    os.chmod(token_dir, 0o700)
    os.chmod(token_path, 0o600)

    return token_dir


# -----------------------------
# Airtable helpers
# -----------------------------

def airtable_headers():
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_TOKEN']}",
        "Content-Type": "application/json",
    }


def find_airtable_record(target_date):
    formula = f"{{Date}}='{target_date}'"

    response = requests.get(
        AIRTABLE_URL,
        headers=airtable_headers(),
        params={
            "filterByFormula": formula,
            "maxRecords": 1,
        },
        timeout=30,
    )

    response.raise_for_status()

    records = response.json().get("records", [])

    if records:
        return records[0]["id"]

    return None


def write_airtable(target_date, rhr, hrv, sleep_h):
    fields = {
        FIELD_DATE: target_date,
        FIELD_SYNC_STATUS: "ok",
    }

    if rhr is not None:
        fields[FIELD_RHR] = rhr

    if hrv is not None:
        fields[FIELD_HRV] = hrv

    if sleep_h is not None:
        fields[FIELD_SLEEP] = sleep_h

    record_id = find_airtable_record(target_date)

    if record_id:
        response = requests.patch(
            f"{AIRTABLE_URL}/{record_id}",
            headers=airtable_headers(),
            json={"fields": fields},
            timeout=30,
        )
        action = "UPDATED"

    else:
        response = requests.post(
            AIRTABLE_URL,
            headers=airtable_headers(),
            json={"fields": fields},
            timeout=30,
        )
        action = "CREATED"

    response.raise_for_status()

    print(f"Airtable: {action}")


# -----------------------------
# Main
# -----------------------------

def main():
    token_dir = decrypt_token_store()

    garmin = Garmin()
    garmin.login(str(token_dir))

    target_date = (date.today() - timedelta(days=1)).isoformat()

    stats = garmin.get_stats(target_date)
    hrv_data = garmin.get_hrv_data(target_date)
    sleep_data = garmin.get_sleep_data(target_date)

    # Resting heart rate
    rhr = stats.get("restingHeartRate")

    # Nightly HRV
    hrv = None
    if hrv_data:
        hrv_summary = hrv_data.get("hrvSummary") or {}
        hrv = hrv_summary.get("lastNightAvg")

    # Sleep duration
    sleep_h = None
    if sleep_data:
        daily_sleep = sleep_data.get("dailySleepDTO") or {}
        sleep_seconds = daily_sleep.get("sleepTimeSeconds")

        if sleep_seconds is not None:
            sleep_h = round(sleep_seconds / 3600, 2)

    print(f"Date: {target_date}")
    print(f"RHR: {rhr}")
    print(f"HRV: {hrv}")
    print(f"Sleep: {sleep_h} h")

    write_airtable(target_date, rhr, hrv, sleep_h)

    print("SYNC OK")


if __name__ == "__main__":
    main()
