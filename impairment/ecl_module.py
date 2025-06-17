import numpy_financial as npf
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.optimize import brentq
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go


class ExposureAtDefault():

    def __init__(
            self,
            valuation_date,
            account_number,
            customer_id,
            disbursement_date, 
            maturity_date,
            loan_type: str,
            disbursed_amount: float, 
            outstanding_balance: float,
            interest_rate: float, 
            dpd: int,            
            payment_frequency: int,
            building: float=0,
            land: float=0,
            bond: float=0,
            motor_vehicle: float=0,
            cash: float=0,
            equity: float=0,
            other: float=0,
            matrix_size: int=3) -> None:
        """ 
        Returns an ExposureAtDefault object based on the input parameters. 
        Designed to be used to map a loan book and determine term attributes for determination of IFRS 9 Exposure at Default.

        Parameters:

        - disbursed_amount: The initial principal loan amount
        - outstanding_balance: The balance outstanding at the reporting date
        - disbursement_date: The date of loan disbursement
        - maturity_date: The expected maturity date of the loan
        - dpd: The number of days since the loan payment fell due. Used to determine the stage of the loan based on IFRS 9 default criteria
        - loan_type: The type of loan i.e., Mortgage, Asset Finance, Staff Loan etc
        - interest_rate: The annual interest rate
        - payment_frequency: The number of payments expected in a year
        - valuation_date: The date at which the ECL is being computed
        - matrix_size: Assumes a Transition matrix approach has been used in the PD model. 
        The matrix size from the PD model is used here in conjunction with the dpd to assign the IFRS 9 stage. 

        """
        
        """EAD Parameters:"""
        self.valuation_date = pd.to_datetime(valuation_date, dayfirst=True).tz_localize(None)
        self.account_number = str(account_number)
        self.customer_id = str(customer_id)
        self.disbursed_amount = float(disbursed_amount)
        self.outstanding_balance = float(outstanding_balance)
        self.disbursement_date = pd.to_datetime(disbursement_date, dayfirst=True).tz_localize(None)
        self.maturity_date = pd.to_datetime(maturity_date).tz_localize(None) if pd.to_datetime(maturity_date).tz_localize(None) > self.valuation_date else pd.to_datetime(valuation_date).tz_localize(None) + pd.offsets.MonthEnd(12)
        self.dpd = int(dpd)
        self.loan_type = loan_type
        self.interest_rate = float(interest_rate)
        self.payment_frequency = max(12, int(payment_frequency))
        self.matrix_size = matrix_size
        self.fees = 0.0
        self.periodic_rate = self.interest_rate / self.payment_frequency
        self.duration = (self.maturity_date - self.valuation_date).days / 365.25
        self.total_duration = (self.maturity_date - self.disbursement_date).days / 365.25
        self.num_payments = round(self.payment_frequency * self.duration) if round(self.payment_frequency * self.duration) >= 1 else 1
        self.total_num_payments = round(self.payment_frequency * self.total_duration)
        self.stage = self.staging_map(self.dpd, self.matrix_size)
        self.pthly_payment = abs(round(npf.pmt(rate=self.periodic_rate, nper=self.total_num_payments, pv=self.disbursed_amount), 2))
        self.eir = self.interest_rate
        # try:
        #     self.eir = brentq(lambda x: self.pthly_payment * ((1 - (1 + x) ** - self.total_num_payments) / x) - (self.disbursed_amount - self.fees), 0.00001, 0.99999) * self.payment_frequency
        # except ValueError:
        #     self.eir = self.interest_rate

        if self.payment_frequency not in set(range(0, 13)):
            raise ValueError("Payment Frequency must be integer value between 1 and 12")
    
        """LGD Parameters:"""
        self.building = building
        self.land = land
        self.bond = bond
        self.motor_vehicle = motor_vehicle
        self.cash = cash
        self.equity = equity
        self.other = other


    def staging_map(self, dpd: int, matrix_size: int) -> int:
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

    @property
    def amortization(self) -> pd.DataFrame:
        """Create a loan amortization schedule for a given loan

        Returns:
        - amortization_schedule: DataFrame object containing the term structures for the Repayment Amount, Interest, Principal and Outstanding Balance
        
        """

        loan_amount = self.outstanding_balance
        start_date = self.valuation_date
        
        schedule_date = [start_date]
        amortization_schedule = [loan_amount]
        principal_schedule = [0]
        interest_schedule = [0]
        payment_schedule = [0]
        payment = abs(round(npf.pmt(rate=self.periodic_rate, nper=self.num_payments, pv=loan_amount), 2))
        counter = 1
        amount = loan_amount
        max_counts = None
        if self.stage == 'stage_1':
            max_counts = min(12, self.num_payments)
        elif self.stage == 'stage_2':
            max_counts = self.num_payments
        else:
            max_counts = 1
        
        while (round(amount, 0) > 0) and (counter <= max_counts):

            if payment > amount:
                payment = round(amount * (1+self.periodic_rate), 2) + 0.001

            start_date += pd.offsets.MonthEnd(1)
            schedule_date.append(start_date)

            payment_schedule.append(payment) if not counter % int(12/self.payment_frequency) else payment_schedule.append(0)

            interest = round(amount * (self.periodic_rate), 2)
            interest_schedule.append(interest)

            principal = round(payment - interest, 2) if not counter % int(12/self.payment_frequency) else 0
            principal_schedule.append(principal)

            amount = round(amount * (1+self.periodic_rate) - payment, 2) if not counter % int(12/self.payment_frequency) else round(amount * (1+self.periodic_rate), 2)
            amortization_schedule.append(amount)

            counter +=1

        schedule_fin = pd.DataFrame({
            'Expected Date': schedule_date[:-1],
            'EAD (Out Bal.)': amortization_schedule[:-1],
            'Payment': payment_schedule[:-1],
            'Interest': interest_schedule[:-1],
            'Principal': principal_schedule[:-1],
            'Loan Type': self.loan_type,
            'Effective Interest Rate': self.eir})
        
        return schedule_fin

 

class LossGivenDefault():
    
    def __init__(self, exposure:ExposureAtDefault, cure_rate:pd.DataFrame, recovery_rate:pd.DataFrame=None) -> None:
        self.exposure = exposure
        self.stage = self.exposure.stage
        self.cure_rate = cure_rate[self.exposure.loan_type]
        self.recovery_rate = recovery_rate[self.exposure.loan_type] if recovery_rate is not None else None
        
        self.max_amort_length = min(self.exposure.amortization.shape[0], self.cure_rate.shape[0])

        if self.stage == 'stage_1':
            self.ead = self.exposure.amortization['EAD (Out Bal.)'].iloc[0:min(12, self.max_amort_length)]
        elif self.stage == 'stage_3':
            self.ead = self.exposure.amortization['EAD (Out Bal.)'].iloc[0]
        else:
            self.ead = self.exposure.amortization['EAD (Out Bal.)'].iloc[0:self.max_amort_length]

        self.expected_dates = self.exposure.amortization['Expected Date'].iloc[0] if np.isscalar(self.ead) else self.exposure.amortization['Expected Date'].iloc[0:len(self.ead)]

        collateral_dict = {
            "building": self.exposure.building, 
            "land": self.exposure.land, 
            "bond": self.exposure.bond, 
            "motor_vehicle": self.exposure.motor_vehicle, 
            "cash": self.exposure.cash, 
            "equity": self.exposure.equity, 
            "other": self.exposure.other,
        }

        collateral_params = {
            "collateral_type": ['building', 'land', 'bond', 'motor_vehicle', 'cash', 'equity', 'other'],
            "time_to_realization_months": [3, 15, 3, 3, 0, 4, 6],
            "haircut": [0.20, 0.35, 0, 0.15, 0, 0.05, 0.15],
            "cost_of_recovery": [0.03, 0.05, 0.01, 0.03, 0.01, 0.015, 0.05] 
        }

        collateral_parameters = pd.DataFrame(collateral_params)
        collateral_parameters.set_index('collateral_type', inplace=True)
        self.collateral_parameters = collateral_parameters

        self.dcv_schedule = pd.DataFrame(self.dcv_loan(collateral_dict, self.collateral_parameters), index=[0])
        self.total_dcv = self.dcv_schedule['total_dcv'].iloc[0]

        # Handle NaN in self.total_dcv by replacing it with zero
        if pd.isna(self.total_dcv):
            self.total_dcv = 0.0

    def dcv_loan(self, collateral_dict, df_params):
        DCV = {}
        for collateral_type, collateral_value in collateral_dict.items():
            if not np.isnan(collateral_value):
                dcv = collateral_value * (1 - df_params.loc[collateral_type]['haircut']) * (1 + self.exposure.eir) ** (-df_params.loc[collateral_type]['time_to_realization_months']/12) - (df_params.loc[collateral_type]['cost_of_recovery'] * collateral_value)
                DCV[collateral_type] = dcv
        DCV["total_dcv"] = sum(DCV.values())
        return DCV

    @property
    def lgd_schedule(self):
        epsilon = 1e-5
        try:
            if self.recovery_rate is not None:
                lgd = ((self.ead - self.total_dcv) / (self.ead + epsilon)) * (1 - self.cure_rate.iloc[0:len(self.ead)]) * (1 - self.recovery_rate.iloc[0:len(self.ead)])
            else:
                lgd = ((self.ead - self.total_dcv) / (self.ead + epsilon)) * (1 - self.cure_rate.iloc[0:len(self.ead)])
            lgd = lgd.clip(0, 1)
            lgd_df = pd.DataFrame({
                "Expected Date": self.expected_dates, 
                "LGD": lgd,
                "Cure Rate": self.cure_rate.iloc[0:len(self.ead)].values,
                "Recovery Rate": self.recovery_rate.iloc[0:len(self.ead)].values if self.recovery_rate is not None else np.nan,
                "Total DCV": self.total_dcv,
            }, index=range(0, len(self.ead)))
        except (TypeError, AttributeError) as e:
            if self.recovery_rate is not None:
                lgd = ((self.ead - self.total_dcv) / (self.ead + epsilon)) * (1 - self.cure_rate.iloc[0]) * (1 - self.recovery_rate.iloc[0])
            else:
                lgd = ((self.ead - self.total_dcv) / (self.ead + epsilon)) * (1 - self.cure_rate.iloc[0])
            lgd = lgd.clip(0, 1)
            lgd_df = pd.DataFrame({
                "Expected Date": self.expected_dates, 
                "LGD": lgd,
                "Cure Rate": [self.cure_rate.iloc[0]],
                "Recovery Rate": [self.recovery_rate.iloc[0]] if self.recovery_rate is not None else [np.nan],
                "Total DCV": [self.total_dcv],
            }, index=[0])

        return lgd_df


def create_ead_instance(row):
    return ExposureAtDefault(
        valuation_date=pd.to_datetime(row['report_date'], dayfirst=True),
        account_number=row['account_no'],
        customer_id=row['client_id'],
        disbursement_date=pd.to_datetime(row['disbursement_date'], dayfirst=True),
        maturity_date=pd.to_datetime(row['maturity_date'], dayfirst=True),
        loan_type=str(row['loan_type']),
        disbursed_amount=float(row['disbursed_amount']),
        outstanding_balance=float(row['outstanding_balance']),
        interest_rate=float(row['interest_rate']),
        dpd=int(row['days_past_due']),
        payment_frequency=int(row['frequency']),
        building=float(row['building']),
        land=float(row['land']),
        bond=float(row['bond']),
        motor_vehicle=float(row['motor_vehicle']),
        cash=float(row['cash']),
        equity=float(row['equity']),
        other=float(row['other']),
    )

# def create_lgd_instance(row):
#     return LossGivenDefault(
#         exposure=row['EAD'],
#         cure_rate=cures,
#         recovery_rate=recoveries
#     )

def calculate_single_loan_ecl(
        account_no:str, 
        stage:str, 
        loan_type:str,
        eir: float,
        amortization_schedule:pd.DataFrame, 
        lgd_schedule:pd.DataFrame, 
        stage1_pds:pd.DataFrame, 
        stage2_pds:pd.DataFrame
    ):
    """
    Function to calculate the ECL for a single loan

    params:

    account_no: String representation of account number or unique loan identifier

    stage: Stage as determined by the ```staging_map``` function - see ```data_validation.py```

    loan_type: The loan-type per the segmentation in the data set - segmentation in PD data and Current Loan Book must match EXACTLY!

    eir: The applicable Effective Interest rate for the loan

    amortization_schedule: Expects Pandas Dataframe from the ```amortization``` property of ```ExposureAtDefault()``` class

    ldg_schedule: Expects Pandas Dataframe from the ```lgd_schedule``` of the ```LossGivenDefault``` class

    stage_1_pds: Expects Pandas Dataframe containing the marginal probability of default for Stage 1 loans - see ```extract_pds()``` function in ```data_validation.py```

    stage_2_pds: Expects Pandas Dataframe containing the marginal probability of default for Stage 2 loans - see ```extract_pds()``` function in ```data_validation.py```

    """

    max_pd_length = stage2_pds.shape[0]
    ead = pd.to_numeric(amortization_schedule["EAD (Out Bal.)"])
    lgd = pd.to_numeric(lgd_schedule["LGD"])

    if isinstance(ead, np.float64):
        num = 1
    else:
        num = min(len(ead), max_pd_length, len(lgd))

    if stage == 'stage_1':
        PD = stage1_pds[loan_type][:num]
    elif stage == 'stage_2':
        PD = stage2_pds[loan_type][:num]
    else:
        PD = pd.Series([1] * num)

    ead = ead[:num]
    lgd = lgd[:num]
    
    n = np.arange(1, num + 1)
    discount_factor = (1 + eir) ** (-n / 12)
    discount_factor = discount_factor[:num]

    try:
        ecl = PD * ead * lgd * discount_factor
    except Exception as e:
        print(f"Error calculating ECL for loan {account_no}: {e}")
        return None

    loan_ecl = {
        "Account Number": [account_no] * num,
        "Stage": [stage] * num,
        "Loan Type": [loan_type] * num,
        "ECL": list(ecl),
        "EAD": list(ead),
        "PD": list(PD),
        "LGD": list(lgd),
    }

    return pd.DataFrame(loan_ecl)

def ECL_Calc(
        account_no_list: list, 
        stage_list: list, 
        loan_type_list: list,
        eir_list: list,
        ead_list: list, 
        lgd_list: list, 
        stage1_pds: pd.DataFrame, 
        stage2_pds: pd.DataFrame
    ):

    parameters = zip(account_no_list, stage_list, loan_type_list, eir_list, ead_list, lgd_list)

    results = list(map(lambda params: calculate_single_loan_ecl(*params, stage1_pds, stage2_pds), parameters))

    ECL_df = pd.concat(results, axis=0)
    ECL_df.reset_index(inplace=True, drop=True)
    ECL_df["ECL"] = ECL_df['ECL'].round(2)
    ECL_df["EAD"] = ECL_df['EAD'].round(2)
    ECL_df["PD"] = ECL_df['PD'].round(8)
    ECL_df["LGD"] = ECL_df['LGD'].round(8)
    return ECL_df


def sum_of_ecl(df: pd.DataFrame):
    ecl_only = df[["Account Number", "Stage", "Loan Type", "EAD", "ECL"]]
    total_ecl = ecl_only.groupby("Account Number", as_index=False)[["EAD", "ECL"]].sum()
    stages = ecl_only[["Account Number", "Stage", "Loan Type"]].drop_duplicates()
    total_ecl_with_stage = total_ecl.merge(stages, on="Account Number", how="left")
    total_ecl_with_stage = total_ecl_with_stage.drop_duplicates(subset=["Account Number", "EAD", "ECL"])

    return total_ecl_with_stage


def merge_original_balance(loanbook_df, total_ECL_df):

    loanbook_df['account_no'] = loanbook_df['account_no'].astype(str)
    total_ECL_df['Account Number'] = total_ECL_df['Account Number'].astype(str)

    df = loanbook_df[['account_no', 'outstanding_balance']]
    df = df.rename(columns={'account_no': "Account Number", 'outstanding_balance': 'EAD'})

    final_df = pd.merge(df, total_ECL_df, on='Account Number', suffixes=('', "_ECL"))
    
    if 'EAD_ECL' in final_df.columns:
        final_df.drop(columns=['EAD_ECL'], inplace=True)
    
    final_df = final_df.rename(columns={'EAD': 'Exposure'})

    return final_df


def plot_ecl_bar(df: pd.DataFrame):
    df = df.groupby("Stage")[["ECL", "Exposure"]].sum().reset_index()

    color_map = {
        "stage_1": "blue",
        "stage_2": "green",
        "stage_3": "red"
    }

    # Melt the dataframe to long format
    df_melted = df.melt(id_vars=["Stage"], value_vars=["ECL", "Exposure"], var_name="Metric", value_name="Amount")

    # Create the bar plot
    fig = px.bar(
        df_melted,
        x="Stage",
        y="Amount",
        color="Stage",
        barmode='group',
        facet_col="Metric",
        color_discrete_map=color_map
    )
    fig.update_layout(
        barmode='group',
        title_text="ECL and Exposure by Stage",
        title_x=0.45
    )

    return fig


def plot_ecl_pie(df: pd.DataFrame):
    # Group the data by stage and sum ECL and EAD
    df = df.groupby("Stage")[["ECL", "Exposure"]].sum().reset_index()

    # Ensure the 'Stage' column is treated as a categorical variable with a specific order
    stage_order = ["stage_1", "stage_2", "stage_3"]
    df['Stage'] = pd.Categorical(df['Stage'], categories=stage_order, ordered=True)

    # Define custom colors for stages
    color_map = {
        "stage_1": "blue",
        "stage_2": "green",
        "stage_3": "red"
    }

    # Create subplots: one row, two columns
    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]],
                        subplot_titles=("ECL", "Exposure"))

    # Create a pie chart for ECL
    fig_ecl = px.pie(
        df,
        names="Stage",
        values="ECL",
        color="Stage",
        color_discrete_map=color_map
    )

    # Create a pie chart for EAD
    fig_ead = px.pie(
        df,
        names="Stage",
        values="Exposure",
        color="Stage",
        color_discrete_map=color_map
    )

    # Add the ECL pie chart to the first subplot
    fig.add_trace(
        go.Pie(labels=fig_ecl.data[0].labels, values=fig_ecl.data[0].values, marker_colors=fig_ecl.data[0].marker.colors),
        row=1, col=1
    )

    # Add the EAD pie chart to the second subplot
    fig.add_trace(
        go.Pie(labels=fig_ead.data[0].labels, values=fig_ead.data[0].values, marker_colors=fig_ead.data[0].marker.colors),
        row=1, col=2
    )

    # Update layout to center the titles and sort the legend
    fig.update_layout(
        title_text="EAD and ECL by Stage",
        title_x=0.45,
        legend=dict(traceorder='normal')
    )

    return fig

def create_loan_type_df(df, loanbook):
    loan_types = df["Loan Type"].unique()

    loan_type_dict = {
        loan_type: [
            df[df["Loan Type"] == loan_type]["ECL"].sum(),
            loanbook[loanbook["loan_type"] == loan_type]['outstanding_balance'].sum()
            ] 
            for loan_type in loanbook['loan_type'].unique()
        
    }
    df = pd.DataFrame.from_dict(loan_type_dict, orient='index', columns=["ECL", "EAD"])
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Loan Type'}, inplace=True)
    
    return df


def plot_bar_loan_type(df: pd.DataFrame):
    df = df.groupby("Loan Type")[["ECL", "Exposure"]].sum().reset_index()

    # Melt the dataframe to long format
    df_melted = df.melt(id_vars=["Loan Type"], value_vars=["ECL", "Exposure"], var_name="Metric", value_name="Amount")

    # Create the bar plot
    fig = px.bar(
        df_melted,
        x="Loan Type",
        y="Amount",
        color="Loan Type",
        barmode='group',
        facet_col="Metric",
    )
    fig.update_layout(
        barmode='group',
        title_text="ECL and Exposure by Stage",
        title_x=0.45
    )

    return fig


def plot_pie_loan_type(df: pd.DataFrame):
    # Group the data by stage and sum ECL and EAD
    df = df.groupby("Loan Type")[["ECL", "Exposure"]].sum().reset_index()

    # Create subplots: one row, two columns
    fig = make_subplots(rows=1, cols=2, specs=[[{'type': 'domain'}, {'type': 'domain'}]],
                        subplot_titles=("ECL", "Exposure"))

    # Create a pie chart for ECL
    fig_ecl = px.pie(
        df,
        names="Loan Type",
        values="ECL",
        color="Loan Type",
    )

    # Create a pie chart for EAD
    fig_ead = px.pie(
        df,
        names="Loan Type",
        values="Exposure",
        color="Loan Type",
    )

    # Add the ECL pie chart to the first subplot
    fig.add_trace(
        go.Pie(labels=fig_ecl.data[0].labels, values=fig_ecl.data[0].values, marker_colors=fig_ecl.data[0].marker.colors),
        row=1, col=1
    )

    # Add the EAD pie chart to the second subplot
    fig.add_trace(
        go.Pie(labels=fig_ead.data[0].labels, values=fig_ead.data[0].values, marker_colors=fig_ead.data[0].marker.colors),
        row=1, col=2
    )

    # Update layout to center the titles and sort the legend
    fig.update_layout(
        title_text="ECL and Exposure by Loan Type",
        title_x=0.45,
        legend=dict(traceorder='normal')
    )

    return fig