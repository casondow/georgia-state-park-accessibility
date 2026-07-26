"""Rebuild the Georgia State Park Accessibility analysis.

Run from the repository root with the project's Conda environment active:
    python scripts/reproduce_analysis.py
"""

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.patheffects as path_effects
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "maps"

COUNTIES_PATH = RAW / "counties" / "tl_2025_us_county" / "tl_2025_us_county.shp"
PARKS_PATH = RAW / "state_parks" / "State_Parks" / "dnr20a.shp"
POPULATION_PATH = RAW / "census" / "population.csv"

ANALYSIS_CRS = "EPSG:26917"  # NAD83 / UTM zone 17N; metres
METRES_PER_MILE = 1609.344

CATEGORY_ORDER = ["High", "Moderate", "Low", "Very Low"]
CATEGORY_COLORS = {
    "High": "#2E7D32",
    "Moderate": "#A6D96A",
    "Low": "#FDAE61",
    "Very Low": "#D73027",
}


def classify_access(distance_miles: float) -> str:
    """Classify straight-line centroid distance to the nearest park."""
    if distance_miles <= 10:
        return "High"
    if distance_miles <= 20:
        return "Moderate"
    if distance_miles <= 30:
        return "Low"
    return "Very Low"


def load_population() -> pd.DataFrame:
    """Read the ACS export and return one numeric population row per county."""
    raw = pd.read_csv(POPULATION_PATH)
    estimate_columns = [column for column in raw.columns if "Estimate" in column]
    if not estimate_columns:
        raise ValueError(f"No estimate columns found in {POPULATION_PATH}")

    population = raw[estimate_columns].T.reset_index()
    population.columns = ["source_county", "population"]
    population["county"] = (
        population["source_county"]
        .str.replace(", Georgia!!Estimate", "", regex=False)
        .str.replace(" County", "", regex=False)
        .str.strip()
    )
    population["population"] = pd.to_numeric(
        population["population"].astype("string").str.replace(",", "", regex=False),
        errors="raise",
    )
    population = population[["county", "population"]]

    if len(population) != 159 or population["county"].nunique() != 159:
        raise ValueError("Population table must contain exactly 159 unique Georgia counties.")
    return population


def build_analysis() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Build county accessibility polygons and one representative point per park."""
    counties_us = gpd.read_file(COUNTIES_PATH)
    counties = counties_us.loc[counties_us["STATEFP"].astype("string") == "13"].copy()
    counties["county"] = counties["NAME"].astype("string").str.strip()

    if len(counties) != 159 or counties["county"].nunique() != 159:
        raise ValueError("County layer must contain exactly 159 unique Georgia counties.")

    managed_lands = gpd.read_file(PARKS_PATH)
    managed_lands["NAME"] = managed_lands["NAME"].astype("string").str.strip()

    # The DNR layer contains WMAs and other managed lands. In its naming scheme,
    # state park properties are designated with a terminal "SP".
    park_parcels = managed_lands.loc[
        managed_lands["NAME"].str.endswith(" SP", na=False)
    ].copy()
    park_boundaries = park_parcels.dissolve(by="NAME").reset_index()

    if len(park_boundaries) != 47:
        raise ValueError(
            f"Expected 47 unique state parks after filtering; found {len(park_boundaries)}."
        )

    counties_projected = counties.to_crs(ANALYSIS_CRS)
    park_boundaries_projected = park_boundaries.to_crs(ANALYSIS_CRS)

    # Representative points are calculated only after projection.
    park_points = park_boundaries_projected[["NAME", "geometry"]].copy()
    park_points["geometry"] = park_boundaries_projected.geometry.centroid
    park_points = park_points.rename(columns={"NAME": "park_name"})

    county_points = counties_projected[["GEOID", "county", "geometry"]].copy()
    county_points["geometry"] = counties_projected.geometry.centroid

    nearest = gpd.sjoin_nearest(
        county_points,
        park_points,
        how="left",
        distance_col="distance_metres",
    )
    nearest["park_distance_miles"] = nearest["distance_metres"] / METRES_PER_MILE
    nearest = nearest.rename(columns={"park_name": "nearest_park"})

    population = load_population()
    result = counties_projected[["GEOID", "county", "geometry"]].merge(
        nearest[["GEOID", "nearest_park", "park_distance_miles"]],
        on="GEOID",
        how="left",
        validate="one_to_one",
    )
    result = result.merge(population, on="county", how="left", validate="one_to_one")
    result["access_category"] = result["park_distance_miles"].map(classify_access)
    result["access_category"] = pd.Categorical(
        result["access_category"], categories=CATEGORY_ORDER, ordered=True
    )

    required = ["nearest_park", "park_distance_miles", "population", "access_category"]
    if result[required].isna().any().any():
        raise ValueError("Final analysis contains unmatched or missing values.")
    if result["nearest_park"].str.contains(r"\bWMA\b", case=False, na=False).any():
        raise ValueError("A Wildlife Management Area was incorrectly classified as a park.")

    return gpd.GeoDataFrame(result, geometry="geometry", crs=ANALYSIS_CRS), park_points


def save_outputs(
    accessibility: gpd.GeoDataFrame, park_points: gpd.GeoDataFrame
) -> None:
    """Save validated GIS layers, tables, statistics, and portfolio maps."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)

    accessibility.to_file(
        PROCESSED / "state_park_accessibility.gpkg",
        layer="county_accessibility",
        driver="GPKG",
    )
    park_points.to_file(
        PROCESSED / "park_points.gpkg",
        layer="park_points",
        driver="GPKG",
    )

    top10 = (
        accessibility.nlargest(10, "park_distance_miles")[
            [
                "county",
                "population",
                "nearest_park",
                "park_distance_miles",
                "access_category",
            ]
        ]
        .copy()
    )
    top10["park_distance_miles"] = top10["park_distance_miles"].round(1)
    top10.to_csv(PROCESSED / "top10_underserved_counties.csv", index=False)

    summary = (
        accessibility.groupby("access_category", observed=False)
        .agg(counties=("county", "count"), population=("population", "sum"))
        .reindex(CATEGORY_ORDER)
        .reset_index()
    )
    summary["population_percent"] = (
        summary["population"] / summary["population"].sum() * 100
    ).round(1)
    summary.to_csv(PROCESSED / "accessibility_summary.csv", index=False)

    display_counties = accessibility.to_crs("EPSG:4326")
    display_parks = park_points.to_crs("EPSG:4326")

    fig, ax = plt.subplots(figsize=(10, 8))
    for category in CATEGORY_ORDER:
        display_counties.loc[
            display_counties["access_category"] == category
        ].plot(
            ax=ax,
            color=CATEGORY_COLORS[category],
            edgecolor="#FFFFFF",
            linewidth=0.35,
        )
    display_counties.boundary.plot(ax=ax, color="#555555", linewidth=0.2)
    display_parks.plot(
        ax=ax,
        color="#111111",
        edgecolor="#FFFFFF",
        linewidth=0.35,
        markersize=18,
        zorder=3,
    )
    label_counties = display_counties.nlargest(10, "park_distance_miles").copy()
    label_counties["label_point"] = label_counties.geometry.representative_point()
    label_offsets = {
        "Baker": (-12, -8),
        "Mitchell": (14, 8),
        "Grady": (0, 10),
        "Long": (10, 8),
        "Wayne": (-8, -8),
        "McIntosh": (12, -6),
    }
    for _, row in label_counties.iterrows():
        offset = label_offsets.get(row["county"], (0, 0))
        label = ax.annotate(
            row["county"],
            (row["label_point"].x, row["label_point"].y),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            va="center",
            fontsize=6.5,
            weight="bold",
            color="#222222",
            zorder=4,
        )
        label.set_path_effects(
            [path_effects.withStroke(linewidth=2, foreground="#FFFFFF")]
        )
    relevant_parks = set(label_counties["nearest_park"])
    for _, park in display_parks.loc[
        display_parks["park_name"].isin(relevant_parks)
    ].iterrows():
        label = ax.annotate(
            park["park_name"].replace(" SP", ""),
            (park.geometry.x, park.geometry.y),
            xytext=(5, 3),
            textcoords="offset points",
            fontsize=5.5,
            color="#111111",
            zorder=4,
        )
        label.set_path_effects(
            [path_effects.withStroke(linewidth=2, foreground="#FFFFFF")]
        )
    legend_items = [
        Patch(facecolor=CATEGORY_COLORS[item], edgecolor="none", label=item)
        for item in CATEGORY_ORDER
    ]
    legend_items.append(
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="#111111",
            markeredgecolor="#FFFFFF",
            markersize=7,
            label="State park",
        )
    )
    ax.legend(
        handles=legend_items,
        title="Access category",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=True,
    )
    ax.set_title("Georgia State Park Accessibility by County", fontsize=18, weight="bold")
    ax.text(
        0,
        -0.035,
        "Straight-line distance from county geometric centroid to nearest state park representative point",
        transform=ax.transAxes,
        fontsize=9,
        color="#444444",
    )
    ax.text(
        0,
        -0.065,
        "Sources: Georgia DNR managed lands; U.S. Census TIGER/Line counties; ACS 2024 5-year B01003",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(MAPS / "accessibility_map.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    priority = display_counties.loc[
        display_counties["access_category"].isin(["Low", "Very Low"])
    ]
    fig, ax = plt.subplots(figsize=(10, 8))
    display_counties.plot(
        ax=ax, color="#ECECEC", edgecolor="#FFFFFF", linewidth=0.3
    )
    for category in ["Low", "Very Low"]:
        priority.loc[priority["access_category"] == category].plot(
            ax=ax,
            color=CATEGORY_COLORS[category],
            edgecolor="#555555",
            linewidth=0.4,
        )
    display_parks.plot(
        ax=ax,
        color="#111111",
        edgecolor="#FFFFFF",
        linewidth=0.35,
        markersize=18,
        zorder=3,
    )
    ax.legend(
        handles=[
            Patch(facecolor=CATEGORY_COLORS["Low"], label="Low (20–30 miles)"),
            Patch(facecolor=CATEGORY_COLORS["Very Low"], label="Very Low (>30 miles)"),
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor="#111111",
                markeredgecolor="#FFFFFF",
                markersize=7,
                label="State park",
            ),
        ],
        title="Priority access areas",
        loc="lower left",
    )
    ax.set_title("Georgia Counties with Limited State Park Access", fontsize=18, weight="bold")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(MAPS / "priority_areas_map.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        summary["access_category"].astype("string"),
        summary["population"],
        color=[CATEGORY_COLORS[item] for item in CATEGORY_ORDER],
    )
    ax.bar_label(
        bars,
        labels=[f"{value / 1_000_000:.2f}M" for value in summary["population"]],
        padding=3,
    )
    ax.set_title("Georgia Population by State Park Access Category", weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Population")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(MAPS / "population_by_access_category.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    accessibility, park_points = build_analysis()
    save_outputs(accessibility, park_points)
    print("Rebuilt and validated Georgia State Park Accessibility outputs.")
    print(f"Counties: {len(accessibility)}")
    print(f"State parks: {len(park_points)}")
    print(
        accessibility.groupby("access_category", observed=False)
        .agg(counties=("county", "count"), population=("population", "sum"))
        .to_string()
    )


if __name__ == "__main__":
    main()
