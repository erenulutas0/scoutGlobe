"""Repository paths. Every raw payload is cached under data/raw/<source>/."""

from pathlib import Path

# services/etl/jobs/common/paths.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[4]

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"


def raw_dir(source: str) -> Path:
    """Cache directory for one source, created on demand."""
    path = RAW_DIR / source
    path.mkdir(parents=True, exist_ok=True)
    return path
