# generate_plot.py
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

x = np.linspace(0, 10, 100)
y = np.sin(x) + np.random.normal(0, 0.2, size=100)

plt.figure(figsize=(6, 3))
plt.plot(x, y, label='Randomized Sine')
plt.title(f'Auto-updated Plot ({datetime.now().strftime("%Y-%m-%d %H:%M:%S")})')
plt.legend()
plt.tight_layout()
plt.savefig("random_plot.png", dpi=100)
plt.close()
