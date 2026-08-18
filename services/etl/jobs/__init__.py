"""ScoutGlobe ETL jobs. Run one with: uv run python -m jobs.<job_name>

Loading .env here (not per job) means third-party clients such as kagglehub,
which read os.environ directly, also see the credentials.
"""

from dotenv import load_dotenv

load_dotenv()
