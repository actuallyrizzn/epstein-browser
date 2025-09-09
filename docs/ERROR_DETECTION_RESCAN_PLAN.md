# Error Detection & Rescan Pass - Project Plan

**Date**: September 7, 2025  
**Status**: Planning Phase  
**Feature**: Error Detection & Rescan Pass 🔍

## Overview

This document outlines the implementation plan for the Error Detection & Rescan Pass feature, which automatically identifies low-quality OCR pages and reprocesses them with smarter preprocessing and engine choices.

## Critical Implementation Note

**⚠️ IMPORTANT**: If we hit a 429 error indicating a DAILY limit hit, the script should exit gracefully and NOT perform any retries. This prevents unnecessary API calls and respects rate limits.

## Error Detection & Rescan Pass 🔍

### Goal
Identify and fix poor OCR quality automatically using machine learning and multiple preprocessing techniques.

### Features
- **Garbage detection** for pages with patterns like "0. 0 00 0"
- **Quality scoring** based on character patterns and word frequency
- **Automatic rescanning** with different preprocessing techniques
- **Confidence thresholds** for OCR quality assessment
- **Batch reprocessing** of flagged documents

### Technical Approach
- Machine learning models to detect OCR quality
- Multiple preprocessing pipelines (contrast, denoising, rotation)
- A/B testing of different OCR engines
- Quality metrics dashboard for monitoring
- **Daily limit handling**: Exit gracefully on 429 errors (no retries)

### Implementation Steps
1. Create OCR quality detection models
2. Implement preprocessing pipeline variations
3. Build batch processing system
4. Create quality metrics dashboard
5. Add 429 error handling with graceful exit

### Working Stub Available
**Status**: ✅ Basic implementation working

We have a working stub that successfully identifies and re-processes bad OCR files:

**Key Features**:
- Detects files with only zeros, spaces, or very short content (< 10 chars)
- Identifies corresponding image files (.tif, .jpg, .jpeg, .png)
- Re-runs tesseract with better settings (--psm 3)
- Validates new OCR results before considering success
- Batch processing with progress reporting

**Current Detection Logic**:
- Very short content (< 10 characters)
- Content that's just repeated zeros with spaces
- Content that's all zeros when stripped of whitespace

**Next Enhancements Needed**:
- Add 429 error handling for any LLM integration
- Improve quality scoring beyond basic length checks
- Add confidence thresholds
- Implement preprocessing pipeline variations
- Add quality metrics dashboard

## Detailed Specification

### Inputs / Outputs
* **Input:** page record (`images.id`), raw OCR text (if present), source image path
* **Output:** corrected OCR text (or failure), quality score, reason codes, audit trail, and rescan status

### Detection Signals (Scored & Combined)
1. **Text length outliers**: `len(raw_text) < 20` and adjacent pages average `>200` chars → suspect
2. **Character diversity**: Ratio of unique alphanumerics to total chars; flag if `< 0.08`
3. **Garbage pattern detectors**: Regex bank for "0 0 00 0", `^O{10,}$`, `^[0\s\W]{N,}$`, repeated trigram runs
4. **Word dictionary hit-rate**: `% of tokens in legal/general vocab` (wordfreq + legal terms). Flag if `< 35%`
5. **Visual blankness/noise**: Downscale to 64×64; compute mean pixel variance + entropy
6. **Orientation/skew suspicion**: Hough-based skew > |3°| → mark for deskew branch
7. **Adjacency similarity**: Cosine sim (minhash/char n-grams) to previous/next page
8. **Engine confidence**: Use engine-reported confidences when present

**Quality Score**: Weighted blend → `Q ∈ [0,100]`. Below `Q_fail` routes to rescan; between `Q_warn` and `Q_fail` queues lower-priority retry.
*Defaults*: `Q_fail=35`, `Q_warn=55`, tunable per volume

### Rescan Strategy (Progressive)
1. **Preprocessing variants** (fast): grayscale → Otsu binarize → adaptive threshold
2. **Orientation sweep**: Try rotations: 90, 180, 270 if non-Latin ratios dominate
3. **Alternate OCR engine (A/B)**: Keep EasyOCR as A; try Tesseract lstm with legal-trained language pack
4. **Last-chance composite**: Split page into bands/columns, OCR per region, reassemble
5. **Fail-out**: Mark `needs_manual_review=true` after N attempts (default 3)

### Data Model
```sql
CREATE TABLE ocr_quality (
  page_id INTEGER PRIMARY KEY,
  q_score INTEGER NOT NULL,            -- 0..100
  reason_codes TEXT NOT NULL,          -- e.g. "LEN,CHAR_DIV,DICT"
  engine_id TEXT,                      -- "easyocr|tesseract"
  attempts INTEGER DEFAULT 0,
  last_attempt_at DATETIME,
  needs_manual_review BOOLEAN DEFAULT 0,
  corrected BOOLEAN DEFAULT 0,         -- downstream LLM pass can set true
  FOREIGN KEY(page_id) REFERENCES images(id)
);
```

### Configuration (Environment Variables)
```
Q_FAIL=35
Q_WARN=55
OCR_MAX_ATTEMPTS=3
OCR_ALT_ENGINE_ENABLED=true
OCR_UPSCALE_DPI=450
OCR_QUEUE_PARALLELISM=4
```

### Rollout Order (Safe & Incremental)
1. Ship detectors → **score only** (no rescan), watch dashboard 24h
2. Enable rescans for `Q < Q_fail` (small concurrency)
3. Turn on orientation/deskew branch; then alt engine A/B
4. Tune thresholds; increase concurrency
5. Hand off persistent failures to **LLM correction** phase

## Next Steps

1. **Phase 1**: Implement detection signals and quality scoring
2. **Phase 2**: Build rescan pipeline with preprocessing variants
3. **Phase 3**: Add alternate OCR engine support
4. **Phase 4**: Implement admin dashboard metrics
5. **Phase 5**: Deploy with safe rollout strategy

---

**Note**: This project plan will be updated as the Error Detection & Rescan Pass feature is implemented and new requirements are identified.
