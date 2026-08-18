"""ScoutGlobe ETL jobs. Run one with: uv run python -m jobs.<job_name>

Loading .env here (not per job) means third-party clients such as kagglehub,
which read os.environ directly, also see the credentials.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# soccerdata reads its league dictionary at import time, so the repo-local
# config has to be pointed at before any job imports it. Keeping the file in
# the repo (rather than ~/soccerdata) means CI and a teammate's machine resolve
# the same leagues we do — see data/reference/soccerdata/README.md.
_REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("SOCCERDATA_DIR", str(_REPO_ROOT / "data" / "reference" / "soccerdata"))
