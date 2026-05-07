from __future__ import annotations

from importlib import import_module


def run_v1_main():
    return import_module("db_creation.canon_group_pipeline.canon_export").main()


def run_v2_main():
    return import_module("db_creation.canon_group_pipeline.canon_group_v2").main()


def run_v3_main():
    return import_module("db_creation.canon_group_pipeline.canon_group_v3").main()


def run_v4_main():
    return import_module("db_creation.canon_group_pipeline.canon_group_v4").main()


def run_v5_main():
    return import_module("db_creation.canon_group_pipeline.canon_group_v5").main()


def run_v6_main():
    return import_module("db_creation.canon_group_pipeline.canon_group_v6").main()

__all__ = [
    "run_v1_main",
    "run_v2_main",
    "run_v3_main",
    "run_v4_main",
    "run_v5_main",
    "run_v6_main",
]
