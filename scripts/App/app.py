#Import packages
from pathlib import Path, WindowsPath
import pandas as pd
import seaborn as sns
from shiny import App, render, req, ui

root_fldr = WindowsPath('C:/Users/agn25/OneDrive - Duke University/Documents/NowellWernerWoodruff')
raw_fldr = root_fldr / "data" / "raw"  
processed_fldr = root_fldr / "data" / "processed"

fire25_csv = processed_fldr / "fire25_2000.csv"

fire25 = pd.read_csv(fire25_csv)

fire25['ALARM_DATE'] = pd.to_datetime(
    fire25['ALARM_DATE'],
    format="%Y-%m-%d",
    errors="coerce"
)

fire25['CONT_DATE'] = pd.to_datetime(
    fire25['CONT_DATE'],
    format="%Y-%m-%d",
    errors="coerce"
)

fire25['YEAR'] = pd.to_numeric(fire25['YEAR'], errors='coerce')
fire25['GIS_ACRES'] = pd.to_numeric(fire25['GIS_ACRES'], errors='coerce')

fire25['DURATION'] = (
    fire25['CONT_DATE'] - fire25['ALARM_DATE']
).dt.total_seconds() / 3600

fire25['DURATION'] = pd.to_numeric(fire25['DURATION'], errors='coerce')

fire_rxburn_25_path = root_fldr / "data" / "processed" / "fire_rxburn_25.csv"

fire_rxburn = pd.read_csv(fire_rxburn_25_path)

fire_rxburn['ALARM_DATE'] = pd.to_datetime(fire_rxburn['ALARM_DATE'], format = '%Y-%m-%d')
fire_rxburn['CONT_DATE'] = pd.to_datetime(fire_rxburn['CONT_DATE'], format = '%Y-%m-%d')

fire_rxburn['duration'] = (
    fire_rxburn['CONT_DATE'] - fire_rxburn['ALARM_DATE']
).dt.total_seconds() / 3600
fire_rxburn['YEAR_'] = pd.to_numeric(fire_rxburn['YEAR_'], errors='coerce')
fire_rxburn['GIS_ACRES'] = pd.to_numeric(fire_rxburn['GIS_ACRES'], errors='coerce')
fire_rxburn['duration'] = pd.to_numeric(fire_rxburn['duration'], errors='coerce')


# Plot as a function (same function as in the notebook)
def plot_cause(start_date='2000',
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
                 .sort_values(by='mean_duration', ascending=False).reset_index()
)
    
    the_plot = sns.catplot(
        data=cause_summary,
        x='CAUSE',
        y= dropdown,
        palette='magma',
        alpha=0.7,
        aspect = 2,
        kind = 'bar'
    )

    # Set plot title and axis labels
    the_plot.set_axis_labels('CAUSE', dropdown)
    the_plot.set(title=f'{dropdown}')
    the_plot.set_xticklabels(rotation=60, ha='right')

    # Return the plot
    return the_plot

def plot_rxburn(start_date='2000',
                   end_date='2025',
                   dropdown='mean_area_burned'
                   ):
    # Subset the data
    df_subset = fire_rxburn.loc[
        (fire_rxburn['YEAR_'] >= start_date) &  # Start date (inclusive)
        (fire_rxburn['YEAR_'] <= end_date)    # End date (inclusive)   
        ]

    rx_summary = (df_subset.groupby(['rx_within_window'])
                 .agg(
                     count=('rx_within_window', 'count'),
                     mean_duration=('duration', 'mean'),
                     total_duration=('duration', 'sum'),
                     mean_area_burned=('GIS_ACRES', 'mean'),
                     total_area_burned=('GIS_ACRES', 'sum'),
                 )
                 .sort_values(by='mean_duration', ascending=False).reset_index()
)
    
    the_plot = sns.catplot(
        data=rx_summary,
        x='rx_within_window',
        y= dropdown,
        palette='magma',
        alpha=0.7,
        aspect = 2,
        kind = 'bar'
    )

    # Set plot title and axis labels
    the_plot.set_axis_labels('Prescribed Burn within a Year', dropdown)
    the_plot.set(title=f'{dropdown}')
    the_plot.set_xticklabels(rotation=60, ha='right')

    # Return the plot
    return the_plot

cause_list = fire25['CAUSE'].unique()
min_date = fire25['YEAR'].min()
max_date = fire25['YEAR'].max()
dropdown = ['mean_duration', 'total_duration', 'mean_area_burned', 'total_area_burned']

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h3('Causes of Fires in California'),
        ui.input_slider(
            'date_slider_cause', 'Date range:',
            min=min_date, max=max_date,
            value=(min_date, max_date),
        ),
        ui.input_select(
            'dropdown_cause', 'Area or Duration:',
            choices=list(dropdown),
            selected=dropdown[0],
        ),
    ),
        ui.h3('Pescribed Burn within a Year'),
        ui.input_slider(
            'date_slider_rx', 'Date range:',
            min=min_date, max=max_date,
            value=(min_date, max_date),
                ),
        ui.input_select(
            'dropdown_rx', 'Area or Duration:',
            choices=list(dropdown),
            selected=dropdown[0],
                ),
            
    ui.output_plot('cause_plot', height='550px'),
     
    ui.output_plot('rx_plot', height='550px'),
)

def server(input, output, session):
    @render.plot
    def cause_plot():

        g = plot_cause(
            start_date=int(input.date_slider_cause()[0]),
            end_date=int(input.date_slider_cause()[1]),
            dropdown=input.dropdown_cause(),
        )
        return g

    @render.plot
    def rx_plot():

        g = plot_rxburn(
            start_date=int(input.date_slider_rx()[0]),
            end_date=int(input.date_slider_rx()[1]),
            dropdown=input.dropdown_rx(),
        )
        return g

app = App(app_ui, server)