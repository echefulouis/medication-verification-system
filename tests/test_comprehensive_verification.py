#!/usr/bin/env python3
"""
Comprehensive Verification Test Suite

Processes all images in test_images/ through the live API at nafdac.echefulouis.com:
  Phase 1: Image Verification — POST /verify with base64 image (OCR + Greenbook validation)
  Phase 2: Manual Validation — POST /validate with extracted NAFDAC numbers
  Phase 3: Report — clear summary of all results

Usage:
    python -m tests.test_comprehensive_verification
"""

import json
import base64
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from collections import Counter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = "https://qaabu1fn66.execute-api.us-east-1.amazonaws.com/prod"
VERIFY_URL = f"{API_BASE}/verify"
VALIDATE_URL = f"{API_BASE}/validate"
TEST_IMAGES_DIR = Path(__file__).resolve().parent.parent / "test_images"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
RESULTS_FILE = REPORTS_DIR / "test_results.json"
REPORT_FILE = REPORTS_DIR / "test_report.txt"
REQUEST_TIMEOUT = 120  # seconds — Greenbook scraping can be slow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_image_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def print_progress(current: int, total: int, label: str = "", width: int = 40):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r  [{bar}] {current}/{total} {label}")
    sys.stdout.flush()
    if current == total:
        print()


# ---------------------------------------------------------------------------
# Phase 1: Image Verification via /verify endpoint
# ---------------------------------------------------------------------------
def phase1_verify_images(image_paths: list[Path]) -> list[dict]:
    """POST each image to /verify, which runs the full pipeline (OCR + Greenbook)."""
    results = []
    total = len(image_paths)
    print(f"\n{'='*70}")
    print(f"  PHASE 1: Image Verification via {VERIFY_URL}")
    print(f"  Processing {total} images through full pipeline")
    print(f"{'='*70}")

    for idx, img_path in enumerate(image_paths, 1):
        print_progress(idx, total, img_path.name)
        record = {
            "image": img_path.name,
            "phase1_status": None,
            "nafdac_number": None,
            "product_name": None,
            "ocr_confidence": None,
            "verification_id": None,
            "greenbook_found": False,
            "greenbook_results": [],
            "greenbook_message": None,
            "error": None,
            "http_status": None,
            "duration_s": None,
        }
        try:
            img_b64 = load_image_base64(img_path)
            start = time.time()
            resp = requests.post(
                VERIFY_URL,
                json={"image": img_b64},
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            record["duration_s"] = round(time.time() - start, 2)
            record["http_status"] = resp.status_code

            data = resp.json()

            if resp.status_code == 200 and data.get("verificationId"):
                record["phase1_status"] = "success"
                record["verification_id"] = data.get("verificationId")
                record["nafdac_number"] = data.get("nafdacNumber")
                record["ocr_confidence"] = data.get("ocrConfidence")

                # The /verify endpoint runs the full pipeline including Greenbook
                vr = data.get("validationResult", {})
                record["greenbook_found"] = vr.get("found", False)
                record["greenbook_results"] = vr.get("results", [])
                record["greenbook_message"] = vr.get("message")

                # Product name: prefer top-level, fall back to first Greenbook result
                record["product_name"] = data.get("productName")
                if not record["product_name"] and record["greenbook_results"]:
                    record["product_name"] = record["greenbook_results"][0].get("product_name")
            else:
                record["phase1_status"] = "error"
                record["error"] = data.get("error", f"HTTP {resp.status_code}")
        except requests.Timeout:
            record["phase1_status"] = "error"
            record["error"] = "Request timed out"
        except Exception as e:
            record["phase1_status"] = "error"
            record["error"] = str(e)

        results.append(record)
        # Small delay between requests
        time.sleep(0.5)

    return results


# ---------------------------------------------------------------------------
# Phase 2: Re-validate unique NAFDAC numbers via /validate endpoint
# ---------------------------------------------------------------------------
def phase2_revalidate(records: list[dict]) -> list[dict]:
    """For each unique NAFDAC number found, do a manual /validate call to cross-check."""
    unique_nafdac = {}
    for r in records:
        if r["nafdac_number"] and r["nafdac_number"] not in unique_nafdac:
            unique_nafdac[r["nafdac_number"]] = r

    total = len(unique_nafdac)
    print(f"\n{'='*70}")
    print(f"  PHASE 2: Cross-validation via {VALIDATE_URL}")
    print(f"  Re-checking {total} unique NAFDAC numbers")
    print(f"{'='*70}")

    revalidation_results = {}
    for idx, (nafdac_num, _) in enumerate(unique_nafdac.items(), 1):
        print_progress(idx, total, nafdac_num)
        result = {
            "nafdac_number": nafdac_num,
            "status": None,
            "found": False,
            "results": [],
            "message": None,
            "error": None,
            "duration_s": None,
        }
        try:
            payload = {
                "verificationId": f"revalidate-{int(time.time())}-{idx}",
                "timestamp": datetime.utcnow().isoformat(),
                "imageKey": "",
                "nafdacNumber": nafdac_num,
            }
            start = time.time()
            resp = requests.post(
                VALIDATE_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            result["duration_s"] = round(time.time() - start, 2)

            data = resp.json()
            vr = data.get("validationResult", {})
            result["status"] = "success"
            result["found"] = vr.get("found", False)
            result["results"] = vr.get("results", [])
            result["message"] = vr.get("message")
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        revalidation_results[nafdac_num] = result
        time.sleep(1)  # Greenbook scraping needs breathing room

    return revalidation_results


# ---------------------------------------------------------------------------
# Phase 3: Report
# ---------------------------------------------------------------------------
def generate_report(records: list[dict], revalidation: dict, elapsed: float) -> str:
    """Build a human-readable report."""
    total = len(records)
    p1_success = sum(1 for r in records if r["phase1_status"] == "success")
    p1_error = sum(1 for r in records if r["phase1_status"] == "error")
    nafdac_found = sum(1 for r in records if r["nafdac_number"])
    nafdac_not_found = sum(1 for r in records if r["phase1_status"] == "success" and not r["nafdac_number"])
    product_name_found = sum(1 for r in records if r["product_name"])
    gb_found = sum(1 for r in records if r["greenbook_found"])
    gb_not_found = sum(1 for r in records if r["phase1_status"] == "success" and not r["greenbook_found"])

    # Confidence stats
    confidences = [r["ocr_confidence"] for r in records if r["ocr_confidence"] is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    min_conf = min(confidences) if confidences else 0
    max_conf = max(confidences) if confidences else 0

    # Duration stats
    durations = [r["duration_s"] for r in records if r["duration_s"] is not None]
    avg_dur = sum(durations) / len(durations) if durations else 0
    min_dur = min(durations) if durations else 0
    max_dur = max(durations) if durations else 0

    unique_nafdac = set(r["nafdac_number"] for r in records if r["nafdac_number"])

    lines = []
    lines.append("=" * 70)
    lines.append("  MEDICINE VERIFICATION — COMPREHENSIVE TEST REPORT")
    lines.append(f"  Endpoint: {API_BASE}")
    lines.append(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"  Total time: {elapsed:.1f}s")
    lines.append("=" * 70)

    lines.append("")
    lines.append("  PHASE 1: IMAGE VERIFICATION (POST /verify)")
    lines.append("  " + "-" * 50)
    lines.append(f"  Total images:              {total}")
    lines.append(f"  Successful:                {p1_success}")
    lines.append(f"  Errors:                    {p1_error}")
    lines.append(f"  NAFDAC extracted (OCR):    {nafdac_found}")
    lines.append(f"  NAFDAC not found:          {nafdac_not_found}")
    lines.append(f"  Product identified:         {product_name_found}")
    lines.append(f"  Greenbook match:           {gb_found}")
    lines.append(f"  Greenbook no match:        {gb_not_found}")
    lines.append(f"  Unique NAFDAC numbers:     {len(unique_nafdac)}")
    if confidences:
        lines.append(f"  OCR confidence (avg/min/max): {avg_conf:.1f}% / {min_conf:.1f}% / {max_conf:.1f}%")
    if durations:
        lines.append(f"  Request time (avg/min/max):   {avg_dur:.1f}s / {min_dur:.1f}s / {max_dur:.1f}s")

    # Phase 2 summary
    p2_total = len(revalidation)
    p2_found = sum(1 for v in revalidation.values() if v["found"])
    p2_not_found = sum(1 for v in revalidation.values() if v["status"] == "success" and not v["found"])
    p2_error = sum(1 for v in revalidation.values() if v["status"] == "error")

    lines.append("")
    lines.append("  PHASE 2: CROSS-VALIDATION (POST /validate)")
    lines.append("  " + "-" * 50)
    lines.append(f"  Unique NAFDAC re-checked:  {p2_total}")
    lines.append(f"  Confirmed in Greenbook:    {p2_found}")
    lines.append(f"  Not found in Greenbook:    {p2_not_found}")
    lines.append(f"  Errors:                    {p2_error}")

    # Detailed per-image table
    lines.append("")
    lines.append("  DETAILED RESULTS")
    lines.append("  " + "-" * 50)
    header = f"  {'Image':<22} {'NAFDAC':<14} {'Conf%':<8} {'Greenbook':<12} {'Time':<7} {'Product/Note'}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) + 10))

    for r in sorted(records, key=lambda x: x["image"]):
        nafdac = r["nafdac_number"] or "-"
        conf = f"{r['ocr_confidence']:.1f}" if r["ocr_confidence"] else "-"
        dur = f"{r['duration_s']:.1f}s" if r["duration_s"] else "-"

        if r["phase1_status"] == "error":
            gb = "ERROR"
        elif r["greenbook_found"]:
            gb = "FOUND"
        else:
            gb = "NOT FOUND"

        note = ""
        if r["greenbook_found"] and r["greenbook_results"]:
            note = r["greenbook_results"][0].get("product_name", "")[:35]
        elif r.get("product_name"):
            note = f"(Bedrock: {r['product_name'][:28]})"
        elif r.get("error"):
            note = f"ERR: {r['error'][:35]}"

        lines.append(f"  {r['image']:<22} {nafdac:<14} {conf:<8} {gb:<12} {dur:<7} {note}")

    # Unique NAFDAC summary with cross-validation
    if unique_nafdac:
        lines.append("")
        lines.append("  UNIQUE NAFDAC NUMBERS")
        lines.append("  " + "-" * 50)
        nafdac_counts = Counter(r["nafdac_number"] for r in records if r["nafdac_number"])
        for num, count in nafdac_counts.most_common():
            p1_match = any(r["greenbook_found"] for r in records if r["nafdac_number"] == num)
            p2_match = revalidation.get(num, {}).get("found", False)
            if p1_match and p2_match:
                status = "VERIFIED (both phases)"
            elif p1_match or p2_match:
                status = "PARTIAL (one phase matched)"
            else:
                status = "UNVERIFIED"
            lines.append(f"  {num:<14} seen {count}x — {status}")

    # Error summary
    errors = [r for r in records if r["phase1_status"] == "error"]
    if errors:
        lines.append("")
        lines.append("  ERRORS")
        lines.append("  " + "-" * 50)
        for r in errors[:20]:  # cap at 20
            lines.append(f"  {r['image']:<22} {r['error'][:50]}")
        if len(errors) > 20:
            lines.append(f"  ... and {len(errors) - 20} more errors")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not TEST_IMAGES_DIR.exists():
        print(f"ERROR: test_images directory not found at {TEST_IMAGES_DIR}")
        sys.exit(1)

    image_paths = sorted(
        p for p in TEST_IMAGES_DIR.iterdir()
        if p.suffix.lower() in (".jpeg", ".jpg", ".png")
    )

    if not image_paths:
        print("ERROR: No images found in test_images/")
        sys.exit(1)

    print(f"\nFound {len(image_paths)} test images")
    print(f"API endpoint: {API_BASE}")
    start = time.time()

    # Phase 1: Full verification via /verify
    records = phase1_verify_images(image_paths)

    # Phase 2: Cross-validate unique NAFDAC numbers via /validate
    revalidation = phase2_revalidate(records)

    elapsed = time.time() - start

    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Save raw results
    output = {"records": records, "revalidation": revalidation}
    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nRaw results saved to {RESULTS_FILE}")

    # Generate and print report
    report = generate_report(records, revalidation, elapsed)
    with open(REPORT_FILE, "w") as f:
        f.write(report)
    print(f"Report saved to {REPORT_FILE}")
    print(report)


if __name__ == "__main__":
    main()
