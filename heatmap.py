import os
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from garminconnect import Garmin
from dotenv import load_dotenv

load_dotenv(".env.local")

NUM_WEEKS = 52

def get_date_window():
    # Rightmost column is the current week. end_date is this week's Sunday
    # (today itself when today is Sunday); start_date is the Monday 52 weeks
    # back, so the window spans exactly NUM_WEEKS whole weeks.
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today + timedelta(days=6 - today.weekday())
    start_date = end_date - timedelta(days=NUM_WEEKS * 7 - 1)
    return start_date, end_date

GARMIN_TOKEN_DIR = os.path.expanduser("~/.garmin_tokens")

def get_garmin_client():
    client = Garmin(
        os.getenv("GARMIN_EMAIL"), 
        os.getenv("GARMIN_PASSWORD"), 
        prompt_mfa=lambda: input("MFA code: "),
    )
    client.login("~/.garminconnect")

    return client

def get_activities_from_garmin():
    client = get_garmin_client()
    start_date, end_date = get_date_window()

    activities = client.get_activities_by_date(
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "running",
    )

    print(f"Total activities fetched: {len(activities)}")
    return activities, start_date, end_date

def build_grid(activities, start_date):
    # Empty 7 x NUM_WEEKS grid; every cell pre-filled so weeks with no runs
    # still render. Rows are days (0 = Monday), columns are weeks.
    z = np.zeros((7, NUM_WEEKS), dtype=float)
    text = np.empty(z.shape, dtype=object)
    for week in range(NUM_WEEKS):
        for dow in range(7):
            cell_date = start_date + timedelta(days=week * 7 + dow)
            text[dow, week] = f"{cell_date.strftime('%Y-%m-%d')}: 0.0 km"

    # start_date is a Monday and the window is a whole number of weeks, so a
    # simple day-offset gives exact (week, day-of-week) placement.
    for activity in activities:
        if activity["activityType"]["typeKey"] != "running":
            continue
        date = datetime.strptime(activity["startTimeLocal"][:10], "%Y-%m-%d")
        offset_days = (date - start_date).days
        if not 0 <= offset_days < NUM_WEEKS * 7:
            continue
        week, dow = divmod(offset_days, 7)
        z[dow, week] += activity["distance"] / 1000
        text[dow, week] = f"{date.strftime('%Y-%m-%d')}: {z[dow, week]:.1f} km"

    return z, text

def get_month_labels(start_date, num_weeks=NUM_WEEKS):
    week_start_dates = [start_date + timedelta(weeks=w) for w in range(num_weeks)]

    # Find which week each 1st of the month falls into
    first_dates = []
    current = start_date
    last = week_start_dates[-1] + timedelta(days=6)
    while current <= last:
        first_dates.append(current.replace(day=1))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    month_labels = [""] * num_weeks
    prev_year = None

    # Always set the first label to the month and year
    start_date_month = start_date.month
    end_of_first_week_date = start_date + timedelta(days=6)
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

def plot_heatmap(z, text, start_date):
    month_labels = get_month_labels(start_date)

    # Piecewise-linear color mapping. A plain log/linear scale wastes its
    # dynamic range: log flattens the 6-15 km band, and linear lets the 60 km
    # ultra squash everyday runs into near-white. Instead we hand-pick km
    # breakpoints and how much of the [0,1] color range each spans, so the
    # bulk of the reds is reserved for the 6-15 km "normal run" band while
    # short and long runs still show, just compressed at the ends.
    #   0-6 km   -> palest 15% of the scale
    #   6-15 km  -> 65% of the scale (the important band)
    #   15-60 km -> darkest 20% (the ultra shows but doesn't distort)
    break_km    = [0.0, 4.0, 20.0, 60.0]
    break_color = [0.0, 0.20, 0.80, 1.00]

    z_color = np.interp(z, break_km, break_color)

    # Colorbar ticks at real km values, positioned by the same mapping.
    tick_km = [0, 5, 10, 15, 20, 60]
    fig = go.Figure(data=go.Heatmap(
        z=z_color,
        zmin=0.0,
        zmax=1.0,
        text=text,
        hoverinfo='text',
        colorscale='Reds',  # Red shades
        showscale=True,
        xgap=2,
        ygap=2,
        colorbar=dict(
            title='Distance [km]',
            tickvals=[float(np.interp(k, break_km, break_color)) for k in tick_km],
            ticktext=[str(k) for k in tick_km],
        ),
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

    fig.write_image("images/running_heatmap.svg", width=1400, height=250)
    fig.write_html("docs/running_heatmap.html")

if __name__ == "__main__":
    activities, start_date, end_date = get_activities_from_garmin()
    z, text = build_grid(activities, start_date)
    plot_heatmap(z, text, start_date)
