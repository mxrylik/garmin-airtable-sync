import os
from datetime import date, timedelta

from garminconnect import Garmin


GARMIN_EMAIL = os.environ["GARMIN_EMAIL"]
GARMIN_PASSWORD = os.environ["GARMIN_PASSWORD"]


def main():
    target_date = (date.today() - timedelta(days=1)).isoformat()

    garmin = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    garmin.login()

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
