import os
import numpy as np
import pandas as pd
from datetime import datetime
import requests
from collections import defaultdict
import plotly.graph_objects as go


def get_activities_from_file():
    df = pd.read_csv("strava_data/strava_activities.csv")
    print(f"Loaded {len(df)} activities from file.")
    return df.to_dict(orient='records')

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

    # Activities from the last 365 days, fetched from a Monday to avoid partial weeks
    last_monday = datetime.now() - pd.DateOffset(days=datetime.now().weekday())
    last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    after_param = int(last_monday.timestamp()) - 365*24*60*60
    params = {  
        "after": after_param,
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
    return all_activities

def group_by_day(activities):
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

    df['day_of_week'] = df['date'].dt.weekday  # 0 = Monday
    df['week'] = ((df['date'] - df['date'].min()).dt.days // 7)
    df['tooltip'] = df['date'].dt.strftime('%Y-%m-%d') + ": " + df['distance'].round(1).astype(str) + " km"
    return df

def plot_heatmap(df):
    z = np.full((7, df['week'].max() + 1), 0, dtype=float)
    text = np.full(z.shape, '', dtype=object)

    for _, row in df.iterrows():
        week = int(row['week'])
        dow = int(row['day_of_week'])
        z[dow, week] = row['distance']
        text[dow, week] = row['tooltip']

    fig = go.Figure(data=go.Heatmap(
        z=z,
        text=text,
        hoverinfo='text',
        # hoverinfo='skip',
        # colorscale='YlOrRd',  # Yellow to Red
        colorscale=[
            [0, 'lightgrey'],   # 0 km = light grey
            [0.01, 'rgb(255,255,204)'],  # start of YlOrRd
            [1, 'rgb(200,0,38)']         # end of YlOrRd
        ],
        showscale=True,
        xgap=2,
        ygap=2,
        colorbar=dict(title='Distance [km]'),
    ))

    fig.update_layout(
        title={
            'text': '🏃 Running Heatmap - Last 365 Days',
            'x': 0.5,
            'xanchor': 'center'
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
            showticklabels=False,
            showgrid=False,
            zeroline=False,
        ),
        margin=dict(t=40, l=20, r=20, b=20),
        width=1100,
        height=200,
    )

    if RUN_LOCALLY:
        fig.show()
    else:
        fig.write_image("images/running_heatmap.svg")

RUN_LOCALLY = False

if __name__ == "__main__":
    if RUN_LOCALLY:
        act = get_activities_from_file()
    else:
        act = get_activities_from_strava()

    df = group_by_day(act)
    plot_heatmap(df)
