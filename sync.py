import os
from pathlib import Path
from datetime import date, timedelta

from cryptography.fernet import Fernet
from garminconnect import Garmin


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


def main():
    token_dir = decrypt_token_store()

    garmin = Garmin()
    garmin.login(str(token_dir))

    target_date = (date.today() - timedelta(days=1)).isoformat()

    stats = garmin.get_stats(target_date)
    hrv_data = garmin.get_hrv_data(target_date)

    rhr = stats.get("restingHeartRate")

    hrv = None
    if hrv_data:
        hrv_summary = hrv_data.get("hrvSummary") or {}
        hrv = hrv_summary.get("lastNightAvg")

    print(f"Date: {target_date}")
    print(f"RHR: {rhr}")
    print(f"HRV: {hrv}")


if __name__ == "__main__":
    main()
