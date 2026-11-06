"""Build the installable add-on without including tests or development files."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "rebuild_filtered_daily"
target = root / "dist" / "rebuild_filtered_daily.ankiaddon"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "addon.py", "config.json", "manifest.json"):
        archive.write(source / name, name)
print(target)
