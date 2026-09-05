"""Small real Earth Engine smoke test.

Example:
    python scripts/check_gee.py --project my-gcp-project
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from webapp import gee_utils  # noqa: E402


DEMO_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [38.9700, 45.0400],
            [38.9800, 45.0400],
            [38.9800, 45.0470],
            [38.9700, 45.0470],
            [38.9700, 45.0400],
        ]
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка доступа к Google Earth Engine")
    parser.add_argument("--project", help="Google Cloud / Earth Engine project id")
    parser.add_argument("--date-from", default="2024-05-01")
    parser.add_argument("--date-to", default="2024-06-30")
    parser.add_argument(
        "--authenticate",
        action="store_true",
        help="Открыть интерактивную авторизацию, если earthengine authenticate ещё не запускался",
    )
    args = parser.parse_args()

    gee_utils.init_gee(project=args.project, authenticate=args.authenticate)
    geometry = gee_utils.to_ee_geometry(DEMO_POLYGON)
    satellite = gee_utils.get_ndvi_timeseries(geometry, args.date_from, args.date_to)
    weather = gee_utils.get_era5_weather(geometry, args.date_from, args.date_to)

    by_sensor = {
        "Sentinel-2": sum(row.get("s2_ndvi") is not None for row in satellite),
        "Landsat": sum(row.get("landsat_ndvi") is not None for row in satellite),
        "MODIS": sum(row.get("modis_ndvi") is not None for row in satellite),
    }
    print("Earth Engine: OK")
    print("Спутниковых дат:", len(satellite), by_sensor)
    print("Дней ERA5:", len(weather))
    print("Последние спутниковые записи:")
    for row in satellite[-3:]:
        print(row)


if __name__ == "__main__":
    main()
