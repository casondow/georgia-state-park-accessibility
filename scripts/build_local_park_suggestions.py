"""Suggest nearby OSM recreation features for lower-access counties.

Suggestions are informational OpenStreetMap features, not verified public
entrances or endorsements. Each Low/Very Low drive-time county receives up to
three named options, preferring features within its boundary.
"""

from pathlib import Path
import re

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OSM_GPKG = (
    ROOT
    / "data"
    / "raw"
    / "local_parks"
    / "georgia-260718-free.gpkg"
    / "georgia.gpkg"
)
ANALYSIS_CRS = "EPSG:26917"
MAX_SUGGESTIONS = 3


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_options() -> gpd.GeoDataFrame:
    where = "fclass IN ('park', 'recreation_ground') AND name IS NOT NULL AND name <> ''"
    point_options = gpd.read_file(
        OSM_GPKG,
        layer="gis_osm_pois_free",
        columns=["osm_id", "fclass", "name", "geometry"],
        where=where,
    ).to_crs(ANALYSIS_CRS)

    polygon_frames = []
    for layer in ["gis_osm_pois_a_free", "gis_osm_landuse_a_free"]:
        frame = gpd.read_file(
            OSM_GPKG,
            layer=layer,
            columns=["osm_id", "fclass", "name", "geometry"],
            where=where,
        ).to_crs(ANALYSIS_CRS)
        frame["geometry"] = frame.geometry.representative_point()
        polygon_frames.append(frame)

    options = gpd.GeoDataFrame(
        pd.concat([point_options, *polygon_frames], ignore_index=True),
        geometry="geometry",
        crs=ANALYSIS_CRS,
    )
    options["name"] = options["name"].astype("string").str.strip()
    options["name_key"] = options["name"].map(normalize_name)

    state_parks = gpd.read_file(
        PROCESSED / "park_points.gpkg",
        layer="park_points",
        columns=["park_name"],
        ignore_geometry=True,
    )
    state_park_keys = {
        normalize_name(re.sub(r"\bSP$", "State Park", name, flags=re.IGNORECASE))
        for name in state_parks["park_name"]
    }
    options = options.loc[
        ~options["name"].str.contains(r"\bstate park\b", case=False, na=False)
        & ~options["name_key"].isin(state_park_keys)
    ].copy()

    # Remove duplicate OSM representations of the same named feature nearby.
    options["x_bucket"] = (options.geometry.x / 500).round().astype(int)
    options["y_bucket"] = (options.geometry.y / 500).round().astype(int)
    options = options.drop_duplicates(["name_key", "x_bucket", "y_bucket"]).copy()
    options["option_id"] = range(1, len(options) + 1)
    return options


def main() -> None:
    counties = gpd.read_file(
        PROCESSED / "drive_time_accessibility.gpkg",
        layer="county_drive_time",
    )
    priority = counties.loc[
        counties["drive_access_category"].isin(["Low", "Very Low"])
    ].copy()
    priority["county_centroid"] = priority.geometry.centroid

    options = load_options()
    within = gpd.sjoin(
        options,
        priority[["county", "geometry"]],
        how="inner",
        predicate="within",
    )

    rows = []
    selected_option_ids = set()
    for _, county in priority.iterrows():
        candidates = within.loc[within["county"] == county["county"]].copy()
        if candidates.empty:
            candidates = options.copy()
            source_note = "Nearest named OSM recreation option"
        else:
            source_note = "Named OSM recreation option within county"

        candidates["distance_metres"] = candidates.geometry.distance(
            county["county_centroid"]
        )
        choices = candidates.nsmallest(MAX_SUGGESTIONS, "distance_metres")

        labels = []
        for rank, (_, choice) in enumerate(choices.iterrows(), start=1):
            labels.append(f"{choice['name']} ({choice['fclass'].replace('_', ' ')})")
            selected_option_ids.add(int(choice["option_id"]))
            rows.append(
                {
                    "county": county["county"],
                    "rank": rank,
                    "option_id": int(choice["option_id"]),
                    "local_option": choice["name"],
                    "option_type": choice["fclass"],
                    "centroid_distance_miles": choice["distance_metres"] / 1609.344,
                    "selection_basis": source_note,
                }
            )

    suggestions = pd.DataFrame(rows)
    suggestions["centroid_distance_miles"] = suggestions[
        "centroid_distance_miles"
    ].round(1)
    suggestions.to_csv(PROCESSED / "local_park_suggestions.csv", index=False)

    popup = (
        suggestions.sort_values(["county", "rank"])
        .groupby("county")["local_option"]
        .apply(lambda values: " • ".join(values))
        .rename("nearby_recreation_options")
        .reset_index()
    )
    popup.to_csv(PROCESSED / "local_park_popup_text.csv", index=False)

    selected = options.loc[options["option_id"].isin(selected_option_ids)][
        ["option_id", "name", "fclass", "geometry"]
    ].copy()
    selected.to_file(
        PROCESSED / "local_park_suggestions.gpkg",
        layer="suggested_recreation_options",
        driver="GPKG",
    )

    print(f"Priority counties: {len(priority)}")
    print(f"Suggestion rows: {len(suggestions)}")
    print(f"Unique mapped options: {len(selected)}")


if __name__ == "__main__":
    main()
