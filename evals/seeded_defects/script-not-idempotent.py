"""Add the archive path to the settings file so the viewer can find it."""
from pathlib import Path

SETTINGS = Path("settings.ini")
with SETTINGS.open("a", encoding="utf-8") as f:
    f.write("archive_path = /data/archive\n")
print("settings updated")
