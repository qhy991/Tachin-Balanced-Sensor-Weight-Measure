import modulefinder
import shutil
import os
import sys

ENTRY_FILE = os.path.abspath('interface_large_sensor.py')
project_root = os.path.dirname(ENTRY_FILE)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

finder = modulefinder.ModuleFinder()
finder.run_script(ENTRY_FILE)

for name, mod in finder.modules.items():
    f = mod.__file__
    if f and f.endswith('.py') and os.path.abspath(f).startswith(project_root):
        rel_path = os.path.relpath(f, project_root)
        dest_path = os.path.join('target_folder', rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(f, dest_path)
