"""
Geolocation resolution module for NAFDAC drug verification requests.

Extracts geographic location from API Gateway Lambda proxy events using
CloudFront geo headers (primary) or source IP (fallback). Geolocation is
observability data — it must never block the core verification workflow.
"""

import logging

try:
    import pycountry
except ImportError:
    pycountry = None

logger = logging.getLogger(__name__)


def _get_country_name(country_code: str) -> str:
    """Look up country name from ISO 3166-1 alpha-2 code using pycountry."""
    if not country_code or not isinstance(country_code, str):
        return "Unknown"
    try:
        if pycountry:
            country = pycountry.countries.get(alpha_2=country_code.upper())
            return country.name if country else "Unknown"
        return "Unknown"
    except Exception:
        return "Unknown"


def _get_header(headers: dict, name: str) -> str | None:
    """Case-insensitive header lookup."""
    if not headers or not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _extract_source_ip(event: dict) -> str:
    """Extract source IP from requestContext or X-Forwarded-For header."""
    try:
        source_ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp")
        if source_ip:
            return source_ip
    except (AttributeError, TypeError):
        pass

    headers = event.get("headers") or {}
    xff = _get_header(headers, "X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()

    return "Unknown"


def resolve_geolocation(event: dict) -> dict:
    """
    Extract geolocation from API Gateway Lambda proxy event.

    Args:
        event: API Gateway Lambda proxy integration event

    Returns:
        dict with keys:
            - country_code: str (ISO 3166-1 alpha-2, e.g. "NG") or "Unknown"
            - country_name: str (e.g. "Nigeria") or "Unknown"
            - region: str (e.g. "Lagos") or "Unknown"
            - source_ip: str (raw IP address)
            - resolution_method: str ("cloudfront_header" | "ip_fallback" | "unknown")
    """
    unknown_result = {
        "country_code": "Unknown",
        "country_name": "Unknown",
        "region": "Unknown",
        "source_ip": "Unknown",
        "resolution_method": "unknown",
    }

    try:
        if not event or not isinstance(event, dict):
            return unknown_result

        headers = event.get("headers") or {}
        source_ip = _extract_source_ip(event)

        # Primary: CloudFront geo headers
        country_code = _get_header(headers, "CloudFront-Viewer-Country")
        if country_code:
            country_name = _get_country_name(country_code)
            region_header = _get_header(headers, "CloudFront-Viewer-Country-Region")
            region = region_header if region_header else "Unknown"

            return {
                "country_code": country_code,
                "country_name": country_name,
                "region": region,
                "source_ip": source_ip,
                "resolution_method": "cloudfront_header",
            }

        # Fallback: source IP available but no geo headers
        if source_ip and source_ip != "Unknown":
            return {
                "country_code": "Unknown",
                "country_name": "Unknown",
                "region": "Unknown",
                "source_ip": source_ip,
                "resolution_method": "ip_fallback",
            }

        return unknown_result

    except Exception:
        logger.warning("Failed to resolve geolocation", exc_info=True)
        return unknown_result
