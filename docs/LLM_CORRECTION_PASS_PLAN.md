# LLM Correction Pass - Project Plan

**Date**: September 9, 2025  
**Status**: Planning Phase  
**Feature**: LLM Correction Pass 🤖

## Overview

This document outlines the implementation plan for the LLM Correction Pass feature, which uses large language models to correct and enhance OCR text with contextual understanding, specifically optimized for legal documents.

## Critical Implementation Requirements

**⚠️ IMPORTANT**: 
1. **API Rate Limiting**: Respect 429 responses from LLM APIs by exiting the processing loop
2. **Cost Control**: Implement cost monitoring to prevent runaway API costs
3. **Idempotency**: The entire LLM Correction Pass system MUST be idempotent and safe to re-run
4. **Side-by-side Storage**: Always preserve original OCR text alongside corrected versions
5. **Confidence Scoring**: Every correction must have a confidence score for human review
6. **Legal Document Optimization**: Specialized prompts and processing for legal document context

## LLM Correction Pass 🤖

### Goal
Use AI to correct and enhance OCR text with contextual understanding, specifically optimized for legal documents from the Epstein case.

### Features
- **Contextual corrections** using large language models (GPT-4/Claude)
- **Side-by-side storage** of raw vs corrected text
- **Confidence scoring** for each correction
- **Legal document optimization** with specialized prompts
- **Version control** for text corrections
- **Cost monitoring** and rate limiting
- **Human review workflows** for low-confidence corrections

### Technical Approach
- Integration with OpenAI GPT-4 or Claude via API
- Specialized prompts for legal document correction
- Confidence scoring and human review workflows
- 429 response handling by exiting processing loop
- Cost monitoring and optimization
- Batch processing with progress tracking
- Database schema for version control

### Implementation Steps
1. **Phase 1**: Database schema for corrected text storage
2. **Phase 2**: LLM integration and API management
3. **Phase 3**: Legal document correction prompts
4. **Phase 4**: Confidence scoring and review workflows
5. **Phase 5**: Cost monitoring and optimization

## Detailed Specification

### Inputs / Outputs
* **Input:** Raw OCR text, document metadata, legal context
* **Output:** Corrected OCR text, confidence scores, correction reasons, version history

### LLM Integration Options

**Option A: OpenAI GPT-4**
- **Pros**: Excellent legal document understanding, fast API
- **Cons**: Higher cost, rate limits
- **Cost**: ~$0.03 per 1K tokens (input), $0.06 per 1K tokens (output)

**Option B: Anthropic Claude**
- **Pros**: Excellent for long documents, good legal understanding
- **Cons**: Slower API, different rate limits
- **Cost**: ~$0.015 per 1K tokens (input), $0.075 per 1K tokens (output)

**Recommendation**: Start with GPT-4 for better legal document performance

### Correction Workflow

1. **Pre-processing**: Clean and prepare OCR text
2. **Context Analysis**: Determine document type and legal context
3. **LLM Correction**: Send to AI with specialized prompts
4. **Confidence Scoring**: Analyze correction quality
5. **Storage**: Save both original and corrected versions
6. **Review Queue**: Flag low-confidence corrections for human review

### Legal Document Prompts

**Base Prompt Template**:
```
You are an expert legal document OCR correction specialist. Your task is to correct OCR errors in legal documents while preserving the original meaning and legal terminology.

DOCUMENT CONTEXT:
- Document Type: [Legal Brief/Court Filing/Correspondence/etc.]
- Case: United States v. Maxwell (Epstein case)
- Date Range: 2020-2024

CORRECTION GUIDELINES:
1. Fix obvious OCR errors (character recognition mistakes)
2. Correct spacing and punctuation
3. Preserve legal terminology and proper names
4. Maintain original document structure
5. Do not add content not present in the original
6. Flag uncertain corrections with [UNCERTAIN: reason]

INPUT TEXT:
[OCR_TEXT]

Provide the corrected text with confidence score (1-100) and brief explanation of major corrections made.
```

### Data Model

**New Database Tables**:

```sql
-- Store corrected OCR text with version control
CREATE TABLE ocr_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    confidence_score INTEGER NOT NULL, -- 1-100
    correction_reason TEXT,
    llm_model TEXT NOT NULL, -- 'gpt-4', 'claude-3', etc.
    llm_version TEXT,
    api_cost_usd REAL DEFAULT 0.0,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
);

-- Track correction review status
CREATE TABLE correction_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correction_id INTEGER NOT NULL,
    reviewer_id TEXT, -- User ID or 'system'
    review_status TEXT NOT NULL, -- 'pending', 'approved', 'rejected', 'needs_review'
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (correction_id) REFERENCES ocr_corrections (id) ON DELETE CASCADE
);

-- API usage tracking for cost monitoring
CREATE TABLE llm_api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER
);
```

**Updates to existing `images` table**:
```sql
-- Add fields to track correction status
ALTER TABLE images ADD COLUMN has_corrected_text BOOLEAN DEFAULT FALSE;
ALTER TABLE images ADD COLUMN correction_confidence INTEGER DEFAULT NULL;
ALTER TABLE images ADD COLUMN correction_status TEXT DEFAULT 'none'; -- 'none', 'pending', 'completed', 'review_needed'
```

### Configuration (Environment Variables)

```bash
# LLM API Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
DEFAULT_LLM_MODEL=gpt-4
FALLBACK_LLM_MODEL=claude-3-sonnet

# Cost Control & API Handling
MAX_DAILY_API_COST_USD=50.0
MAX_TOKENS_PER_REQUEST=8000
BATCH_SIZE=10

# Correction Settings
MIN_CONFIDENCE_FOR_AUTO_APPROVAL=80
REVIEW_QUEUE_SIZE_LIMIT=100
ENABLE_HUMAN_REVIEW=true
```

### Cost Optimization Strategies

1. **Smart Batching**: Group similar documents for batch processing
2. **Token Optimization**: Truncate very long documents intelligently
3. **Confidence Thresholds**: Skip high-confidence corrections
4. **Caching**: Cache similar corrections to avoid duplicate API calls
5. **Cost Monitoring**: Real-time cost tracking with automatic shutdown
6. **429 Handling**: Exit processing loop on rate limit to let cron job retry later

### Quality Assurance

1. **Confidence Scoring**: Every correction gets a 1-100 confidence score
2. **Human Review**: Low-confidence corrections flagged for review
3. **A/B Testing**: Compare different models and prompts
4. **Sample Validation**: Manual review of random corrections
5. **Feedback Loop**: Learn from human corrections to improve prompts

### Rollout Strategy (Safe, Incremental & Idempotent)

1. **Phase 1**: Database schema and basic LLM integration
2. **Phase 2**: Legal document prompts and confidence scoring
3. **Phase 3**: Human review workflows and cost monitoring
4. **Phase 4**: Batch processing and optimization
5. **Phase 5**: Full production deployment with monitoring

**Idempotency Testing**:
- Verify safe re-runs don't duplicate API calls
- Test interrupted process recovery
- Validate cost tracking accuracy
- Confirm database state consistency

## Implementation Priority

**Phase 1: Database Schema & Basic Integration**
- Add correction tables to database
- Implement basic LLM API integration
- Add cost tracking and rate limiting

**Phase 2: Legal Document Processing**
- Develop specialized legal prompts
- Implement confidence scoring
- Add document type detection

**Phase 3: Review Workflows**
- Build human review interface
- Implement approval/rejection workflows
- Add correction versioning

**Phase 4: Optimization & Monitoring**
- Add cost monitoring dashboard
- Implement smart batching
- Add performance metrics

## Success Metrics

- **Accuracy**: >95% of corrections improve readability
- **Cost**: <$0.10 per document average
- **Speed**: <30 seconds per document average
- **Coverage**: Process 1000+ documents per day
- **Quality**: <5% of corrections need human review

---

**Note**: This project plan will be updated as the LLM Correction Pass feature is implemented and new requirements are identified.
