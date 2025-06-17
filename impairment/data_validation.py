import numpy as np
import pandas as pd
from datetime import datetime
from functools import partial


def extract_null(my_df: pd.DataFrame) -> pd.DataFrame:
    """Extracts rows will any null values from a dataframe and creates a df of these values."""
    blanks = []
    for col in my_df.columns:
        blank_df = my_df[my_df[col].isna()]
        blanks.append(blank_df)
    df = pd.concat(blanks).drop_duplicates()
    return df


def clean_dataframe(df: pd.DataFrame) -> tuple:
    """Cleans the dataframe provided. Tailored to the expected data input file for historical PD data."""
    for col in df.columns:
        df[col].astype(str)

    for col in df.columns:
        if "Unnamed" in col:
            df = df.drop(col, axis=1)

    pre_data = df.copy()

    # convert date column to datetime where possible
    df["current_date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    # convert dates if format type is excel day counts
    mask = pd.to_numeric(df["date"], errors="coerce").notna()
    df.loc[mask, "current_date"] = pd.to_datetime(df["date"][mask].astype(float), errors="coerce", unit="D", origin="1899-12-30")

    df["out_balance"] = (df["out_balance"].astype(str).str.replace("(", "-").str.replace(r"[^0-9.-]", "", regex=True))
    df["days_past_due"] = (df["days_past_due"].astype(str).str.replace("(", "-").str.replace(r"[^0-9.-]", "", regex=True))

    df["out_balance"] = pd.to_numeric(df["out_balance"], errors="coerce")
    df["days_past_due"] = pd.to_numeric(df["days_past_due"], errors="coerce")

    # Identify and drop rows with errors
    bad_data = extract_null(df)

    # Concatenate all error DataFrames
    error_df = pre_data[pre_data.index.isin(bad_data.index)].copy()
    error_df.loc[:, "REFERENCE"] = error_df.index + 2
    error_df = error_df.sort_index()

    # Drop rows with errors
    clean_df = df.drop(error_df.index, axis=0).reset_index(drop=True)

    return clean_df, error_df


def date_cleaner(df: pd.DataFrame, old_column: str, new_column: str) -> pd.DataFrame:
    """Cleans a date column with mixed types and unifies format. Creates a new column for the dates"""
    df[new_column] = pd.to_datetime(df[old_column], errors="coerce", dayfirst=True, format="%d/%m/%Y")  # try date coercion
    # Coerce date if given in day count format
    mask = pd.to_numeric(df[old_column], errors="coerce").notna()
    df.loc[mask, new_column] = pd.to_datetime(df[old_column][mask].astype(float), errors="coerce", unit="D", origin="1899-12-30")
    return df


def clean_recoveries(my_df: pd.DataFrame) -> tuple:
    for col in my_df.columns:
        my_df[col].astype(str)

    for col in my_df.columns:
        if "Unnamed" in col:
            my_df = my_df.drop(col, axis=1)

    pre_data = my_df.copy()

    date_cleaner(my_df, "date", "current_date")
    date_cleaner(my_df, "default_date", "current_default_date")
    date_cleaner(my_df, "recovery_date", "current_recovery_date")

    my_df["cash_collections"] = (my_df["cash_collections"].astype(str).str.replace("(", "-").str.replace(r"[^0-9.-]", "", regex=True))
    my_df["cash_collections"] = pd.to_numeric(my_df["cash_collections"], errors="coerce")

    my_df["eir"] = (my_df["eir"].astype(str).str.replace("(", "-").str.replace(r"[^0-9.-]", "", regex=True))
    my_df["eir"] = pd.to_numeric(my_df["eir"], errors="coerce")

    # Identify and drop rows with errors
    bad_data = extract_null(my_df)

    # Concatenate all error DataFrames
    error_df = pre_data[pre_data.index.isin(bad_data.index)].copy()
    error_df.loc[:, "REFERENCE"] = error_df.index + 2
    error_df = error_df.sort_index()

    # Drop rows with errors
    clean_df = my_df.drop(error_df.index, axis=0).reset_index(drop=True)

    return clean_df, error_df


def staging_map(dpd: int, matrix_size: int) -> int:
    """Assigns IFRS 9 Staging to loan facility based on Days Past Due value.

    Parameters:
    - dpd: Days Past Due value
    - matrix_size: Integer value representing the size of the transition matrix (3 or 4)

    Returns:
    - Staging category

    """

    if matrix_size not in {3, 4}:
        raise ValueError("Invalid matrix size. Should be 3 or 4 only")

    if dpd <= 30:
        stage = "stage_1"
    elif dpd <= 60 and matrix_size == 4:
        stage = "stage_2a"
    elif dpd <= 90:
        stage = "stage_2" if matrix_size == 3 else "stage_2b"
    else:
        stage = "stage_3"
    return stage


def map_lookup(df: pd.DataFrame, value_column: str, search_columm: str, return_column: str, value_not_found: str = None, new_column_name="lookup_result") -> pd.DataFrame:
    """
    Search for 'value column' in 'search column' and return the 'return column'. Ensure no duplicates in 'search_column'.
    Function imitates Excel's XLOOKUP funtion.
    """
    df[new_column_name] = (df[value_column].map(df.set_index(search_columm)[return_column]).fillna(value_not_found))
    return df


def closest_period(avg_months):
    periods = [1, 3, 6, 12]
    closest = min(periods, key=lambda x: abs(x - avg_months))
    return closest

def data_prep(data: pd.DataFrame, matrix_size: int = 3, valuation_date=pd.to_datetime('today')) -> tuple:
    """Prepares the dataframe for creation of transition matrices. Period is used to set the offset amount i.e., monthly, quarterly or annual

    Parameters:
    - data: dataframe containing historical default information.
    - matrix_size: the size of the transition matrix (3 or 4).

    Returns:
    - tuple: containing 3 dataframe objects, cleaned PD data, error data and duplicate ID files
    """
    if matrix_size not in {3, 4}:
        raise ValueError("Invalid matrix size selected. Matrix size must be 3 or 4.")
    
    pd_data, error_data = clean_dataframe(data)  # clean data

    pd_data = pd_data.sort_values(by="current_date")  # sort values in ascending order by date

    # Calculate average lag between successive unique dates
    unique_dates = pd_data["current_date"].drop_duplicates().sort_values()
    date_diffs = unique_dates.diff().dropna().dt.days
    avg_days = date_diffs.mean()
    avg_months = avg_days / 30.44  # approximate average number of days in a month

    period = closest_period(avg_months)
    
    pd_data["current_id"] = (pd_data["current_date"].astype(str) + "_" + pd_data["account_no"].astype(str))  # create unique identifier

    duplicate_id = pd_data[pd_data.duplicated(subset="current_id", keep="first")]

    pd_data = pd_data.drop_duplicates(subset="current_id", keep="first").reset_index(drop=True)  # drop duplicates to ensure identifier is unique

    pd_data["next_date"] = pd_data["current_date"] + pd.offsets.MonthEnd(period)  # create next date by offsetting by 'period' number of months

    pd_data["next_id"] = (pd_data["next_date"].astype(str) + "_" + pd_data["account_no"].astype(str))  # create next_id - unique id for next period

    staging_map_partial = partial(staging_map, matrix_size = matrix_size)
    pd_data["current_stage"] = pd_data["days_past_due"].map(staging_map_partial)  # map dpd to staging

    map_lookup(pd_data, "next_id", "current_id", "current_stage", "exit", "next_stage")  # create next_stage based on map_lookup funtion

    if matrix_size == 3:
        conditions = ((pd_data["current_stage"] == "stage_3") & ((pd_data["next_stage"] == "stage_1") | (pd_data["next_stage"] == "stage_2")))
    if matrix_size == 4:
        conditions = ((pd_data["current_stage"] == "stage_3") & ((pd_data["next_stage"] == "stage_1") | (pd_data["next_stage"] == "stage_2a") | (pd_data["next_stage"] == "stage_2b")))

    pd_data["cures"] = np.where(conditions, "cured", pd_data["next_stage"])

    map_lookup(pd_data, 'next_id', 'current_id', 'out_balance', 0.0, 'next_value')

    conditions_1 = ((pd_data['current_stage'] == 'stage_3') & (pd_data['next_stage'] == 'exit') & (pd_data['current_date'] != max(pd_data['current_date'])))
    conditions_2 = ((pd_data['current_stage'] == 'stage_3') & (pd_data['next_stage'] == 'stage_3') & (pd_data['next_value'] < pd_data['out_balance']))

    pd_data['exit_recoveries'] = np.where(conditions_1, pd_data['out_balance'], 0.0)
    pd_data['cash_recoveries'] = np.where(conditions_2, pd_data['out_balance'] - pd_data['next_value'], 0.0)

    pd_data = pd_data[pd_data['current_date'] < pd.to_datetime(valuation_date)]

    return pd_data, period


def recoveries_prep(data: pd.DataFrame) -> tuple:
    """Prepares the dataframe for creation of transition matrices for recoveries. Period is used to set the offset amount i.e., monthly, quarterly or annual"""

    recoveries_data, error_data = clean_recoveries(data)  # clean recoveries data

    recoveries_data["current_id"] = (recoveries_data["current_date"].astype(str) + "_" + recoveries_data["account_no"].astype(str))  # create unique identifier

    unique_dates = recoveries_data["current_date"].drop_duplicates().sort_values()
    date_diffs = unique_dates.diff().dropna().dt.days
    avg_days = date_diffs.mean()
    avg_months = avg_days / 30.44  # approximate average number of days in a month

    period = closest_period(avg_months)

    recoveries_data["next_date"] = recoveries_data["current_date"] + pd.offsets.MonthEnd(period)  # create next_date by offsetting by period number of months

    recoveries_data["next_id"] = (recoveries_data["next_date"].astype(str) + "_" + recoveries_data["account_no"].astype(str))  # create next_id

    recoveries_data["time_in_default"] = (recoveries_data["current_recovery_date"] - recoveries_data["current_default_date"]).dt.days / 365.25  # time in default in years

    recoveries_data["discounted_recoveries"] = recoveries_data["cash_collections"] * ((1 + recoveries_data["eir"]) ** (-recoveries_data["time_in_default"]))

    discounted_cash_recoveries = (recoveries_data.groupby("current_id")["discounted_recoveries"].sum().reset_index())

    return discounted_cash_recoveries, period


def merge_recoveries(pd_df: pd.DataFrame, recoveries_df: pd.DataFrame, valuation_date=pd.to_datetime('today').normalize()) -> pd.DataFrame:
    """Merge the historical pd dataframe with the recoveries dataframe and identify recoveries. Determine cures, recoveries and exits"""

    final_df = pd.merge(pd_df, recoveries_df, on="current_id", how="left")

    final_df["discounted_recoveries"] = final_df["discounted_recoveries"].fillna(0.0)

    cond_1 = ((final_df["current_stage"] == "stage_3") & (final_df["cures"] != "cured") & (final_df["discounted_recoveries"] > 0))

    final_df["recoveries"] = np.where(cond_1, "recovered", final_df["cures"])

    cond_2 = ((final_df["current_stage"] == "stage_3") & (final_df["cures"] == "cured"))

    final_df["cure_num"] = np.where(cond_2, final_df["out_balance"], 0)

    cond_3 = ((final_df["current_stage"] == "stage_3") & (final_df["recoveries"] == "recovered"))

    final_df["rec_num"] = np.where(cond_3, final_df["discounted_recoveries"], 0)

    cond_4 = (final_df["current_stage"] == "stage_3")

    final_df["denom"] = np.where(cond_4, final_df["out_balance"], 0)

    cond_5 = ((final_df["current_stage"] == "stage_3") & (final_df["recoveries"] == "exit"))

    final_df["denom_exit"] = np.where(cond_5, final_df["out_balance"], 0)

    cond_6 = ((final_df["current_stage"] == "stage_3") & (final_df["recoveries"] == "stage_3")) 

    final_df["no_transition"] = np.where(cond_6, final_df["out_balance"], 0)

    final_df = final_df[final_df["current_date"] < pd.to_datetime(valuation_date)]

    return final_df

def add_dates(df: pd.DataFrame, date=datetime(2023, 12, 31), offset: int=1):
    """
    Function to add a date column to a dataframe starting at the valuation date
    """

    def date_off(n: int):
        nonlocal date
        fin_date = date + pd.offsets.MonthEnd((1+n)*offset)
        return fin_date

    df.index = pd.to_numeric(df.index, errors='coerce')
    df["DATE"] = (df.index).map(date_off)
    df['DATE'] = pd.to_datetime(df['DATE'])  # Convert 'DATE' column to datetime format
    df['DATE'] = df['DATE'].dt.strftime('%d-%m-%Y')
    col_order = ["DATE"] + list(df.columns[:-1])
    df = df.reindex(columns=col_order)
    return df

