"""Streamlit dashboard for Healthier Dining Programme walking-accessibility.

Run with: streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

import config
from dashboard.data import COUNT_COL, district_aggregate, hex_aggregate, load_accessibility_data

st.set_page_config(
    page_title="Healthier Dining Accessibility",
    page_icon="\U0001f957",
    layout="wide",
)

RED = (214, 39, 40)
GREEN = (44, 160, 44)


def color_scale(values: pd.Series, vmax: float) -> list[list[int]]:
    """Linear red->green interpolation, clipped at vmax."""
    ratios = (values.clip(lower=0, upper=vmax) / vmax).fillna(0)
    colors = [
        [
            int(RED[i] + (GREEN[i] - RED[i]) * r)
            for i in range(3)
        ]
        for r in ratios
    ]
    return colors


st.title("\U0001f957 Healthier Dining Programme Accessibility")
st.caption(
    f"Number of HPB Healthier Dining Programme options within "
    f"{config.WALK_DISTANCE_THRESHOLD_M:,}m true walking distance of each HDB "
    f"residential postal code in Singapore."
)

df = load_accessibility_data()

# --- Sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")

district_options = (
    df[["district_number", "district_label"]]
    .dropna()
    .drop_duplicates()
    .sort_values("district_number")
)
district_choices = st.sidebar.multiselect(
    "Postal district",
    options=district_options["district_label"].tolist(),
    default=[],
    help="Leave empty to include all districts.",
)

count_min, count_max = int(df[COUNT_COL].min()), int(df[COUNT_COL].max())
selected_range = st.sidebar.slider(
    "Dining options within 1km",
    min_value=count_min,
    max_value=count_max,
    value=(count_min, count_max),
)

search_text = st.sidebar.text_input("Search address or postal code")

filtered = df.copy()
if district_choices:
    filtered = filtered[filtered["district_label"].isin(district_choices)]
filtered = filtered[
    filtered[COUNT_COL].between(selected_range[0], selected_range[1])
]
if search_text:
    mask = filtered["address"].str.contains(
        search_text, case=False, na=False
    ) | filtered["postal_code"].str.contains(search_text, case=False, na=False)
    filtered = filtered[mask]

st.sidebar.caption(f"{len(filtered):,} of {len(df):,} addresses match")

# --- KPI row -----------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Addresses shown", f"{len(filtered):,}")
k2.metric("Mean options", f"{filtered[COUNT_COL].mean():.1f}" if len(filtered) else "-")
k3.metric("Median options", f"{filtered[COUNT_COL].median():.0f}" if len(filtered) else "-")
zero_pct = (filtered[COUNT_COL] == 0).mean() * 100 if len(filtered) else 0
k4.metric("Addresses with 0 options", f"{zero_pct:.1f}%")
k5.metric("Max options", f"{filtered[COUNT_COL].max():,}" if len(filtered) else "-")

if filtered.empty:
    st.warning("No addresses match the current filters.")
    st.stop()

vmax = max(filtered[COUNT_COL].quantile(0.95), 1)

tab_points, tab_hex, tab_district, tab_dist, tab_table = st.tabs(
    [
        "Individual Addresses",
        "Hex Density (H3)",
        "District Comparison",
        "Distribution",
        "Data Table",
    ]
)

with tab_points:
    st.subheader("Every residential postal code")
    st.caption(
        "Color: red = few/no nearby options, green = well served (scale capped "
        f"at the 95th percentile, {vmax:.0f} options, so a few very well-served "
        "outliers don't wash out the rest of the map). Bubble size also scales "
        "with the option count, clamped in screen pixels so bubbles stay legible "
        "and don't blanket the basemap as you zoom in."
    )
    plot_df = filtered.copy()
    plot_df["color"] = color_scale(plot_df[COUNT_COL], vmax)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plot_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_line_color=[60, 60, 60],
        get_radius=COUNT_COL,
        radius_scale=1,
        radius_min_pixels=2,
        radius_max_pixels=12,
        line_width_min_pixels=0.5,
        stroked=True,
        filled=True,
        pickable=True,
        opacity=0.55,
    )
    view_state = pdk.ViewState(
        latitude=float(plot_df["lat"].mean()),
        longitude=float(plot_df["lon"].mean()),
        zoom=10.5,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{address}\n{postal_code}\n{num_dining_options_within_1km_walk} options within 1km"},
        )
    )

with tab_hex:
    st.subheader("Density of dining access by hex cell")
    resolution = st.slider(
        "Hex resolution (higher = smaller, more granular hexes)",
        min_value=7,
        max_value=10,
        value=9,
    )
    hex_df = hex_aggregate(filtered, resolution)
    st.caption(
        f"{len(hex_df):,} hex cells. Color: red = low average nearby options, "
        "green = high average nearby options for addresses in that cell."
    )
    hex_vmax = max(hex_df["mean_options"].quantile(0.95), 1)
    hex_df = hex_df.copy()
    hex_df["color"] = color_scale(hex_df["mean_options"], hex_vmax)

    hex_layer = pdk.Layer(
        "H3HexagonLayer",
        data=hex_df,
        get_hexagon="h3_cell",
        get_fill_color="color",
        get_line_color=[80, 80, 80],
        line_width_min_pixels=1,
        pickable=True,
        opacity=0.6,
        extruded=False,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[hex_layer],
            initial_view_state=view_state,
            tooltip={"text": "Mean options: {mean_options}\nAddresses: {num_addresses}"},
        )
    )

with tab_district:
    st.subheader("Mean dining options by postal district")
    dist_agg = district_aggregate(filtered)
    if dist_agg.empty:
        st.info("No district data available for the current filter selection.")
    else:
        fig = px.bar(
            dist_agg,
            x="mean_options",
            y="district_label",
            orientation="h",
            color="mean_options",
            color_continuous_scale=["#d62728", "#2ca02c"],
            labels={"mean_options": "Mean options within 1km", "district_label": "District"},
            hover_data=["median_options", "num_addresses"],
        )
        fig.update_layout(height=700, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

        col_worst, col_best = st.columns(2)
        with col_worst:
            st.markdown("**5 least-served districts**")
            st.dataframe(
                dist_agg.head(5)[["district_label", "mean_options", "median_options", "num_addresses"]],
                hide_index=True,
            )
        with col_best:
            st.markdown("**5 best-served districts**")
            st.dataframe(
                dist_agg.tail(5)[["district_label", "mean_options", "median_options", "num_addresses"]]
                .sort_values("mean_options", ascending=False),
                hide_index=True,
            )

with tab_dist:
    st.subheader("Distribution of dining options across addresses")
    fig = px.histogram(
        filtered,
        x=COUNT_COL,
        nbins=min(int(filtered[COUNT_COL].max()) + 1, 60),
        labels={COUNT_COL: "Dining options within 1km"},
    )
    fig.update_layout(height=450, bargap=0.05)
    st.plotly_chart(fig, use_container_width=True)

with tab_table:
    st.subheader("Filtered data")
    display_cols = [
        "postal_code",
        "address",
        "district_label",
        COUNT_COL,
        "dining_option_names_within_1km_walk",
        "source",
        "lat",
        "lon",
    ]
    st.dataframe(filtered[display_cols], hide_index=True, use_container_width=True)
    st.download_button(
        "Download filtered CSV",
        data=filtered[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="accessibility_filtered.csv",
        mime="text/csv",
    )
