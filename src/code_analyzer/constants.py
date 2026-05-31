"""Centralized constants for the Code Architecture Analyzer.

All magic numbers used across the codebase should be defined here as named constants.
This improves readability, maintainability, and makes tuning easier.
"""
from __future__ import annotations

# =============================================================================
# SCORE WEIGHTING
# =============================================================================

# Weight for criteria score vs Maintainability Index in final score
CRITERIA_WEIGHT = 0.7
MI_WEIGHT = 0.3

# =============================================================================
# PRIORITY INDEX WEIGHTS (Priority Index = fan-in + commits + coverage)
# =============================================================================

PRIORITY_WEIGHT_FAN_IN = 0.40
PRIORITY_WEIGHT_COMMITS = 0.35
PRIORITY_WEIGHT_COVERAGE = 0.25

# =============================================================================
# TEST PAIN WEIGHTS (TP1 + TP2 + TP3 + TP4 → aggregate)
# =============================================================================

TEST_PAIN_WEIGHT_COVERAGE = 0.30
TEST_PAIN_WEIGHT_MOCK_DENSITY = 0.30
TEST_PAIN_WEIGHT_COMPLEXITY = 0.20
TEST_PAIN_WEIGHT_ISOLATION = 0.20

# =============================================================================
# CONFIDENCE THRESHOLDS (0.0–1.0)
# =============================================================================

# Findings with confidence >= HIGH_CONFIDENCE are emitted directly without asking
HIGH_CONFIDENCE = 0.85

# Very high confidence (used in dict_get detector)
VERY_HIGH_CONFIDENCE = 0.9

# Findings with confidence < ASK_THRESHOLD trigger a clarifying question in Intent Learning
ASK_THRESHOLD = 0.70

# Medium confidence (used in various detectors)
MEDIUM_CONFIDENCE = 0.65

# Low confidence (used in layer_separation detector)
LOW_CONFIDENCE = 0.55

# Moderate confidence (used in cohesion, dependency_inversion, interface_segregation, orm_in_loop)
MODERATE_CONFIDENCE = 0.60

# =============================================================================
# INTENT LEARNING
# =============================================================================

# Minimum answers before a detector can be marked as "noisy"
MIN_ANSWERS_FOR_NOISE = 10

# False positive rate threshold to mark a detector as noisy
FP_THRESHOLD = 0.7

# =============================================================================
# COHESION (LCOM - Lack of Cohesion of Methods)
# =============================================================================

# LCOM threshold: above this, class is considered to have low cohesion
LCOM_THRESHOLD = 0.7

# =============================================================================
# ROI DIMINISHING RETURNS
# =============================================================================

# Minimum delta to consider score improvement significant
ROI_DELTA_THRESHOLD = 0.3

# =============================================================================
# SIMILARITY (for cross-file duplication detection)
# =============================================================================

# Similarity cutoff for difflib.get_close_matches
SIMILARITY_CUTOFF = 0.6

# Number of close matches to return
CLOSE_MATCHES_COUNT = 3

# =============================================================================
# FEATURE ENVY THRESHOLDS
# =============================================================================

# Multiplier for foreign access count vs own access count
FEATURE_ENVY_FOREIGN_MULTIPLIER = 3

# Minimum foreign accesses to consider feature envy
FEATURE_ENVY_MIN_FOREIGN_ACCESSES = 5

# =============================================================================
# COMPLEXITY THRESHOLDS
# =============================================================================

# Average complexity penalty factor in Maintainability Index
MI_COMPLEXITY_PENALTY = 0.23

# =============================================================================
# MOCK DENSITY THRESHOLD
# =============================================================================

# Mock density above this indicates real coupling
MOCK_DENSITY_THRESHOLD = 0.3

# =============================================================================
# PRODUCTION RISK SCORE
# =============================================================================

# Weight per factor (5 factors × 20 = 100 max)
PROD_RISK_WEIGHT_PER_FACTOR = 20

# Normalizers for each factor
PROD_RISK_COVERAGE_NORMALIZER = 80
PROD_RISK_COMPLEXITY_NORMALIZER = 20
PROD_RISK_COUPLING_NORMALIZER = 15
PROD_RISK_ALTA_NORMALIZER = 3
PROD_RISK_DEFAULT_TEST_PAIN = 50
PROD_RISK_MAX_SCORE = 100

# Risk label thresholds
RISK_THRESHOLD_SAFE = 85
RISK_THRESHOLD_GOOD = 65
RISK_THRESHOLD_RISK = 40

# =============================================================================
# COUPLING THRESHOLDS
# =============================================================================

# Maximum unique imports before penalty
COUPLING_MAX_UNIQUE_IMPORTS = 15
COUPLING_PENALTY_UNIQUE = 3

# Maximum third-party imports before penalty
COUPLING_MAX_THIRD_PARTY = 8
COUPLING_PENALTY_THIRD_PARTY = 2

# Starting coupling score
COUPLING_STARTING_SCORE = 10

# =============================================================================
# DEFAULT MIN SCORE
# =============================================================================

# Default minimum score for pre-commit gate and init command
DEFAULT_MIN_SCORE = 7.0