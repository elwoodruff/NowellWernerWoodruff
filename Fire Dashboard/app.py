# Import packages
from pathlib import Path, WindowsPath

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from shiny import App, reactive, render, ui

sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)

# ---------------------------------------------------------------- Data
root_fldr = Path(__file__).parent
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


# ----------------------------------------------------------------- UI
min_year = int(fire25["YEAR"].min())
max_year = int(fire25["YEAR"].max())

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h4("Causes of Fires"),
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
        ui.hr(),
        ui.h4("Prescribed Burns"),
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
        width=320,
    ),
    ui.layout_columns(
        ui.card(
            ui.card_header("Causes of Fires in California"),
            ui.output_plot("cause_plot", height="500px"),
            ui.h6("Summary by Cause", class_="mt-3"),
            ui.output_table("cause_table"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Prescribed Burn Within a Year"),
            ui.output_plot("rx_plot", height="500px"),
            ui.h6("Summary by Prescribed Burn", class_="mt-3"),
            ui.output_table("rx_table"),
            full_screen=True,
        ),
        col_widths=(12, 12),
    ),
    title="California Fire Dashboard",
    fillable=False,
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
            xlabel="Prescribed Burn Within Five Years",
            title=f"{METRIC_LABELS[metric]} by Prior Prescribed Burn, {int(start)}–{int(end)}",
        )

    @render.table
    def rx_table():
        return format_table(rx_df(), "rx_within_window", "Prescribed Burn Within Five Years")


app = App(app_ui, server)