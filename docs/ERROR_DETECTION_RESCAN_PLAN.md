# Error Detection & Rescan Pass - Project Plan

**Date**: September 7, 2025  
**Status**: Planning Phase  
**Feature**: Error Detection & Rescan Pass 🔍

## Overview

This document outlines the implementation plan for the Error Detection & Rescan Pass feature, which automatically identifies low-quality OCR pages and reprocesses them with smarter preprocessing and engine choices.

## Critical Implementation Requirements

**⚠️ IMPORTANT**: 
1. **Daily Limit Handling**: If we hit a 429 error indicating a DAILY limit hit, the script should exit gracefully and NOT perform any retries. This prevents unnecessary API calls and respects rate limits.

2. **Idempotency**: The entire Error Detection & Rescan Pass system MUST be idempotent. This means:
   - Safe to re-run without side effects
   - No duplicate processing of already-processed pages
   - State tracking prevents re-processing successful rescans
   - Atomic operations for all database writes
   - Graceful handling of interrupted processes

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

### Detection Signals (Simplified)
**Current Working Implementation**:
1. **Text length check**: `len(raw_text) < 10` characters → flag for rescan
2. **Zero pattern detection**: Content that's just repeated zeros with spaces → flag for rescan  
3. **All zeros check**: Content that's all zeros when stripped of whitespace → flag for rescan
4. **Venice AI quality check**: Use existing Venice SDK to detect catastrophic OCR failures

**Venice AI Quality Check** (using existing `helpers/venice_sdk/`):
```python
from helpers.venice_sdk import chat_complete, load_config

def check_ocr_quality_with_venice(raw_text: str) -> int:
    """Use Venice AI to check if OCR represents catastrophic failure"""
    try:
        config = load_config()
        messages = [
            {"role": "system", "content": "You are an expert at detecting catastrophic OCR failures in legal documents. Analyze this OCR text and determine if it represents a complete failure of OCR processing. CATASTROPHIC FAILURE INDICATORS: Text is mostly or entirely garbled characters, repeated patterns that make no sense (like '0 0 00 0' or '### ###'), text that appears to be random characters or symbols, content that is clearly not English words or legal text, text that looks like it came from a corrupted or unreadable image. GOOD OCR INDICATORS: Contains recognizable English words, has proper legal terminology, contains dates, names, or document references, has readable sentence structure (even with minor OCR errors). Respond with ONLY: 'CATASTROPHIC_FAILURE' if the OCR is completely unusable, 'ACCEPTABLE' if the OCR is readable despite minor errors. Do not provide explanations or corrections, just the classification."},
            {"role": "user", "content": f"Check this OCR text for catastrophic failure:\n\n{raw_text}"}
        ]
        
        response = chat_complete(messages, model="llama-3.3-70b", temperature=0.1)
        classification = response["choices"][0]["message"]["content"].strip().upper()
        
        if "CATASTROPHIC_FAILURE" in classification:
            return 0  # Bad OCR
        elif "ACCEPTABLE" in classification:
            return 100  # Good OCR
        else:
            return 0  # Default to bad on unclear response
            
    except Exception as e:
        logger.error(f"Venice AI quality check failed: {e}")
        return 0  # Default to bad on error
```

**Quality Score**: Simple 0/100 scoring:
- `100` = Good OCR (passed all checks + Venice says "ACCEPTABLE")
- `0` = Bad OCR (failed basic checks OR Venice says "CATASTROPHIC_FAILURE")
- `NULL` = Not checked yet

**Rescan Logic**: 
- If `ocr_rescan_attempts < 3` and `ocr_quality_score = 0` → rescan
- If `ocr_rescan_attempts >= 3` → give up, mark as failed

### Rescan Strategy (Simplified)
1. **Re-run tesseract with better settings**: `--psm 3` (automatic page segmentation)
2. **Validate new results**: Check if new OCR text is longer and not all zeros
3. **Fail-out**: After 3 attempts, give up and mark as failed

**Idempotency Guarantees**:
- Check `ocr_rescan_attempts` before processing
- Skip if `ocr_rescan_attempts >= 3`
- Atomic file operations: `data/ocr/<volume>/<id>.txt.tmp` → rename to `.txt` on success
- Update `ocr_rescan_attempts` counter after each attempt

### Data Model
**Simplified Approach**: Add fields to existing `images` table instead of creating a separate table.

```sql
-- Add these fields to the existing images table
ALTER TABLE images ADD COLUMN ocr_quality_score INTEGER DEFAULT NULL;  -- 0-100, NULL = not checked yet
ALTER TABLE images ADD COLUMN ocr_rescan_attempts INTEGER DEFAULT 0;   -- for idempotency (max 3)
```

**Database Migration Required**:
- Update `init_database()` functions in `app.py` and `index_images.py` to include these fields
- Add migration logic to check for existing fields and add them if missing
- Existing installations will need the scan tool to add these fields automatically

**⚠️ CRITICAL ARCHITECTURAL REQUIREMENT**:
The **image indexer** (`index_images.py`) is the component that initially builds the database, not the main Flask app. Therefore:

1. **Image Indexer Schema Updates**: The `index_images.py` script MUST handle idempotent schema updates
2. **Error Detection Script Schema Updates**: Any error detection/rescan scripts MUST also handle idempotent schema updates
3. **Main App Schema Updates**: The Flask app (`app.py`) should only handle schema updates for production environments where the database already exists

**Implementation Priority**:
- **Primary**: Update `index_images.py` to handle schema migrations idempotently
- **Secondary**: Update error detection scripts to handle schema migrations idempotently  
- **Tertiary**: Ensure Flask app schema updates work for existing production databases

This ensures that whether the database is being built fresh (via indexer) or updated (via error detection), all schema changes are handled consistently and idempotently.

### Configuration (Environment Variables)
```
OCR_MAX_ATTEMPTS=3
OCR_QUEUE_PARALLELISM=4
```

### Rollout Order (Safe, Incremental & Idempotent)
1. **Add database fields** to existing `images` table
2. **Run quality detection** on all existing OCR files (score only, no rescan)
3. **Enable rescan processing** for files with `ocr_quality_score = 0`
4. **Monitor progress** and tune concurrency as needed

**Idempotency Testing**:
- Verify safe re-runs don't duplicate work
- Test interrupted process recovery
- Validate atomic file operations
- Confirm database state consistency

## Next Steps

1. **Phase 1**: Add database fields to `images` table
2. **Phase 2**: Implement simple quality detection (length + zero checks)
3. **Phase 3**: Build rescan pipeline with tesseract `--psm 3`
4. **Phase 4**: Add migration logic for existing installations
5. **Phase 5**: Deploy with safe rollout strategy

---

**Note**: This project plan will be updated as the Error Detection & Rescan Pass feature is implemented and new requirements are identified.
