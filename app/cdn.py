"""
AWS CloudFront CDN cache invalidation.
When CDN_ENABLED=false (local dev/test), all calls are no-ops.
"""

import time
import boto3
from app.config import settings


def invalidate_paths(paths: list[str]) -> None:
    """
    Create a CloudFront invalidation for the given paths.
    Each path should start with '/', e.g. ['/assets/uuid/download'].
    """
    if not settings.cdn_enabled:
        print(f"[cdn] CDN_ENABLED=false — skipping invalidation for: {paths}")
        return

    client = boto3.client(
        "cloudfront",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    caller_reference = str(time.time())
    client.create_invalidation(
        DistributionId=settings.cloudfront_distribution_id,
        InvalidationBatch={
            "Paths": {
                "Quantity": len(paths),
                "Items": paths,
            },
            "CallerReference": caller_reference,
        },
    )
    print(f"[cdn] CloudFront invalidation created for: {paths}")
