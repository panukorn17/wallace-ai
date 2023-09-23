import io
import datetime
import numpy as np
import pandas as pd

from typing import Tuple, List
from tqdm import tqdm
from datetime import timedelta

# initialise tqdm for pandas
tqdm.pandas()

THRESHOLD_MINUTES = 500
TOTAL_FOR_LOOPS = 18
MISSING_DATA_THRESHOLD = 10.0 
STATION_OFFSET_TRAVEL_TIME = 1
STATION_OFFSET_DWELL_TIME = 2
NEXT_STATION_OFFSET = 1

def add_schedule_detail(schedule: pd.DataFrame) -> pd.DataFrame:
    """
    Add schedule detail to a given schedule.

    Parameters:
    - schedule: DataFrame representing the schedule.

    Returns:
    - DataFrame of schedule schdule.
    """
    schedule = pd.read_csv(io.StringIO(schedule), sep=',', dtype=str, engine='python')
    schedule = schedule.drop(schedule.columns[0], axis=1)
    return schedule

def is_valid_string(value):
    return value is not None and isinstance(value, str) and value != ""

def set_starting_terminating_times(schedule: pd.DataFrame) -> pd.DataFrame:
    """ 
    Set the starting and terminating times for a given schedule.
    
    Parameters:
    - schedule: DataFrame representing the schedule.

    Returns:
    - DataFrame with modified starting and terminating times.
    """
    schedule.at[0,'actual_ta'] = 'starting'
    schedule.at[0,'gbtt_pta'] = 'starting'
    schedule.iloc[-1, schedule.columns.get_loc('actual_td')] = 'terminating'
    schedule.iloc[-1, schedule.columns.get_loc('gbtt_ptd')] = 'terminating'
    return schedule

def calculate_missing_percentage(schedule: pd.DataFrame) -> float():
    '''
    Calculate the percentage of missing data in a given schedule.

    Parameters:
    - schedule: DataFrame representing the schedule.

    Returns:
    - Percentage of missing data in the schedule.
    '''
    schedule = schedule.replace(r'\s+', np.nan, regex=True).replace('', np.nan)
    return schedule.isnull().sum().sum() / np.prod(schedule.shape) * 100

def get_time_difference(time1: str, time2: str, format='%H%M') -> float():
    '''
    Calculate the time difference between two given times.

    Parameters:
    - time1: First time.
    - time2: Second time.

    Returns:
    - Time difference between the two given times in minutes
    '''
    startDateTime = datetime.datetime.strptime(time1, format)
    endDateTime = datetime.datetime.strptime(time2, format)
    diff_minutes = (endDateTime - startDateTime).total_seconds() / 60.0
    if np.abs(diff_minutes) > THRESHOLD_MINUTES:
        endDateTime += timedelta(days=1)
        diff_minutes = (endDateTime - startDateTime).total_seconds() / 60.0
    return diff_minutes

def travel_time(schedule: pd.DataFrame) -> pd.DataFrame:
    '''
    Calculate the travel time for a given schedule.

    Parameters:
    - schedule: DataFrame representing the schedule.

    Returns:
    - DataFrame with added actual and predicted travel time.
    '''

    travel_times = [0] * len(schedule)
    travel_times_predicted = [0] * len(schedule)

    for j in range(len(schedule) - STATION_OFFSET_TRAVEL_TIME):
        # for loop runs until the penultimate row to avoid index out of bounds error
        # get the actual and public arrival and departure time of the current and next station
        actual_td, actual_ta = schedule.iloc[j]['actual_td'], schedule.iloc[j + NEXT_STATION_OFFSET]['actual_ta']
        gbtt_ptd, gbtt_pta = schedule.iloc[j]['gbtt_ptd'], schedule.iloc[j + NEXT_STATION_OFFSET]['gbtt_pta']

        # if the actual and public arrival and departure time of the current and next station are not null then calculate the travel time
        if is_valid_string(actual_ta) and is_valid_string(actual_td):
            # the actual travel time to get to the current station starting from the second station
            travel_times[j + NEXT_STATION_OFFSET] = get_time_difference(actual_td, actual_ta)
        
        if is_valid_string(gbtt_pta) and is_valid_string(gbtt_ptd):
            # the predicted travel time to get to the current station starting from the second station
            travel_times_predicted[j + NEXT_STATION_OFFSET] = get_time_difference(gbtt_ptd, gbtt_pta)

    # add actual and predicted travel time a new feature to the schedule dataframe
    schedule['travel_time'] = travel_times
    schedule['travel_time_predicted'] = travel_times_predicted
    return schedule

def dwell_time(schedule: pd.DataFrame) -> pd.DataFrame:
    '''
    Calculate the dwell time for a given schedule.

    Parameters:
    - schedule: DataFrame representing the schedule.

    Returns:
    - DataFrame with added actual and predicted dwell time.
    '''

    dwell_times = [0] * len(schedule)
    dwell_times_predicted = [0] * len(schedule)

    for j in range(len(schedule) - STATION_OFFSET_DWELL_TIME):
        # for loop runs from the second row to the penultimate row as the first and last row will be the starting terminating station and not have a dwell time
        actual_ta, actual_td = schedule.iloc[j + NEXT_STATION_OFFSET]['actual_ta'], schedule.iloc[j + NEXT_STATION_OFFSET]['actual_td']
        gbtt_pta, gbtt_ptd = schedule.iloc[j + NEXT_STATION_OFFSET]['gbtt_pta'], schedule.iloc[j + NEXT_STATION_OFFSET]['gbtt_ptd']
        
        # if the actual and public arrival and departure time of the current and next station are not null then calculate the dwell time
        if is_valid_string(actual_ta) and is_valid_string(actual_td):
            # the actual dwell time of the current station next station starting from the second station
            dwell_times[j + NEXT_STATION_OFFSET] = get_time_difference(actual_ta, actual_td)

        if is_valid_string(gbtt_pta) and is_valid_string(gbtt_ptd):
            # the predicted dwell time of the current station next station starting from the second station
            dwell_times_predicted[j + NEXT_STATION_OFFSET] = get_time_difference(gbtt_pta, gbtt_ptd)

    # add actual and predicted dwell time a new feature to the schedule dataframe
    schedule['dwell_time'] = dwell_times
    schedule['dwell_time_predicted'] = dwell_times_predicted
    return schedule

def calculate_metrics(schedule: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate travel and dwell times.
    
    Parameters:
    - row: DataFrame representing the schedule.
    
    Returns:
    - DataFrame with added actual and predicted travel and dwell times.
    """
    schedule = travel_time(schedule)
    schedule = dwell_time(schedule)
    return schedule

def dwell_time_extract(historical_information: pd.DataFrame) -> Tuple[pd.DataFrame, List[int]]:
    """
    Extracts dwell times for each station from the historical information.
    
    Parameters:
    - historical_information: DataFrame containing the historical data.
    - total_for_loops: Total number of loops for progress bar.
    
    Returns:
    - DataFrame containing station, dwell time, and predicted dwell time.
    - List of indices of extreme values.
    """
    
    all_stations = []
    dwell_time_all_stations = []
    dwell_time_predicted_all_stations = []
    extreme_value_index = []
    
    # Iterate through the DataFrame index
    for i in tqdm(historical_information.index, desc=f'Extracting all dwell times'):
        schedule_detail = historical_information.at[i, '5.schedule_detail']
        
        # Extract the necessary columns from schedule_detail
        stations = schedule_detail['location'].tolist()
        dwell_times = schedule_detail['dwell_time'].tolist()
        dwell_times_predicted = schedule_detail['dwell_time_predicted'].tolist()

        # Append to results lists
        all_stations.extend(stations)
        dwell_time_all_stations.extend(dwell_times)
        dwell_time_predicted_all_stations.extend(dwell_times_predicted)
        
        # Check threshold conditions for each dwell time and predicted dwell time
        for dwell_time, dwell_time_predicted in zip(dwell_times, dwell_times_predicted):
            if (np.absolute(dwell_time) > THRESHOLD_MINUTES) or (np.absolute(dwell_time_predicted) > THRESHOLD_MINUTES):
                extreme_value_index.append(i)
    
    dwell_time_stations = pd.DataFrame({
        '1.station': all_stations,
        '2.dwell_time': dwell_time_all_stations,
        '3.dwell_time_predicted': dwell_time_predicted_all_stations
    })
    
    return dwell_time_stations, extreme_value_index

def dwell_time_summary_statistics(dwell_time_stations: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineer unique station metrics such as total and average dwell times.
    
    Parameters:
    - dwell_time_stations: DataFrame with station dwell time data.

    Returns:
    - DataFrame with unique station metrics.
    """
    aggregated = dwell_time_stations.groupby('1.station').agg(
        total_dwell_time=pd.NamedAgg(column='2.dwell_time', aggfunc='sum'),
        total_dwell_time_predicted=pd.NamedAgg(column='3.dwell_time_predicted', aggfunc='sum'),
        average_dwell_time=pd.NamedAgg(column='2.dwell_time', aggfunc='mean'),
        average_dwell_time_predicted=pd.NamedAgg(column='3.dwell_time_predicted', aggfunc='mean')
    ).reset_index()

    # Remove rows with all zero values
    aggregated = aggregated.loc[~(aggregated == 0).all(axis=1)]

    return aggregated

def extract_schedule_OD_travel(historical_information: pd.DataFrame) -> Tuple[List[str], List[str], List[float], List[float]]:
    """
    Extract details from schedule.
    
    Parameters:
    - historical_information: DataFrame containing the historical data.

    Returns:
    - List of origins.
    - List of destinations.
    - List of travel times.
    - List of predicted travel times.
    """
    origins, destinations, travel_times, predicted_travel_times = [], [], [], []
    
    for _, row in historical_information.iterrows():
        schedule_detail = row['5.schedule_detail']
        
        # Extract details of origin and destination travel time and predicted travel time in minutes
        for i in range(len(schedule_detail) - STATION_OFFSET_TRAVEL_TIME):
            origins.append(schedule_detail.iloc[i]['location'])
            destinations.append(schedule_detail.iloc[i + STATION_OFFSET_TRAVEL_TIME]['location'])
            travel_times.append(schedule_detail.iloc[i + STATION_OFFSET_TRAVEL_TIME]['travel_time'])
            predicted_travel_times.append(schedule_detail.iloc[i + STATION_OFFSET_TRAVEL_TIME]['travel_time_predicted'])
            
    return origins, destinations, travel_times, predicted_travel_times

def create_OD_pairs_dataframe(origins: List[str], destinations: List[str], travel_times: List[float], predicted_travel_times: List[float]) -> pd.DataFrame:
    """
    Create the OD pairs DataFrame.
    
    Parameters:
    - origins: List of origins.
    - destinations: List of destinations.
    - travel_times: List of travel times.
    - predicted_travel_times: List of predicted travel times.

    Returns:
    - DataFrame containing OD pairs.
    """
    return pd.DataFrame({
        '1.origin': origins,
        '2.destination': destinations,
        '3.time_travelled': travel_times,
        '4.predicted_time_travelled': predicted_travel_times
    })

def travel_time_summary_statistics(OD_pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate travel times summmary statistics.
    
    Parameters:
    - OD_pairs: DataFrame containing OD pairs.

    Returns:
    - DataFrame containing travel times summary statistics.
    """
    # Group by origin and destination
    group = OD_pairs.groupby(['1.origin', '2.destination'])
    
    # Calculate aggregate values
    agg_df = group.agg(total_travel_time=('3.time_travelled', 'sum'),
                       average_travel_time=('3.time_travelled', 'mean'),
                       total_travel_time_predicted=('4.predicted_time_travelled', 'sum'),
                       average_travel_time_predicted=('4.predicted_time_travelled', 'mean')).reset_index()
    
    return agg_df

def drop_nan_pairs(historical_information: pd.DataFrame, OD_pairs_unique: pd.DataFrame)-> pd.DataFrame:
    """
    Drop rows with nan values.

    Parameters:
    - historical_information: DataFrame containing the historical data.
    - OD_pairs_unique: DataFrame containing OD pairs.

    Returns:
    - DataFrame with dropped rows.
    """
    # Extract list of lists containing the origin and destinations that have nan average travel times
    OD_pairs_unique_nan = OD_pairs_unique[np.isnan(OD_pairs_unique['average_travel_time'])][['1.origin', '2.destination']].values.tolist()
    # Convert each inner list into a tuple. The result is a list of tuples, where each tuple represents an (origin, destination) pair.
    OD_pairs_unique_nan = [tuple(i) for i in OD_pairs_unique_nan]

    # Check for each row if it contains any OD nan pair
    to_drop = historical_information['5.schedule_detail'].apply(
        lambda x: any((row['location'], x.loc[idx + NEXT_STATION_OFFSET, 'location']) in OD_pairs_unique_nan for idx, row in x.iterrows() if idx + NEXT_STATION_OFFSET < len(x))
    )
    return historical_information[~to_drop].reset_index(drop=True)

def get_total_null(historical_information: pd.DataFrame) -> pd.DataFrame:
    '''
    Compute total null value.

    Parameters:
    - historical_information: DataFrame representing the historical information dataset.

    Returns:
    - Total null value.
    '''
    total_null = historical_information['5.schedule_detail'].apply(
        lambda x: x.loc[:, 'gbtt_ptd':'actual_ta'].isnull().sum().sum()
    ).sum()
    return total_null

def extract_missing_data(historical_information: pd.DataFrame) -> pd.DataFrame:
    '''
    Extract missing data and their indexes in the historical information dataframe and schedule dataframe.

    Parameters:
    - historical_information: DataFrame representing the historical information dataset.

    Returns:
    - DataFrame containing missing data.
    '''
    rows_list = []
    for idx, row in historical_information.iterrows():
        x = row['5.schedule_detail']
        for j in x.index[:-1]:
            if pd.isna(x.loc[j + NEXT_STATION_OFFSET, 'actual_ta']):
                data = {
                    '1.origin': x.loc[j, 'location'],
                    '2.destination': x.loc[j + NEXT_STATION_OFFSET, 'location'],
                    '3.actual_departure_prev_station': x.loc[j, 'actual_td'],
                    '4.actual_arrival': x.loc[j + NEXT_STATION_OFFSET, 'actual_ta'],
                    '5.actual_departure_current_station': x.loc[j + NEXT_STATION_OFFSET, 'actual_td'],
                    '6.h_i_index': idx,
                    '7.s_d_index': j + NEXT_STATION_OFFSET,
                    'average_actual_travel_time': 0,
                    'average_predicted_travel_time': 0,
                    'average_dwell_time': 0,
                    'average_predicted_dwell_time': 0
                }
                rows_list.append(data)

    return pd.DataFrame(rows_list)

def process_historical_data(historical_information: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
    '''
    Process the historical information dataset.

    Parameters:
    - historical_information: DataFrame representing the historical information dataset.

    Returns:
    - Processed historical information dataset.
    '''
    # Set arrival/departure time for starting/terminating stations
    print('Setting arrival/departure time for starting/terminating stations...')
    historical_information.loc[:,'5.schedule_detail'] = historical_information['5.schedule_detail'].progress_apply(set_starting_terminating_times)

    # Calculate missing data percentages
    print('Calculating missing data percentages...')
    historical_information.loc[:,'percentage_null'] = historical_information['5.schedule_detail'].progress_apply(calculate_missing_percentage)

    # Drop rows with more than 10% missing data
    print('Dropping rows with more than 10% missing data...')
    historical_information = historical_information[historical_information['percentage_null'] <= MISSING_DATA_THRESHOLD].reset_index(drop=True)

    # Extract trips to find unique ones
    print('Extracting trips to find unique ones...')
    historical_information['locations'] = historical_information['5.schedule_detail'].apply(lambda x: x['location'].to_string())
    duplicate_list = historical_information.duplicated(['2.origin', '3.destination', '4.stops', 'locations'], keep='first').tolist()
    historical_information['duplicate_list'] = duplicate_list

    # Get unique trips
    print('Getting unique trips...')
    unique_trips = historical_information[~historical_information.duplicate_list]
    unique_trips = unique_trips.drop(columns=['1.date', 'percentage_null', 'duplicate_list']).sort_values(by='2.origin').reset_index(drop=True)

    # Feature engineer time-related metrics
    print('Feature engineer actual and predicted travel and dwell times...')
    historical_information['5.schedule_detail'] = historical_information['5.schedule_detail'].progress_apply(calculate_metrics)
    
    # Extract dwell times for each station
    print('Extracting dwell times for each station...')
    dwell_time_stations, extreme_value_index = dwell_time_extract(historical_information)
    
    # Calculate summary statistics for dwell times
    print('Calculating summary statistics for dwell times...')
    station_dwell_time_unique = dwell_time_summary_statistics(dwell_time_stations)

    # Extract schedule origin, destination, travel time, and predicted travel time
    print('Extracting schedule origin, destination, travel time, and predicted travel time...')
    origins, destinations, travel_times, predicted_travel_times = extract_schedule_OD_travel(historical_information)

    # Create OD pairs DataFrame
    print('Creating OD pairs DataFrame...')
    od_pairs = create_OD_pairs_dataframe(origins, destinations, travel_times, predicted_travel_times)

    # Calculate summary statistics for travel times
    print('Calculating summary statistics for travel times...')
    od_pairs_unique = travel_time_summary_statistics(od_pairs)

    # Drop rows with nan values
    historical_information = drop_nan_pairs(historical_information, od_pairs_unique)

    # while the total null values is not zero
    while True:
        # Compute missing data stats
        total_null = get_total_null(historical_information)
        print('Total null values =', total_null)
        if total_null == 0:
            break

        aa_nan = extract_missing_data(historical_information)

    return historical_information, unique_trips

if __name__ == '__main__':

    DATA_PATHS = ["Data/hist_info_DID_PAD_2016.csv"]
    OUTPUT_FILENAME = "Data/feature_engineered.csv"  # Adjust this accordingly, or include the dynamic filename generation logic.

    historical_information = pd.read_csv(DATA_PATHS[0]).head(1000)
    print("Adding schedule detail...")
    historical_information.loc[:,'5.schedule_detail'] = historical_information['5.schedule_detail'].progress_apply(add_schedule_detail)
    # process historical information to add actual and predicted travel time and dwell time and get unique trips
    historical_information_refactored, unique_trips = process_historical_data(historical_information)
    historical_information_refactored.to_csv(OUTPUT_FILENAME)
