"""Recall fixture: secrets identifiable by VALUE prefix, not by variable name.

HardcodedSecretsDetector is currently name-based only. These assignments use
non-sensitive variable names but the literal values carry unmistakable provider
prefixes (AWS access key, GitHub PAT, Stripe live key). Expected to MISS today
until value-based detection (prefix table + entropy) is added.
"""

# AWS access key id format: AKIA + 16 uppercase alphanumerics
aws_thing = "AKIA1234567890ABCDEF"  # EXPECT: HardcodedSecrets

# GitHub personal access token: ghp_ + 36 chars
gh_handle = "ghp_16C7e42F292c6912E7710c838347Ae178B4a01"  # EXPECT: HardcodedSecrets

# Stripe live secret assigned to a generic name
billing_cfg = "sk_test__REPLACED_BY_HISTORY_REWRITE"  # EXPECT: HardcodedSecrets
