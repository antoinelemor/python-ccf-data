"""ccf_data — Python client for the Canadian Climate Framing data API.

>>> from ccf_data import CCF
>>> ccf = CCF(token='...')             # token from data.ccf-project.ca
>>> ccf.summary()
>>> ccf.search('carbon tax', limit=200)
"""

from .client import CCF
from .exceptions import (
    CCFError, CCFAuthError, CCFTierError, CCFQuotaError,
    CCFNotFound, CCFServerError, CCFBadRequest,
)
from .schema import (
    CODEBOOK, FRAME_NAMES, FRAME_COLUMNS, ALL_FRAME_SUBCATEGORIES,
    MESSENGERS, EVENTS, SOLUTIONS, TONES, OTHER,
    ALL_ANNOTATION_COLUMNS, MEDIA_OUTLETS, LANGUAGES,
    define, subcategories_of, codebook_dataframe,
)
from .tiers import (
    TIERS, TIER_DESCRIPTIONS, METHOD_TIERS,
    tier_required, methods_by_tier, tier_at_least,
)

__version__ = "0.2.0"

__all__ = [
    "CCF",
    "CCFError", "CCFAuthError", "CCFTierError", "CCFQuotaError",
    "CCFNotFound", "CCFServerError", "CCFBadRequest",
    "CODEBOOK", "FRAME_NAMES", "FRAME_COLUMNS", "ALL_FRAME_SUBCATEGORIES",
    "MESSENGERS", "EVENTS", "SOLUTIONS", "TONES", "OTHER",
    "ALL_ANNOTATION_COLUMNS", "MEDIA_OUTLETS", "LANGUAGES",
    "define", "subcategories_of", "codebook_dataframe",
    "TIERS", "TIER_DESCRIPTIONS", "METHOD_TIERS",
    "tier_required", "methods_by_tier", "tier_at_least",
]
