"""ATHENA Fundamentals Normalization Package (SI-F2B).

Provides production XBRL parsing, canonical mapping, and fact persistence
pipelines adhering to frozen decisions D1-D12.
"""

from athena.fundamentals.mapping_registry import (
    MAPPING_VERSION_V1,
    MappingRegistry,
    get_v1_mapping_registry,
)
from athena.fundamentals.normalizer import FundamentalFactNormalizer
from athena.fundamentals.xbrl_parser import parse_xbrl_document

__all__ = [
    "MAPPING_VERSION_V1",
    "FundamentalFactNormalizer",
    "MappingRegistry",
    "get_v1_mapping_registry",
    "parse_xbrl_document",
]
