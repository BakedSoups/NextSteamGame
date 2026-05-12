#!/usr/bin/env python3

from metadata_pipeline.assets import SteamStoreAssetEnricher
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
RUN_ASSET_ENRICHMENT = True
ASSET_ENRICHMENT_WORKERS = 5
ASSET_ENRICHMENT_BATCH_SIZE = 25
ASSET_ENRICHMENT_BATCH_DELAY = 4.0
ASSET_ENRICHMENT_TIMEOUT = 20
ASSET_ENRICHMENT_LIMIT = None
ASSET_ENRICHMENT_REFRESH = False
ASSET_ENRICHMENT_RETRY_FAILURES = False
ASSET_ENRICHMENT_RETRY_NO_ASSETS = False
ASSET_ENRICHMENT_RESTART = False


def build_metadata_builder() -> SteamMetadataBuilder:
    return SteamMetadataBuilder(
        db_path=DB_PATH,
        retry_config=RetryConfig(
            max_retries=5,
            base_delay=2.0,
            timeout=30,
        ),
        store_delay=0.4,
        store_batch_delay=8.0,
        store_batch_size=25,
        store_workers=5,
        price_regions=PRICE_REGIONS,
    )


def run_metadata_sync() -> int:
    builder = build_metadata_builder()
    return builder.build(
        limit=LIMIT,
        page_limit=PAGE_LIMIT,
        skip_store=SKIP_STORE,
        refresh_store=REFRESH_STORE,
        resume=RESUME,
        notes=NOTES,
    )


def run_storefront_asset_enrichment() -> int:
    enricher = SteamStoreAssetEnricher(
        db_path=str(DB_PATH),
        workers=ASSET_ENRICHMENT_WORKERS,
        batch_size=ASSET_ENRICHMENT_BATCH_SIZE,
        batch_delay=ASSET_ENRICHMENT_BATCH_DELAY,
        timeout=ASSET_ENRICHMENT_TIMEOUT,
        limit=ASSET_ENRICHMENT_LIMIT,
        refresh=ASSET_ENRICHMENT_REFRESH,
        retry_failures=ASSET_ENRICHMENT_RETRY_FAILURES,
        retry_no_assets=ASSET_ENRICHMENT_RETRY_NO_ASSETS,
        restart=ASSET_ENRICHMENT_RESTART,
    )
    return enricher.run()


def main() -> int:
    configure_logging()
    metadata_result = run_metadata_sync()
    if metadata_result != 0:
        return metadata_result
    if RUN_ASSET_ENRICHMENT:
        return run_storefront_asset_enrichment()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
