import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# Create random heatmap data
z = np.random.rand(7, 53)  # 7 rows (days), 53 cols (weeks)

# Timestamp for title
timestamp = datetime.now()#.strftime("%Y-%m-%d %H:%M UTC")

# Create heatmap figure
fig = go.Figure(data=go.Heatmap(
    z=z,
    colorscale='YlOrRd',
    xgap=1,
    ygap=1,
    colorbar=dict(title='Value')
))

# Update layout with title
fig.update_layout(
    title=f"🗓️ Random Heatmap - {timestamp}",
    margin=dict(t=50, l=20, r=20, b=20),
    width=800,
    height=200
)

# Save as SVG
# fig.show()
fig.write_image("random_heatmap.svg")
