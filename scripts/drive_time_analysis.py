"""Estimate county-to-park drive times with the OSRM table service.

This screening analysis routes from county geometric centroids to state-park
representative points. It does not use verified park entrances or household
origins. The public OSRM demo endpoint is suitable for reproducible portfolio
testing, not production workloads.
"""

from pathlib import Path
import time

import geopandas as gpd
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OSRM_BASE_URL = "https://router.project-osrm.org"
MILES_PER_METRE = 1 / 1609.344
BATCH_SIZE = 45  # 45 origins + 47 destinations remains below 100 coordinates.

DRIVE_CATEGORY_ORDER = ["High", "Moderate", "Low", "Very Low"]


def classify_drive_time(minutes: float) -> str:
    if minutes <= 30:
        return "High"
    if minutes <= 45:
        return "Moderate"
    if minutes <= 60:
        return "Low"
    return "Very Low"


def request_table(
    origins: gpd.GeoDataFrame,
    destinations: gpd.GeoDataFrame,
    retries: int = 3,
) -> dict:
    locations = list(origins.geometry) + list(destinations.geometry)
    coordinates = ";".join(f"{point.x:.6f},{point.y:.6f}" for point in locations)
    source_indexes = ";".join(str(index) for index in range(len(origins)))
    destination_indexes = ";".join(
        str(index) for index in range(len(origins), len(locations))
    )
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coordinates}"
    params = {
        "sources": source_indexes,
        "destinations": destination_indexes,
        "annotations": "duration,distance",
    }

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "Ok":
                raise RuntimeError(payload)
            return payload
        except (requests.RequestException, RuntimeError, ValueError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(3 * attempt)
    raise RuntimeError(f"OSRM request failed after {retries} attempts: {last_error}")


def main() -> None:
    counties = gpd.read_file(
        PROCESSED / "state_park_accessibility.gpkg",
        layer="county_accessibility",
    )
    parks = gpd.read_file(PROCESSED / "park_points.gpkg", layer="park_points")

    county_points = counties[["GEOID", "county", "geometry"]].copy()
    county_points["geometry"] = counties.geometry.centroid
    county_points = county_points.to_crs("EPSG:4326").reset_index(drop=True)
    parks = parks.to_crs("EPSG:4326").reset_index(drop=True)

    records = []
    for start in range(0, len(county_points), BATCH_SIZE):
        origins = county_points.iloc[start : start + BATCH_SIZE].copy()
        table = request_table(origins, parks)

        for row_index, (_, county) in enumerate(origins.iterrows()):
            durations = table["durations"][row_index]
            distances = table["distances"][row_index]
            valid = [
                index
                for index, duration in enumerate(durations)
                if duration is not None and distances[index] is not None
            ]
            if not valid:
                raise RuntimeError(f"No routable park found for {county['county']}.")
            park_index = min(valid, key=lambda index: durations[index])
            records.append(
                {
                    "GEOID": county["GEOID"],
                    "nearest_drive_park": parks.iloc[park_index]["park_name"],
                    "drive_time_minutes": durations[park_index] / 60,
                    "drive_distance_miles": distances[park_index] * MILES_PER_METRE,
                }
            )
        time.sleep(1)

    drive = pd.DataFrame(records)
    result = counties.merge(drive, on="GEOID", how="left", validate="one_to_one")
    result["drive_access_category"] = result["drive_time_minutes"].map(
        classify_drive_time
    )
    result["drive_access_category"] = pd.Categorical(
        result["drive_access_category"],
        categories=DRIVE_CATEGORY_ORDER,
        ordered=True,
    )

    required = [
        "nearest_drive_park",
        "drive_time_minutes",
        "drive_distance_miles",
        "drive_access_category",
    ]
    if result[required].isna().any().any():
        raise ValueError("Drive-time output contains missing values.")

    result.to_file(
        PROCESSED / "drive_time_accessibility.gpkg",
        layer="county_drive_time",
        driver="GPKG",
    )

    summary = (
        result.groupby("drive_access_category", observed=False)
        .agg(counties=("county", "count"), population=("population", "sum"))
        .reindex(DRIVE_CATEGORY_ORDER)
        .reset_index()
    )
    summary["population_percent"] = (
        summary["population"] / summary["population"].sum() * 100
    ).round(1)
    summary.to_csv(PROCESSED / "drive_time_summary.csv", index=False)

    top10 = result.nlargest(10, "drive_time_minutes")[
        [
            "county",
            "population",
            "nearest_drive_park",
            "drive_time_minutes",
            "drive_distance_miles",
            "drive_access_category",
        ]
    ].copy()
    top10["drive_time_minutes"] = top10["drive_time_minutes"].round(1)
    top10["drive_distance_miles"] = top10["drive_distance_miles"].round(1)
    top10.to_csv(PROCESSED / "top10_drive_time_counties.csv", index=False)

    print("Drive-time analysis complete.")
    print(summary.to_string(index=False))
    print("\nLongest estimated drive times:")
    print(top10.to_string(index=False))


if __name__ == "__main__":
    main()
