"""Recall fixture: secrets by VALUE prefix (AWS, GitHub) and by NAME (Stripe).

The detector has both name-based and value-based passes. AWS/GitHub keys here
use non-sensitive variable names to test value-based detection. Stripe uses a
sensitive variable name to avoid GitHub push protection.
"""

# AWS access key id format: AKIA + 16 uppercase alphanumerics
aws_thing = "AKIA1234567890ABCDEF"  # EXPECT: HardcodedSecrets

# GitHub personal access token: ghp_ + 36 chars
gh_handle = "ghp_16C7e42F292c6912E7710c838347Ae178B4a01"  # EXPECT: HardcodedSecrets

# Stripe live secret (name-based to avoid GitHub push protection)
stripe_secret_key = "DO_NOT_USE_THIS_VALUE_IN_PRODUCTION"  # EXPECT: HardcodedSecrets
