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
    fernet = Fernet(key)

    encrypted_path = Path("garmin_tokens.enc")
    token_dir = Path.home() / ".garminconnect"
    token_dir.mkdir(parents=True, exist_ok=True)

    token_path = token_dir / "garmin_tokens.json"

    encrypted = encrypted_path.read_bytes()
    original_plaintext = fernet.decrypt(encrypted)

    token_path.write_bytes(original_plaintext)

    os.chmod(token_dir, 0o700)
    os.chmod(token_path, 0o600)

    return token_dir, token_path, original_plaintext, fernet


def persist_token_store(token_path, original_plaintext, fernet):
    current_plaintext = token_path.read_bytes()

    if current_plaintext == original_plaintext:
        print("Garmin token: unchanged")
        return

    encrypted = fernet.encrypt(current_plaintext)
    Path("garmin_tokens.enc").write_bytes(encrypted)

    print("Garmin token: updated and re-encrypted")


# -----------------------------
# Airtable
# -----------------------------

def airtable_headers():
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_TOKEN']}",
        "Content-Type": "application/json",
    }


def find_airtable_records(target_date):
    formula = f"IS_SAME({{Date}}, '{target_date}', 'day')"

    response = requests.get(
        AIRTABLE_URL,
        headers=airtable_headers(),
        params={
            "filterByFormula": formula,
        },
        timeout=30,
    )

    response.raise_for_status()
    return response.json().get("records", [])


def write_airtable(target_date, rhr, hrv, sleep_h):
    desired_fields = {
        FIELD_DATE: target_date,
        FIELD_SYNC_STATUS: "ok",
    }

    if rhr is not None:
        desired_fields[FIELD_RHR] = rhr

    if hrv is not None:
        desired_fields[FIELD_HRV] = hrv

    if sleep_h is not None:
        desired_fields[FIELD_SLEEP] = sleep_h

    records = find_airtable_records(target_date)

    if not records:
        response = requests.post(
            AIRTABLE_URL,
            headers=airtable_headers(),
            json={"fields": desired_fields},
            timeout=30,
        )
        response.raise_for_status()

        print("Airtable: CREATED")
        return

    record = records[0]
    record_id = record["id"]
    current_fields = record.get("fields", {})

    needs_update = False

    for field_id, desired_value in desired_fields.items():
        current_value = current_fields.get(field_id)

        if current_value != desired_value:
            needs_update = True
            break

    if needs_update:
        response = requests.patch(
            f"{AIRTABLE_URL}/{record_id}",
            headers=airtable_headers(),
            json={"fields": desired_fields},
            timeout=30,
        )
        response.raise_for_status()

        print("Airtable: UPDATED")
    else:
        print("Airtable: ALREADY CORRECT")

    if len(records) > 1:
        print(f"WARNING: {len(records)} Airtable records found for {target_date}")


# -----------------------------
# Main
# -----------------------------

def main():
    token_dir, token_path, original_plaintext, fernet = decrypt_token_store()

    garmin = Garmin()
    garmin.login(str(token_dir))

    target_dates = [
        date.today().isoformat(),
        (date.today() - timedelta(days=1)).isoformat(),
    ]

    for target_date in target_dates:
        stats = garmin.get_stats(target_date)
        hrv_data = garmin.get_hrv_data(target_date)
        sleep_data = garmin.get_sleep_data(target_date)

        rhr = stats.get("restingHeartRate")

        hrv = None
        if hrv_data:
            hrv_summary = hrv_data.get("hrvSummary") or {}
            hrv = hrv_summary.get("lastNightAvg")

        sleep_h = None
        if sleep_data:
            daily_sleep = sleep_data.get("dailySleepDTO") or {}
            sleep_seconds = daily_sleep.get("sleepTimeSeconds")

            if sleep_seconds is not None:
                sleep_h = round(sleep_seconds / 3600, 4)

        print(f"Date: {target_date}")
        print(f"RHR: {rhr}")
        print(f"HRV: {hrv}")
        print(f"Sleep: {sleep_h} h")

        write_airtable(target_date, rhr, hrv, sleep_h)

    persist_token_store(
        token_path,
        original_plaintext,
        fernet,
    )

    print("SYNC OK")


if __name__ == "__main__":
    main()
