"""Old start command kept working: `python mkdb.py` runs main.py (it used to be an identical copy)."""
import os, runpy
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"), run_name="__main__")
