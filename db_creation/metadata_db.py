#!/usr/bin/env python3

from metadata_pipeline.pipeline import RetryConfig, SteamMetadataBuilder, configure_logging
from paths import metadata_db_path

DB_PATH = metadata_db_path()
LIMIT = None
PAGE_LIMIT = None
SKIP_STORE = False
REFRESH_STORE = False
RESUME = True
NOTES = None
PRICE_REGIONS = ["us"]


def main() -> int:
    configure_logging()

    builder = SteamMetadataBuilder(
        db_path=DB_PATH,
        retry_config=RetryConfig(
            max_retries=5,
            base_delay=2.0,
            timeout=30,
        ),
        steamspy_delay=1.1,
        store_delay=0.4,
        store_batch_delay=8.0,
        store_batch_size=25,
        price_regions=PRICE_REGIONS,
    )

    return builder.build(
        limit=LIMIT,
        page_limit=PAGE_LIMIT,
        skip_store=SKIP_STORE,
        refresh_store=REFRESH_STORE,
        resume=RESUME,
        notes=NOTES,
    )


if __name__ == "__main__":
    raise SystemExit(main())
