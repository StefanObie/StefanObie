import os
import numpy as np
import pandas as pd
from datetime import datetime
import requests
from collections import defaultdict
import plotly.graph_objects as go

def get_start_date(date=None):
    # Use the provided date, if any.
    if date:
        return pd.to_datetime(date)
    
    # Calculate the start date, which is one year ago from today,
    # adjusted to the previous Monday to ensure full weeks are included.
    year_ago = datetime.now() - pd.DateOffset(years=1)
    year_ago_monday = year_ago - pd.DateOffset(days=year_ago.weekday())
    return year_ago_monday.replace(hour=0, minute=0, second=0, microsecond=0)

def get_activities_from_file():
    df = pd.read_csv("strava_data/strava_activities.csv")
    print(f"Loaded {len(df)} activities from file.")
    return df.to_dict(orient='records'), get_start_date('2024-06-03')

def get_access_token():
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    response = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    })

    if response.status_code != 200:
        raise Exception(f"Strava token refresh failed: {response.text}")

    tokens = response.json()
    return tokens["access_token"]

def get_activities_from_strava():
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    start_date = get_start_date()

    params = {  
        "after": int(start_date.timestamp()),
        "per_page": 200, 
        "page": 1
    }

    all_activities = []
    for page in range(1, 100):
        params["page"] = page
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {response.status_code} {response.text}")
        
        data = response.json()
        if not data:
            break
        all_activities.extend(data)

    print(f"Total activities fetched: {len(all_activities)}")
    return all_activities, start_date

def group_by_day(activities, start_date):
    daily_distances = defaultdict(float)
    for activity in activities:
        if activity["type"] != "Run":
            continue
        date = activity["start_date_local"][:10]
        distance_km = activity["distance"] / 1000
        daily_distances[date] += distance_km

    df = pd.DataFrame(list(daily_distances.items()), columns=["date", "distance"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(by='date')

    # Use ISO calendar for week alignment
    df[['iso_year', 'iso_week', 'iso_day']] = df['date'].dt.isocalendar()
    start_iso = start_date.isocalendar()
    start_iso_year = start_iso.year
    start_iso_week = start_iso.week
    df['week'] = (df['iso_year'] - start_iso_year) * 52 + (df['iso_week'] - start_iso_week)
    df['day_of_week'] = df['iso_day'] - 1  # 0 = Monday, as before
    df['tooltip'] = df['date'].dt.strftime('%Y-%m-%d') + ": " + df['distance'].round(1).astype(str) + " km"

    # Create full date range to include missing weeks/days
    if not df.empty:
        end_date = df['date'].max()
    else:
        end_date = start_date + pd.DateOffset(weeks=52)  # Fallback if no data

    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    full_df = pd.DataFrame({'date': all_dates})
    full_df[['iso_year', 'iso_week', 'iso_day']] = full_df['date'].dt.isocalendar()
    full_df['week'] = (full_df['iso_year'] - start_iso_year) * 52 + (full_df['iso_week'] - start_iso_week)
    full_df['day_of_week'] = full_df['iso_day'] - 1

    # Merge with existing data
    full_df = full_df.merge(df[['date', 'distance', 'tooltip']], on='date', how='left')
    full_df['distance'] = full_df['distance'].fillna(0)
    full_df['tooltip'] = full_df['tooltip'].fillna(full_df['date'].dt.strftime('%Y-%m-%d') + ": 0.0 km")
    
    return full_df

def get_month_labels(start_date, num_weeks):
    week_start_dates = [start_date + pd.Timedelta(weeks=w) for w in range(num_weeks)]

    # Find which week each 1st of the month falls into
    first_dates = []
    current = pd.Timestamp(start_date)
    last = week_start_dates[-1] + pd.Timedelta(days=6)
    while current <= last:
        first_dates.append(current.replace(day=1))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year+1, month=1, day=1)
        else:
            current = current.replace(month=current.month+1, day=1)

    month_labels = [""] * num_weeks
    prev_year = None

    # Always set the first label to the month and year
    start_date_month = start_date.month
    end_of_first_week_date = start_date + pd.Timedelta(days=6)
    end_of_first_week_month = end_of_first_week_date.month

    if end_of_first_week_month == start_date_month:
        first_label = start_date.strftime('%b<br>%Y')
    else: # If the first week spans two months, use the month at the end of the week
        first_label = end_of_first_week_date.strftime('%b<br>%Y')

    month_labels[0] = first_label
    prev_year = start_date.year

    for first in first_dates:
        week_idx = ((first - start_date).days) // 7
        if 0 < week_idx < num_weeks:
            label = first.strftime('%b')
            if label == "Jan" and first.year != prev_year:
                label = f"Jan<br>{first.year}"
            month_labels[week_idx] = label
            prev_year = first.year

    return month_labels

def plot_heatmap(df, start_date):
    z = np.full((7, df['week'].max() + 1), 0, dtype=float)
    text = np.full(z.shape, '', dtype=object)

    for _, row in df.iterrows():
        week = int(row['week'])
        dow = int(row['day_of_week'])
        z[dow, week] = row['distance']
        text[dow, week] = row['tooltip']

    month_labels = get_month_labels(start_date, num_weeks=z.shape[1])

    fig = go.Figure(data=go.Heatmap(
        z=z,
        text=text,
        hoverinfo='text',
        # hoverinfo='skip',
        # colorscale='YlOrRd',  # Yellow to Red
        # colorscale='Blues',  # Blue shades
        # colorscale='Greens',  # Green shades
        colorscale='Reds',  # Red shades
        # More options: 'Viridis', 'Cividis', 'Magma', 'Inferno'
        # colorscale='Magma',
        # reverse the color scale
        # reversescale=True,
        # colorscale=[
        #     [0, 'lightgrey'],   # 0 km = light grey
        #     [0.01, 'rgb(255,255,204)'],  # start of YlOrRd
        #     [1, 'rgb(200,0,38)']         # end of YlOrRd
        # ],
        showscale=True,
        xgap=2,
        ygap=2,
        colorbar=dict(title='Distance [km]'),
    ))

    fig.update_layout(
        title={
            'text': '🏃 Running Distance Heatmap - Past Year 🏃',
            'x': 0.5,
            'xanchor': 'center',
            'font': dict(size=24),
        },
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(7)),
            ticktext=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            autorange='reversed',
            showgrid=False,
            zeroline=False,
            shift=-5,
            anchor='free',
        ),
        xaxis=dict(
            tickmode='array',
            tickvals=list(range(len(month_labels))),
            ticktext=month_labels,
            showgrid=False,
            zeroline=False,
        ),
        margin=dict(t=60, l=20, r=20, b=20),
        width=1400,
        height=250,
    )

    if run_locally:
        fig.show()
    else:
        fig.write_image("images/running_heatmap.svg", width=1400, height=250)
    
    fig.write_html("docs/running_heatmap.html")

if __name__ == "__main__":
    run_locally = os.getenv("RUN_LOCALLY", "true").lower() in ("true", "1", "yes", "y")
    if run_locally: # Default
        act, start_date = get_activities_from_file()
    else:
        act, start_date = get_activities_from_strava()  

    df = group_by_day(act, start_date)
    plot_heatmap(df, start_date)
