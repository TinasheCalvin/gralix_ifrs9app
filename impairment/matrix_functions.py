import numpy as np
import pandas as pd
import plotly.graph_objs as go
import plotly.offline as pyo
import plotly.express as px
import plotly.io as pio
from scipy.linalg import expm, logm


def multi_to_single(df: pd.DataFrame):
    dff = df.copy()
    dff["Loan Type"] = dff.index.get_level_values('Loan Segment')
    dff["Current Stage"] = dff.index.get_level_values('Current Stage')
    dff.reset_index(drop=True, inplace=True)
    
    columns_order = ['Loan Type', 'Current Stage'] + list(dff.columns[:-2])
    dff = dff.reindex(columns=columns_order)

    return dff


def base_matrices(df: pd.DataFrame) -> pd.DataFrame:
    """Create the base transition matrices. Assumes dataframe is output from 'data_prep()[0]' or 'merged_recoveries'. See data_validation.py
    
    Returns:
    - transition matrix dataframe containing PDs TMs for each loan segment.
    
    """

    df = df[df['next_stage'] != 'exit']

    matrices = pd.crosstab(index=[df['loan_type'], df['current_stage']],
                           columns=[df['next_stage']],
                           values=df['out_balance'],
                           rownames=['Loan Segment', 'Current Stage'],
                           colnames=['Next Stage'],
                           aggfunc="sum",
                           margins=False,
                           dropna=False,
                           normalize='index')
    return matrices



def convert_to_monthly_transition_matrix(matrix, period):
    """
    Convert a transition matrix from a given period to a monthly transition matrix.
    
    Parameters:
    matrix (np.array): Transition matrix for the given period.
    period (int): Period of the input matrix (1=monthly, 3=quarterly, 6=semi-annual, 12=annual).
    
    Returns:
    np.array: Monthly transition matrix.
    """
    if period == 1:
        # The input matrix is already monthly, no conversion needed
        return matrix
    
    log_matrix = logm(matrix)
    log_monthly_matrix = log_matrix / period
    monthly_matrix = expm(log_monthly_matrix)
    
    # Ensure no negative values and rows sum to 1
    monthly_matrix[monthly_matrix < 0] = 0
    monthly_matrix = monthly_matrix / monthly_matrix.sum(axis=1, keepdims=True)
    
    return monthly_matrix

def absorbing_state(matrices_df: pd.DataFrame, matrix_size: int = 3, period: int = 1) -> pd.DataFrame:
    """
    Convert the given transition matrices for each loan segment to monthly matrices and ensure absorbing states.
    
    Parameters:
    matrices_df (pd.DataFrame): DataFrame containing the transition matrices for each loan segment.
    matrix_size (int): Size of the transition matrices (3 or 4).
    period (int): Period of the input matrices (1=monthly, 3=quarterly, 6=semi-annual, 12=annual).
    
    Returns:
    pd.DataFrame: DataFrame containing the monthly transition matrices with absorbing states.
    """
    if matrix_size not in {3, 4}:
        raise ValueError("Invalid matrix size. Should be 3 or 4 only.")
    
    matrices_df = matrices_df.copy()
    if matrix_size == 3:
        for loan_segment in matrices_df.index.get_level_values('Loan Segment').unique():
            matrices_df.loc[(loan_segment, 'stage_3'), :] = (0, 0, 1)

    elif matrix_size == 4:
        for loan_segment in matrices_df.index.get_level_values('Loan Segment').unique():
            matrices_df.loc[(loan_segment, 'stage_3'), :] = (0, 0, 0, 1)

    loan_segments = matrices_df.index.get_level_values('Loan Segment').unique()
    matrices_df_monthly = pd.DataFrame()

    for segment in loan_segments:
        segment_matrix = matrices_df.loc[segment].values
        monthly_matrix = convert_to_monthly_transition_matrix(segment_matrix, period)
        monthly_matrix_df = pd.DataFrame(monthly_matrix, index=matrices_df.loc[segment].index, columns=matrices_df.loc[segment].columns)
        monthly_matrix_df['Loan Segment'] = segment
        matrices_df_monthly = pd.concat([matrices_df_monthly, monthly_matrix_df])

    matrices_df_monthly.set_index('Loan Segment', append=True, inplace=True)
    matrices_df_monthly = matrices_df_monthly.reorder_levels(['Loan Segment', 'Current Stage'])

    return matrices_df_monthly


def extract_pds(matrices_df: pd.DataFrame, matrix_size: int = 3, mult_len: int = 300) -> tuple:
    """Extract the probabilities of default from the provided transition matrix dataframe.

    Parameters:
    - matrices_df: MultiIndex dataframe containing cumulative pds for each loan segment -> Output from 'absorbing_state()'
    - matrix_size: Integer value representing size of the transition matrix.
    - mult_len: Number of n-step transitions to generate
    
    Returns:
    - tuple of cumulative and marginal PDs dataframes.
    """

    if matrix_size not in {3, 4}:
        raise ValueError("Invalid matrix size. Should be 3 or 4 only")

    stage_dicts = {stage: {"cumulative_dict": {}, "marginal_dict": {}} for stage in range(matrix_size - 1)}
    loan_segments = matrices_df.index.get_level_values('Loan Segment').unique()

    for loan_segment in loan_segments:
        transition_matrix = matrices_df.loc[loan_segment].to_numpy()

        for stage in range(matrix_size - 1):
            if stage == 0:
                cumulative_pds = np.array([np.linalg.matrix_power(transition_matrix, i)[stage, matrix_size - 1] for i in range(1, 13)])
            else:
                cumulative_pds = np.array([np.linalg.matrix_power(transition_matrix, i)[stage, matrix_size - 1] for i in range(1, mult_len)])

            marginal_pds = np.diff(np.insert(cumulative_pds, 0, 0))

            stage_dicts[stage]['cumulative_dict'][loan_segment] = cumulative_pds
            stage_dicts[stage]['marginal_dict'][loan_segment] = marginal_pds

    df_cumulative = {f"non-default-{stage}-cumulative": pd.DataFrame(stage_dicts[stage]['cumulative_dict']).applymap(lambda x: f"{x:.8f}") for stage in stage_dicts.keys()}
    df_marginal = {f"non-default-{stage}-marginal": pd.DataFrame(stage_dicts[stage]['marginal_dict']).applymap(lambda x: f"{x:.8f}") for stage in stage_dicts.keys()}

    return tuple(df_marginal.values()) + tuple(df_cumulative.values())


def cure_rate(df: pd.DataFrame, mult_len: int = 300, period: int = 1) -> tuple:
    cure_rates_dict = {}
    recovery_rates_dict = {}

    df.sort_values(by='loan_type', inplace=True)
    loan_segments = df['loan_type'].unique()
    discounted_recoveries_exist = 'discounted_recoveries' in df.columns

    for loan_segment in loan_segments:
        dff = df[df["loan_type"] == loan_segment]
        cr_rr = np.identity(3)

        if discounted_recoveries_exist:
            recoveries = dff.groupby('recoveries')[['out_balance', 'discounted_recoveries']].sum()
            cr_rr[2, 0] = recoveries['out_balance'].get('cured', 0)
            cr_rr[2, 1] = recoveries['discounted_recoveries'].get('recovered', 0)
            cr_rr[2, 2] = recoveries['out_balance'].get('stage_3', 0)
        else:
            cures = dff.groupby("cures")['out_balance'].sum()
            cr_rr[2, 0] = cures.get("cured", 0)
            cr_rr[2, 1] = dff['exit_recoveries'].sum() + dff['cash_recoveries'].sum()
            cr_rr[2, 2] = cures.get('stage_3', 0)

        cr_rr = cr_rr / cr_rr.sum(axis=1, keepdims=1)

        monthly_cr_rr = convert_to_monthly_transition_matrix(cr_rr, period)

        cumulative_cure_rate = np.array([np.linalg.matrix_power(monthly_cr_rr, i)[2, 0] for i in range(1, mult_len)])
        cumulative_recovery_rate = np.array([np.linalg.matrix_power(monthly_cr_rr, i)[2, 1] for i in range(1, mult_len)])

        cure_rates = np.diff(np.insert(cumulative_cure_rate, 0, 0))
        recovery_rates = np.diff(np.insert(cumulative_recovery_rate, 0, 0))

        cure_rates_dict[loan_segment] = cure_rates
        recovery_rates_dict[loan_segment] = recovery_rates

    cure_df = pd.DataFrame(cure_rates_dict).fillna(0).applymap(lambda x: f"{x:.8f}")
    recovery_df = pd.DataFrame(recovery_rates_dict).fillna(0).applymap(lambda x: f"{x:.8f}") if recovery_rates_dict else None

    return cure_df, recovery_df


def plot_rates(df: pd.DataFrame, name_of_file: str, main_title: str='Title', x_title: str='Time Period - Quarters', y_title: str='Probability of Default', x_range: int=100 ):
    """
    Function to plot the dataframe passed to it. Designed for plotting cumulative and marginal PDs as well as cure and recovery rates per loan segment.

    """
    df = df.head(x_range)
    data = [go.Scatter(x=df.index,
                    y=df[col],
                    mode='lines',
                    name=col) for col in df.columns]

    layout = go.Layout(title=main_title,
                    xaxis=dict(title=x_title),
                    yaxis=dict(title="Probability of Default"),
                    hovermode="closest")

    fig = go.Figure(data=data, layout=layout)
    
    return pyo.plot(fig, filename=name_of_file)  # change between iplot and plot for embedded notebook plotting vs online plotting
    # return fig


def plot_rates_px(df, main_title='Title', x_title='Time Period - Months', y_title='Probability of Default', x_range=100):
    """
    Function to plot the dataframe passed to it. Designed for plotting cumulative and marginal PDs as well as cure and recovery rates per loan segment.

    """
    df = df.head(x_range)
    
    # Check if index name is None, if so, assign a default name
    index_name = df.index.name if df.index.name is not None else 'index'
    
    # Reshape DataFrame into long format
    df_long = pd.melt(df.reset_index(), id_vars=index_name, var_name='Loan Segment', value_name='Value')
    
    fig = px.line(df_long, x=index_name, y='Value', color='Loan Segment',
                  title=main_title,
                  labels={index_name: x_title, 'Value': y_title, 'Loan Segment': 'Loan Segment'},
                  hover_name='Loan Segment')

    fig.update_layout(xaxis_title=x_title, yaxis_title=y_title)
    fig.update_traces(mode='lines+markers')

    return fig


def save_plot_as_image(df, plot_func, image_file='plot_image.png'):
    """
    Function to generate a plot and save it as an image file.
    
    Parameters:
    - df: pd.DataFrame - DataFrame containing the data to be plotted.
    - plot_func: function - Function that generates the plot.
    - image_file: str - The name of the image file to be created.
    """
    # Generate the plot
    fig = plot_func(df)
    
    # Save the plot as an image
    pio.write_image(fig, image_file)
    print(f'Plot saved as {image_file}')
