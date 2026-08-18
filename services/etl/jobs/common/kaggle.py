"""Kaggle dataset acquisition with a cache-first policy.

DATA_SOURCES.md rule: every raw payload lands in data/raw/<source>/ and the same
data is never requested twice. If credentials are missing the job must fail with
an actionable message instead of silently importing nothing.
"""

import logging
import os
import shutil
from pathlib import Path

from jobs.common.paths import raw_dir

logger = logging.getLogger(__name__)

DATASET = "davidcariboo/player-scores"
CACHE_NAME = "kaggle/player-scores"


class DatasetUnavailableError(RuntimeError):
    """Raised when the dataset is neither cached nor downloadable."""


def _has_credentials() -> bool:
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    return (Path.home() / ".kaggle" / "kaggle.json").exists()


def ensure_dataset(required: tuple[str, ...], force_download: bool = False) -> Path:
    """Return the local directory holding the dataset CSVs.

    Order: local cache -> Kaggle download -> actionable error.
    """
    cache = raw_dir(CACHE_NAME)
    missing = [name for name in required if not (cache / name).exists()]

    if not missing and not force_download:
        logger.info("cache hit: %s", cache)
        return cache

    if not _has_credentials():
        raise DatasetUnavailableError(
            "Kaggle veri seti yerelde yok ve kimlik bilgisi bulunamadi.\n"
            f"  Eksik dosyalar : {', '.join(missing)}\n"
            f"  Beklenen klasor: {cache}\n"
            "Cozum (biri yeterli):\n"
            "  1) services/etl/.env icine KAGGLE_USERNAME ve KAGGLE_KEY ekle "
            "(kaggle.com > Settings > API > Create New Token), sonra bu job'i tekrar calistir.\n"
            f"  2) https://www.kaggle.com/datasets/{DATASET} adresinden zip'i indirip "
            f"CSV'leri {cache} klasorune ac."
        )

    try:
        import kagglehub
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DatasetUnavailableError("kagglehub kurulu degil: uv add kagglehub") from exc

    logger.info("downloading %s from Kaggle...", DATASET)
    downloaded = Path(kagglehub.dataset_download(DATASET, force_download=force_download))

    copied = 0
    for source_file in downloaded.glob("*.csv"):
        shutil.copy2(source_file, cache / source_file.name)
        copied += 1
    logger.info("cached %s CSV files into %s", copied, cache)

    still_missing = [name for name in required if not (cache / name).exists()]
    if still_missing:
        raise DatasetUnavailableError(
            f"Indirme tamamlandi ama beklenen dosyalar yok: {', '.join(still_missing)}. "
            f"Kaggle veri setinin semasi degismis olabilir; {cache} icerigini kontrol et."
        )
    return cache
