import sys
from pathlib import Path
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')
DB_PATH = Path('database/disease_detector.db')
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

cursor.execute("SELECT id, user_id, name, location, primary_crop, area_hectare FROM farms")
farms = cursor.fetchall()
print(f"Total farms: {len(farms)}")
for f in farms:
    print(f" - Farm #{f[0]}: {f[2]} ({f[4]}, {f[5]} ha) - Owner User #{f[1]}")

cursor.execute("SELECT COUNT(*) FROM farm_plots")
plots_cnt = cursor.fetchone()[0]
print(f"Total farm plots: {plots_cnt}")

cursor.execute("SELECT COUNT(*) FROM plot_timeline_events")
events_cnt = cursor.fetchone()[0]
print(f"Total timeline events: {events_cnt}")
