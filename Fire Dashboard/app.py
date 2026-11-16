# Import packages
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from shiny import App, reactive, render, ui

sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)

# ---------------------------------------------------------------- Data
root_fldr = Path(__file__).parent
raw_fldr = root_fldr.parent / "data" / 'raw'
processed_fldr = root_fldr / "data" / "processed"

fire25 = pd.read_csv(processed_fldr / "fire25_2000.csv")
fire25["ALARM_DATE"] = pd.to_datetime(fire25["ALARM_DATE"], format="%Y-%m-%d", errors="coerce")
fire25["CONT_DATE"] = pd.to_datetime(fire25["CONT_DATE"], format="%Y-%m-%d", errors="coerce")
fire25["YEAR"] = pd.to_numeric(fire25["YEAR"], errors="coerce")
fire25["GIS_ACRES"] = pd.to_numeric(fire25["GIS_ACRES"], errors="coerce")
fire25["DURATION"] = (fire25["CONT_DATE"] - fire25["ALARM_DATE"]).dt.total_seconds() / 3600

fire_rxburn = pd.read_csv(processed_fldr / "fire_rxburn_25.csv")
fire_rxburn["ALARM_DATE"] = pd.to_datetime(fire_rxburn["ALARM_DATE"], format="%Y-%m-%d", errors="coerce")
fire_rxburn["CONT_DATE"] = pd.to_datetime(fire_rxburn["CONT_DATE"], format="%Y-%m-%d", errors="coerce")
fire_rxburn["YEAR_"] = pd.to_numeric(fire_rxburn["YEAR_"], errors="coerce")
fire_rxburn["GIS_ACRES"] = pd.to_numeric(fire_rxburn["GIS_ACRES"], errors="coerce")
fire_rxburn["duration"] = (fire_rxburn["CONT_DATE"] - fire_rxburn["ALARM_DATE"]).dt.total_seconds() / 3600

# Map layers (raw shapefiles live in the project's data/raw folder)

fire_gdf = gpd.read_file(raw_fldr / "fire25.zip")
rxburn_gdf = gpd.read_file(raw_fldr / "rxburn25.zip")

cause_lookup = pd.read_csv(raw_fldr / "fire_25_TD.csv", usecols=["CAUSE", "d_CAUSE"]).drop_duplicates().set_index("CAUSE")["d_CAUSE"]
fire_gdf["CAUSE"] = fire_gdf["CAUSE"].map(cause_lookup)
fire_gdf["DURATION_DAYS"] = (fire_gdf["CONT_DATE"] - fire_gdf["ALARM_DATE"]).dt.days

# Keep 2000+ and simplify shapes (100 m) so the map stays fast
fire_gdf = fire_gdf[fire_gdf["YEAR_"] >= 2000]
rxburn_gdf = rxburn_gdf[rxburn_gdf["YEAR_"] >= 2000]
fire_gdf["geometry"] = fire_gdf.geometry.simplify(100)
rxburn_gdf["geometry"] = rxburn_gdf.geometry.simplify(100)

# ------------------------------------------------------------- Labels
# Dictionary keys are the column names; values are what the user sees.
METRIC_LABELS = {
    "mean_duration": "Mean Duration (hours)",
    "total_duration": "Total Duration (hours)",
    "mean_area_burned": "Mean Area Burned (acres)",
    "total_area_burned": "Total Area Burned (acres)",
}
TABLE_LABELS = {"count": "Number of Fires", **METRIC_LABELS}

RX_LABELS = {"True": "Yes", "False": "No", "1": "Yes", "0": "No"}


# ---------------------------------------------------------- Summaries
def _summarize(df, group_col, duration_col, metric):
    """Grouped summary shared by the plots and the tables."""
    return (
        df.groupby(group_col)
        .agg(
            count=(group_col, "count"),
            mean_duration=(duration_col, "mean"),
            total_duration=(duration_col, "sum"),
            mean_area_burned=("GIS_ACRES", "mean"),
            total_area_burned=("GIS_ACRES", "sum"),
        )
        .sort_values(by=metric, ascending=False)
        .reset_index()
    )


def cause_summary(start_year, end_year, metric):
    df = fire25.loc[(fire25["YEAR"] >= start_year) & (fire25["YEAR"] <= end_year)]
    if df.empty:
        return df.iloc[0:0]
    summary = _summarize(df, "CAUSE", "DURATION", metric)
    summary["CAUSE"] = summary["CAUSE"].astype(str)
    return summary


def rx_summary(start_year, end_year, metric):
    df = fire_rxburn.loc[
        (fire_rxburn["YEAR_"] >= start_year) & (fire_rxburn["YEAR_"] <= end_year)
    ]
    if df.empty:
        return df.iloc[0:0]
    summary = _summarize(df, "rx_within_window", "duration", metric)
    summary["rx_within_window"] = summary["rx_within_window"].astype(str).replace(RX_LABELS)
    return summary


def format_table(summary, group_col, group_label):
    """Rename columns, then format numbers with thousands separators."""
    if summary.empty:
        return pd.DataFrame({"Message": ["No fires in the selected date range"]}).style.hide(axis="index")

    table = summary.rename(columns={group_col: group_label, **TABLE_LABELS})
    number_formats = {"Number of Fires": "{:,.0f}"}
    number_formats.update({label: "{:,.1f}" for label in METRIC_LABELS.values()})
    return (
        table.style.format(number_formats)
        .hide(axis="index")
        .set_table_attributes('class="table table-striped table-sm w-100"')
    )


# -------------------------------------------------------------- Plots
def _style_axes(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=12, labelpad=10)
    ax.set_ylabel(ylabel, fontsize=12, labelpad=10)
    ax.set_title(title, fontsize=15, fontweight="bold", loc="left", pad=14)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="x", visible=False)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    sns.despine(ax=ax, left=True)


def _empty_plot(message="No fires in the selected date range"):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=14, color="gray")
    ax.set_axis_off()
    return fig


def _summary_bar(summary, x, metric, xlabel, title):
    if summary.empty:
        return _empty_plot()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(
        data=summary, x=x, y=metric, hue=x,
        palette="magma", alpha=0.85, legend=False, ax=ax,
    )
    _style_axes(ax, xlabel, METRIC_LABELS[metric], title)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- Map
def make_fire_map(fires, rx, start_date, end_date, causes=None, show_fires=True, show_rx=True):
    start, end = pd.to_datetime(start_date), pd.to_datetime(end_date)
    fires = fires[fires["ALARM_DATE"].between(start, end)]
    rx = rx[rx["START_DATE"].between(start, end)]
    if causes is not None:
        fires = fires[fires["CAUSE"].isin(causes)]

    m = folium.Map(
        location=[37.2, -119.5], zoom_start=6,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
    )

    # Duration classes for the fire colors and the legend
    labels = ["Same day", "1-3 days", "4-7 days", "8-30 days", "Over 30 days", "Unknown"]
    colors = ["#fed976", "#feb24c", "#fd8d3c", "#e31a1c", "#800026", "#bdbdbd"]
    fires = fires.assign(DURATION=pd.cut(fires["DURATION_DAYS"], [-1, 0, 3, 7, 30, float("inf")], labels=labels[:-1])
                         .cat.add_categories("Unknown").fillna("Unknown"))

    legend = ""
    if show_fires:
        fires.explore(
            m=m, name="Fires", column="DURATION", cmap=colors, legend=False,
            tooltip=["FIRE_NAME", "CAUSE", "ALARM_DATE", "CONT_DATE", "DURATION_DAYS", "GIS_ACRES"],
        )
        legend += "<b>Fire duration</b>" + "".join(_legend_row(c, l) for l, c in zip(labels, colors))
    if show_rx:
        rx.explore(
            m=m, name="Prescribed burns", color="blue",
            tooltip=["TREATMENT1", "START_DATE", "END_DATE", "GIS_ACRES"],
        )
        legend += _legend_row("blue", "Prescribed burn")

    if legend:
        m.get_root().html.add_child(folium.Element(
            '<div style="position:fixed; bottom:30px; left:10px; z-index:9999; background:white; '
            'padding:8px 10px; border-radius:4px; font:12px sans-serif; box-shadow:0 0 4px rgba(0,0,0,.3)">'
            f"{legend}</div>"
        ))
    folium.LayerControl().add_to(m)
    return m


def _legend_row(color, label):
    return f'<div><span style="display:inline-block; width:12px; height:12px; margin-right:6px; background:{color}"></span>{label}</div>'


# ----------------------------------------------------------------- UI
min_year = int(fire25["YEAR"].min())
max_year = int(fire25["YEAR"].max())

map_causes = sorted(fire_gdf["CAUSE"].dropna().unique())
map_min_date = fire_gdf["ALARM_DATE"].min().date()
map_max_date = fire_gdf["ALARM_DATE"].max().date()

app_ui = ui.page_fluid(
    ui.h2("California Fire Dashboard", class_="my-3"),
    ui.layout_columns(
        ui.card(
            ui.card_header("Causes of Fires in California"),
            ui.layout_columns(
                ui.input_slider(
                    "date_slider_cause", "Year range:",
                    min=min_year, max=max_year,
                    value=(min_year, max_year),
                    step=1, sep="",  # sep="" removes the thousands comma
                ),
                ui.input_select(
                    "dropdown_cause", "Measure:",
                    choices=METRIC_LABELS,
                    selected="mean_area_burned",
                ),
                col_widths=(8, 4),
            ),
            ui.output_plot("cause_plot", height="500px"),
            ui.h6("Summary by Cause", class_="mt-3"),
            ui.output_table("cause_table"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Prescribed Burn Within 5 Years"),
            ui.layout_columns(
                ui.input_slider(
                    "date_slider_rx", "Year range:",
                    min=min_year, max=max_year,
                    value=(min_year, max_year),
                    step=1, sep="",
                ),
                ui.input_select(
                    "dropdown_rx", "Measure:",
                    choices=METRIC_LABELS,
                    selected="mean_area_burned",
                ),
                col_widths=(8, 4),
            ),
            ui.output_plot("rx_plot", height="500px"),
            ui.h6("Summary by Prescribed Burn", class_="mt-3"),
            ui.output_table("rx_table"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Fire Duration and Prescribed Burns Map"),
            ui.layout_columns(
                ui.input_date_range(
                    "map_dates", "Date range:",
                    start="2025-01-01", end=map_max_date,
                    min=map_min_date, max=map_max_date,
                ),
                ui.input_selectize(
                    "map_causes", "Fire cause:",
                    choices=map_causes, selected=map_causes, multiple=True,
                ),
                ui.div(
                    ui.input_checkbox("show_fires", "Show fires", value=True),
                    ui.input_checkbox("show_rx", "Show prescribed burns", value=True),
                ),
                col_widths=(3, 6, 3),
            ),
            ui.output_ui("fire_map"),
            full_screen=True,
        ),
        col_widths=(12, 12, 12),
    ),
    title="California Fire Dashboard",
)


# ------------------------------------------------------------- Server
def server(input, output, session):
    # Each summary is computed once and shared by its plot and its table.
    @reactive.calc
    def cause_df():
        start, end = input.date_slider_cause()
        return cause_summary(int(start), int(end), input.dropdown_cause())

    @reactive.calc
    def rx_df():
        start, end = input.date_slider_rx()
        return rx_summary(int(start), int(end), input.dropdown_rx())

    @render.plot
    def cause_plot():
        start, end = input.date_slider_cause()
        metric = input.dropdown_cause()
        return _summary_bar(
            cause_df(), "CAUSE", metric,
            xlabel="Cause",
            title=f"{METRIC_LABELS[metric]} by Cause, {int(start)}–{int(end)}",
        )

    @render.table
    def cause_table():
        return format_table(cause_df(), "CAUSE", "Cause")

    @render.plot
    def rx_plot():
        start, end = input.date_slider_rx()
        metric = input.dropdown_rx()
        return _summary_bar(
            rx_df(), "rx_within_window", metric,
            xlabel="Prescribed Burn Within 5 Years",
            title=f"{METRIC_LABELS[metric]} by Prior Prescribed Burn, {int(start)}–{int(end)}",
        )

    @render.table
    def rx_table():
        return format_table(rx_df(), "rx_within_window", "Prescribed Burn Within 5 Years")

    @render.ui
    def fire_map():
        start, end = input.map_dates()
        m = make_fire_map(
            fire_gdf, rxburn_gdf, start, end,
            causes=list(input.map_causes()),
            show_fires=input.show_fires(),
            show_rx=input.show_rx(),
        )
        return ui.HTML(m._repr_html_())


app = App(app_ui, server)