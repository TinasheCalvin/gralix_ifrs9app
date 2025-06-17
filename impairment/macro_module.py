import pandas as pd
import asyncio
import aiohttp
import re


BASE_API_URL = 'https://www.imf.org/external/datamapper/api/v1/'
COUNTRY = 'Zambia'


def api_date_range(start=2000, end=2035):
    date_range = ",".join(map(str, range(start, end)))
    return f"?periods={date_range}"


async def fetch_country_code(session, country):
    country = country.casefold()
    async with session.get(f"{BASE_API_URL}countries") as response:
        data = (await response.json())['countries']
        country_codes = {str(data[code]['label']).casefold(): code for code in data}
        code = country_codes[country]
        return code


async def all_indicators(session):
    async with session.get(f"{BASE_API_URL}indicators") as response:
        data = (await response.json())['indicators']
        indicator_codes = {code: f"{data[code]['label']} - {data[code]['unit']}" for code in data.keys()}
        return indicator_codes 


async def fetch_indicator_data(session, indicator_dict, code, country_code, date_range):
    try:
        async with session.get(f"{BASE_API_URL}{country_code}/{code}/{date_range}") as response:
            data = await response.json()
            indicator_df = pd.DataFrame(data['values'][code])
            indicator_df.columns = [indicator_dict[code]]
            return indicator_df
    except KeyError:
        return None
    

async def all_data_fetch(session, indicator_dict, country_code, date_range):
    indicators = [item for item in indicator_dict.keys() if item != '']
    tasks = [fetch_indicator_data(session, indicator_dict, code, country_code, date_range) for code in indicators]
    results = await asyncio.gather(*tasks)
    df_list = [result for result in results if result is not None]
    return pd.concat(df_list, axis = 1)


async def fetch_imf():
    async with aiohttp.ClientSession() as session:
        country_code_result = await fetch_country_code(session, COUNTRY)
        indicator_dict = await all_indicators(session)
        data = await all_data_fetch(session, indicator_dict, country_code_result, api_date_range())
        pattern = re.compile(r'percent change|% change', re.IGNORECASE)
        cols_to_exclude = [col for col in data.columns if pattern.search(col)]
        cols_to_process = [col for col in data.columns if col not in cols_to_exclude]
        data[cols_to_exclude] = data[cols_to_exclude].div(100)
        data_pct_change = data[cols_to_process].fillna(0.0).pct_change()
        data_pct_change = (pd.concat([data_pct_change, data[cols_to_exclude]], axis=1))
        data_pct_change = data_pct_change.sort_index(axis=1, ascending=True)
        data_pct_change["Year"] = data_pct_change.index
        col_order = ["Year"] + list(data_pct_change.columns)
        return data_pct_change.reindex(columns=col_order)
    

