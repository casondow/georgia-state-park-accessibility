"""Create static portfolio graphics from the saved drive-time analysis."""

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "maps"

CATEGORY_ORDER = ["High", "Moderate", "Low", "Very Low"]
DRIVE_COLORS = {
    "High": "#2166AC",
    "Moderate": "#67A9CF",
    "Low": "#FDAE61",
    "Very Low": "#B2182B",
}


def main() -> None:
    MAPS.mkdir(parents=True, exist_ok=True)
    counties = gpd.read_file(
        PROCESSED / "drive_time_accessibility.gpkg",
        layer="county_drive_time",
    ).to_crs("EPSG:4326")
    parks = gpd.read_file(
        PROCESSED / "park_points.gpkg",
        layer="park_points",
    ).to_crs("EPSG:4326")

    fig, ax = plt.subplots(figsize=(10, 8))
    for category in CATEGORY_ORDER:
        counties.loc[counties["drive_access_category"] == category].plot(
            ax=ax,
            color=DRIVE_COLORS[category],
            edgecolor="#FFFFFF",
            linewidth=0.35,
        )
    counties.boundary.plot(ax=ax, color="#555555", linewidth=0.2)
    parks.plot(
        ax=ax,
        color="#111111",
        edgecolor="#FFFFFF",
        linewidth=0.35,
        markersize=18,
        zorder=3,
    )
    handles = [
        Patch(facecolor=DRIVE_COLORS[item], edgecolor="none", label=item)
        for item in CATEGORY_ORDER
    ]
    handles.append(
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
    ax.legend(handles=handles, title="Estimated drive-time access", loc="lower left")
    ax.set_title(
        "Estimated Drive Time to Georgia State Parks by County",
        fontsize=18,
        weight="bold",
    )
    ax.text(
        0,
        -0.035,
        "Fastest OSRM route from county geometric centroid to park representative point",
        transform=ax.transAxes,
        fontsize=9,
        color="#444444",
    )
    ax.text(
        0,
        -0.065,
        "Screening estimate; excludes live traffic and verified park entrances",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(MAPS / "drive_time_accessibility_map.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    for category in CATEGORY_ORDER:
        subset = counties.loc[counties["drive_access_category"] == category]
        ax.scatter(
            subset["park_distance_miles"],
            subset["drive_time_minutes"],
            s=20 + subset["population"] / 10_000,
            alpha=0.72,
            color=DRIVE_COLORS[category],
            edgecolor="#FFFFFF",
            linewidth=0.35,
            label=category,
        )
    top_labels = counties.nlargest(6, "drive_time_minutes")
    for _, row in top_labels.iterrows():
        ax.annotate(
            row["county"],
            (row["park_distance_miles"], row["drive_time_minutes"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_title("Straight-Line Distance vs. Estimated Drive Time", weight="bold")
    ax.set_xlabel("Straight-line distance to nearest park (miles)")
    ax.set_ylabel("Estimated drive time to fastest park (minutes)")
    ax.legend(title="Drive-time category", frameon=False)
    ax.grid(color="#DDDDDD", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0,
        -0.14,
        "Bubble size represents county population. The fastest park by road may differ from the nearest park in straight-line distance.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout()
    fig.savefig(
        MAPS / "distance_vs_drive_time.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)

    print("Saved drive-time map and comparison chart.")


if __name__ == "__main__":
    main()
