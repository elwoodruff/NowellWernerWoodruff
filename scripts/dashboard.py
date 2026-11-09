#Import packages
from pathlib import Path
import pandas as pd
import seaborn as sns
from shiny import App, render, req, ui

root_fldr = Path.cwd().parent
raw_fldr = root_fldr / "data" / "raw"
processed_fldr = root_fldr / "data" / "processed"

fire25_csv = processed_fldr / "fire25_2000.csv"

fire25 = pd.read_csv(fire25_csv)

fire25['DURATION'] = (fire25['CONT_DATE'] - fire25['ALARM_DATE']).dt.total_seconds() / 3600

# Plot as a function (same function as in the notebook)
def plot_nutrients(start_date='2000',
                   end_date='2025',
                   dropdown='mean_area_burned'
                   ):
    # Subset the data
    df_subset = fire25.loc[
        (fire25['YEAR'] >= start_date) &  # Start date (inclusive)
        (fire25['YEAR'] <= end_date)    # End date (inclusive)   
        ]

    cause_summary = (df_subset.groupby(['CAUSE'])
                 .agg(
                     count=('CAUSE', 'count'),
                     mean_duration=('DURATION', 'mean'),
                     total_duration=('DURATION', 'sum'),
                     mean_area_burned=('GIS_ACRES', 'mean'),
                     total_area_burned=('GIS_ACRES', 'sum'),
                 )
                 .sort_values(by='mean_duration', ascending=False)
)
    # Create a plot of selected nutrients by sampledate, with markers
    # colored by depth_id and different shapes for lakename
    the_plot = sns.catplot(
        data=cause_summary,
        x='CAUSE',
        y= dropdown,
        palette='magma',
        alpha=0.7,
        aspect = 2
    )

    # Set plot title and axis labels
    the_plot.set_axis_labels('CAUSE', dropdown)
    the_plot.set(title=f'{dropdown}')
    the_plot.set_xticklabels(rotation=60, ha='right')

    # Clean up the legend
    sns.move_legend(
        the_plot,
        loc='center right',
        frameon=True,
    )

    # Return the plot
    return the_plot

cause_list = fire25['CAUSE'].unique()
min_date = fire25['YEAR'].min()
max_date = fire25['YEAR'].max()
dropdown = ['mean_duration', 'total_duration', 'mean_area_burned', 'total_area_burned']

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_slider(
            'date_slider', 'Date range:',
            min=min_date, max=max_date,
            value=(min_date, max_date),
        ),
        ui.input_select(
            'dropdown', 'Area or Duration:',
            choices=list(dropdown),
            selected=dropdown[0],
        ),
    ),
    ui.output_plot('cause_plot', height='550px'),
    title='Causes of Fires in California',
)

def server(input, output, session):
    @render.plot
    def cause_plot():
        # Don't attempt to plot if either multi-select has no selections.
        req(input.depth_zone_select(), input.lake_name_select())

        g = plot_nutrients(
            start_date=pd.Timestamp(input.date_slider()[0]),
            end_date=pd.Timestamp(input.date_slider()[1]),
            dropdown=input.dropdown(),
        )
        return g.figure

    app = App(app_ui, server)