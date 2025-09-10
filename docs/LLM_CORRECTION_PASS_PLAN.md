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
7. **Low-Quality OCR Detection**: Flag pages with nonsense OCR (images, handwriting failures) for high-quality reprocessing
8. **Database Schema Idempotency**: Both LLM correction script AND main image indexer must idempotently handle table upgrades

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
- **Smart UI display** with corrected text by default and original text toggle
- **Historical accuracy preservation** with easy access to original OCR
- **Low-quality OCR detection** and flagging for high-quality reprocessing
- **Intelligent reprocessing queue** for pages with nonsense OCR output

### Technical Approach
- Integration with OpenAI GPT-4 or Claude via API
- Specialized prompts for legal document correction
- Confidence scoring and human review workflows
- 429 response handling by exiting processing loop
- Cost monitoring and optimization
- Batch processing with progress tracking
- Database schema for version control
- **Helper Module Architecture**: OCR quality assessment system in `helpers/ocr_quality_assessment.py`

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

### Data Flow Integration

**Current OCR Text Flow**:
1. `view_image()` route calls `get_ocr_text(image['file_path'])`
2. `get_ocr_text()` reads `.txt` file from filesystem
3. Template displays text in `.text-content` div

**Enhanced Flow with LLM Corrections**:
1. `view_image()` route checks for corrected text in `ocr_corrections` table
2. If corrected text exists:
   - Fetch both original and corrected text
   - Pass both to template with confidence score
3. If no corrected text exists:
   - Fall back to current behavior (original OCR only)
4. Template displays corrected text by default with toggle option

**API Endpoint Updates**:
- Modify `/api/document/<int:doc_id>` to include correction data
- Add new fields: `has_corrected_text`, `correction_confidence`, `correction_reason`
- Maintain backward compatibility for documents without corrections

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
3. **Round 1 - LLM Correction**: Send to AI for OCR correction only
4. **Round 2 - Quality Assessment**: Compare original vs corrected text
5. **JSON Parsing**: Parse assessment using dirtyjson for robustness
6. **Storage**: Save both original and corrected versions with assessment data
7. **Review Queue**: Flag corrections marked as needing review

### Legal Document Prompts

**Two-Round Correction Process**:

**Round 1: OCR Correction**
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

CRITICAL RESTRICTIONS - DO NOT:
- Change the meaning or substance of any legal text
- Modify legal arguments, claims, or statements
- Alter dates, numbers, or factual content
- Rewrite or rephrase sentences for clarity
- Add interpretation or commentary
- Change legal citations or references
- Modify signatures, names, or official designations
- Transform the document in any substantive way

REMEMBER: You are correcting OCR/transcription errors ONLY, not improving or modifying the legal content itself.

INPUT TEXT:
[OCR_TEXT]

Provide ONLY the corrected text. Do not include any explanations or scores.
```

**Round 2: Quality Assessment**
```
You are an OCR correction quality assessor. Compare the original OCR text with the corrected version and provide a JSON assessment.

ORIGINAL OCR TEXT:
[ORIGINAL_TEXT]

CORRECTED TEXT:
[CORRECTED_TEXT]

Provide a JSON response with the following structure:
{
  "quality_score": 85,
  "improvement_level": "significant",
  "major_corrections": ["fixed spacing", "corrected proper names"],
  "confidence": "high",
  "needs_review": false
}

Valid values:
- quality_score: 1-100 (overall quality of correction)
- improvement_level: "minimal", "moderate", "significant", "substantial"
- major_corrections: array of strings describing key improvements
- confidence: "low", "medium", "high"
- needs_review: boolean (true if human review recommended)
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
    quality_score INTEGER, -- 1-100 from Round 2 assessment
    improvement_level TEXT, -- 'minimal', 'moderate', 'significant', 'substantial'
    major_corrections TEXT, -- JSON array of correction descriptions
    confidence TEXT, -- 'low', 'medium', 'high'
    needs_review BOOLEAN DEFAULT FALSE,
    assessment_json TEXT, -- Full JSON response from Round 2
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
-- Add fields to track correction status (idempotent)
ALTER TABLE images ADD COLUMN has_corrected_text BOOLEAN DEFAULT FALSE;
ALTER TABLE images ADD COLUMN correction_confidence INTEGER DEFAULT NULL;
ALTER TABLE images ADD COLUMN correction_status TEXT DEFAULT 'none'; -- 'none', 'pending', 'completed', 'review_needed'

-- Add OCR quality tracking fields (idempotent)
ALTER TABLE images ADD COLUMN ocr_quality_score INTEGER DEFAULT NULL;
ALTER TABLE images ADD COLUMN ocr_quality_status TEXT DEFAULT 'pending'; -- 'pending', 'high_quality', 'needs_correction', 'reprocess_required'
ALTER TABLE images ADD COLUMN reprocess_priority INTEGER DEFAULT 0; -- Higher numbers = higher priority
```

### Database Schema Idempotency

**Critical Requirement**: Both the LLM correction script and the main image indexer (`index_images.py`) must handle database schema changes idempotently.

**Implementation Strategy**:
1. **Check before ALTER**: Use `PRAGMA table_info()` to check if columns exist before adding them
2. **Safe ALTER statements**: Use `IF NOT EXISTS` or equivalent patterns where supported
3. **Graceful handling**: Handle "column already exists" errors without failing
4. **Version tracking**: Consider adding a schema version table to track applied migrations

**Example Idempotent Schema Update**:
```python
def ensure_database_schema(conn):
    """Idempotently ensure database schema is up to date"""
    
    # Check if ocr_corrections table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ocr_corrections'")
    if not cursor.fetchone():
        # Create ocr_corrections table
        conn.execute("""
            CREATE TABLE ocr_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                quality_score INTEGER,
                improvement_level TEXT,
                major_corrections TEXT,
                confidence TEXT,
                needs_review BOOLEAN DEFAULT FALSE,
                assessment_json TEXT,
                llm_model TEXT NOT NULL,
                llm_version TEXT,
                api_cost_usd REAL DEFAULT 0.0,
                processing_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
            )
        """)
    
    # Check and add columns to images table idempotently
    cursor = conn.execute("PRAGMA table_info(images)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    required_columns = [
        ('has_corrected_text', 'BOOLEAN DEFAULT FALSE'),
        ('correction_confidence', 'INTEGER DEFAULT NULL'),
        ('correction_status', 'TEXT DEFAULT "none"'),
        ('ocr_quality_score', 'INTEGER DEFAULT NULL'),
        ('ocr_quality_status', 'TEXT DEFAULT "pending"'),
        ('reprocess_priority', 'INTEGER DEFAULT 0')
    ]
    
    for column_name, column_def in required_columns:
        if column_name not in existing_columns:
            try:
                conn.execute(f"ALTER TABLE images ADD COLUMN {column_name} {column_def}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise  # Re-raise if it's not a duplicate column error
```

**Integration Points**:
- **`index_images.py`**: Must call `ensure_database_schema()` before processing
- **LLM Correction Script**: Must call `ensure_database_schema()` before processing
- **App startup**: Consider calling schema check on app initialization
- **Migration safety**: Both scripts can run simultaneously without conflicts

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

# Token Counting
USE_TIKTOKEN=true
TOKEN_ESTIMATION_BUFFER=0.03  # 3% buffer for token estimation

# JSON Parsing
USE_DIRTYJSON=true  # Use dirtyjson for robust JSON parsing
```

### Token Counting & Cost Estimation

**Token Calculation Formula**:
```python
import tiktoken

def calculate_token_estimate(prompt: str, ocr_text: str) -> int:
    """
    Calculate estimated tokens for API request
    
    Formula: prompt_tokens + (ocr_text_tokens * 2) + 3% buffer
    - OCR text is multiplied by 2 to account for input + output
    - 3% buffer accounts for response overhead and variations
    """
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    prompt_tokens = len(encoding.encode(prompt))
    ocr_tokens = len(encoding.encode(ocr_text))
    
    # Apply formula: prompt + (ocr * 2) + 3% buffer
    total_tokens = prompt_tokens + (ocr_tokens * 2)
    buffer_tokens = int(total_tokens * 0.03)
    
    return total_tokens + buffer_tokens
```

**Cost Estimation**:
- Use tiktoken for accurate token counting
- Apply 3% buffer to account for response variations
- Track both input and output token estimates
- Monitor actual vs estimated costs for accuracy

### Cost Optimization Strategies

1. **Smart Batching**: Group similar documents for batch processing
2. **Token Optimization**: Truncate very long documents intelligently
3. **Confidence Thresholds**: Skip high-confidence corrections
4. **Caching**: Cache similar corrections to avoid duplicate API calls
5. **Cost Monitoring**: Real-time cost tracking with automatic shutdown
6. **429 Handling**: Exit processing loop on rate limit to let cron job retry later
7. **Accurate Token Counting**: Use tiktoken for precise cost estimation
8. **Token Budget Management**: Set per-document token limits based on cost targets

### UI/UX Implementation for Corrected OCR Display

**Integration with Existing Document Viewer**:
The LLM correction feature will integrate seamlessly with the current split-panel viewer layout:
- **Left Panel**: Document image (unchanged)
- **Right Panel**: Text panel with enhanced OCR display functionality
- **Current Text Panel**: 400px width, dark theme (#2c3e50), scrollable text content area

**Default Display Behavior**:
- Corrected OCR text is displayed by default in the existing `.text-content` div
- Users see the improved, readable version immediately upon page load
- Original OCR text is preserved and accessible via toggle button
- Maintains existing styling: `white-space: pre-wrap`, `line-height: 1.7`, `color: #e8e8e8`

**User Interface Elements** (Integrated into existing layout):
- **Text Panel Header Enhancement**: 
  - Current: `<h6><i class="fas fa-file-text me-2"></i>Extracted Text</h6>`
  - Enhanced: Add confidence badge and toggle button to header
- **"View Original" Toggle Button**: 
  - Positioned in text panel header next to "Extracted Text"
  - Styled to match existing `.nav-btn` design
  - Icon: `fas fa-history` for original, `fas fa-magic` for corrected
- **Confidence Indicator**: 
  - Color-coded badge in header (green=high, yellow=medium, red=low)
  - Tooltip showing confidence percentage and correction summary
- **Seamless Text Switching**: 
  - JavaScript toggle without page reload
  - Smooth fade transition between versions
  - Preserve scroll position when switching

**Text Panel Enhancements**:
- **Header Layout**: 
  ```html
  <div class="d-flex justify-content-between align-items-center mb-3">
      <h6 class="mb-0"><i class="fas fa-file-text me-2"></i>Extracted Text</h6>
      <div class="d-flex align-items-center gap-2">
          <span class="confidence-badge">High</span>
          <button class="nav-btn btn-sm" onclick="toggleOCRVersion()">
              <i class="fas fa-history"></i>View Original
          </button>
      </div>
  </div>
  ```
- **Text Content Area**: 
  - Add data attributes for both versions: `data-original-text` and `data-corrected-text`
  - Maintain existing `.text-content` styling
  - Add subtle visual indicator when showing corrected text

**Legal Accuracy Considerations**:
- Original text always accessible for historical accuracy
- Clear labeling: "Corrected Text" vs "Original OCR Text"
- Audit trail of corrections for legal compliance
- Download options for both versions (add to existing download functionality)
- Preserve existing `white-space: pre-wrap` formatting for both versions

**Visual Design Integration**:
- **Confidence Badge Styling**:
  ```css
  .confidence-badge {
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
  }
  .confidence-high { background: #28a745; color: white; }
  .confidence-medium { background: #ffc107; color: #212529; }
  .confidence-low { background: #dc3545; color: white; }
  ```
- **Toggle Button States**:
  - Active state: `fas fa-magic` with blue highlight
  - Inactive state: `fas fa-history` with standard nav-btn styling
- **Smooth Transitions**: 
  - Fade effect when switching between versions
  - Maintain existing scrollbar styling
  - Responsive design preserved for mobile (text panel becomes bottom panel)

**Mobile Responsive Considerations**:
- Toggle button and confidence badge work in mobile layout
- Text panel header adjusts for smaller screens
- Maintains existing mobile breakpoints and styling

### Low-Quality OCR Detection & Reprocessing

**Problem Identification**:
Many pages contain OCR output that is complete nonsense due to:
- Pages with multiple images/photos that OCR attempts to read as text
- Handwritten content that fails standard OCR processing
- Poor scan quality or skewed pages
- Complex layouts that confuse OCR engines
- Non-text elements (charts, diagrams) processed as text

**Detection Strategy**:
1. **Content Analysis**: Use LLM to evaluate OCR text quality
2. **Pattern Recognition**: Identify common nonsense patterns
3. **Confidence Thresholds**: Flag text below quality thresholds
4. **Manual Review Queue**: Human verification of flagged content

**Quality Assessment Prompts**:
```
You are an OCR quality assessment specialist. Evaluate the following OCR text for quality and readability.

ASSESSMENT CRITERIA:
1. Is this text coherent and readable?
2. Does it contain meaningful legal content?
3. Are there obvious OCR errors or nonsense characters?
4. Is the text structure logical (sentences, paragraphs)?
5. Does it appear to be actual document content vs. OCR artifacts?

OCR TEXT TO ASSESS:
[OCR_TEXT]

Provide:
- Quality Score (1-100)
- Assessment: "HIGH_QUALITY", "NEEDS_CORRECTION", or "REPROCESS_REQUIRED"
- Reason for assessment
- Specific issues identified
```

**Reprocessing Workflow**:
1. **Detection Phase**: Flag low-quality OCR during correction pass
2. **Queue Management**: Add flagged pages to high-quality reprocessing queue
3. **Priority Processing**: Process flagged pages with advanced OCR engines
4. **Quality Verification**: Re-assess after reprocessing
5. **Integration**: Merge improved OCR with existing correction system

**Database Schema Updates**:
```sql
-- Add OCR quality tracking
ALTER TABLE images ADD COLUMN ocr_quality_score INTEGER DEFAULT NULL;
ALTER TABLE images ADD COLUMN ocr_quality_status TEXT DEFAULT 'pending'; -- 'pending', 'high_quality', 'needs_correction', 'reprocess_required'
ALTER TABLE images ADD COLUMN reprocess_priority INTEGER DEFAULT 0; -- Higher numbers = higher priority

-- Track reprocessing attempts
CREATE TABLE ocr_reprocessing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    original_quality_score INTEGER,
    reprocess_reason TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued', -- 'queued', 'processing', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
);
```

**Integration Points & Required Changes**:

**1. Error Detection System (`helpers/error_detection.py`)**:
- Add OCR quality assessment methods
- Integrate with existing error detection patterns
- Add quality scoring to existing detection pipeline
- Coordinate with LLM correction pass

**1a. New Helper Module (`helpers/ocr_quality_assessment.py`)**:
- Create dedicated module for OCR quality assessment
- Implement LLM-based quality scoring
- Handle reprocessing queue management
- Coordinate with existing error detection system
- Follow existing helper module patterns and structure

**Helper Module Structure**:
```python
# helpers/ocr_quality_assessment.py
import tiktoken
import dirtyjson
from typing import Dict, Any, Optional

class OCRQualityAssessment:
    """OCR quality assessment and reprocessing queue management"""
    
    def __init__(self, db_path: str, llm_client: LLMClient):
        self.db_path = db_path
        self.llm_client = llm_client
        self.encoding = tiktoken.encoding_for_model("gpt-4")
    
    def calculate_token_estimate(self, prompt: str, ocr_text: str) -> int:
        """Calculate token estimate using tiktoken with 3% buffer"""
        prompt_tokens = len(self.encoding.encode(prompt))
        ocr_tokens = len(self.encoding.encode(ocr_text))
        total_tokens = prompt_tokens + (ocr_tokens * 2)
        buffer_tokens = int(total_tokens * 0.03)
        return total_tokens + buffer_tokens
    
    def correct_ocr_text(self, ocr_text: str) -> str:
        """Round 1: Correct OCR text using LLM"""
        pass
    
    def assess_correction_quality(self, original_text: str, corrected_text: str) -> Dict[str, Any]:
        """Round 2: Assess correction quality and return JSON"""
        pass
    
    def parse_assessment_json(self, json_response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response using dirtyjson for robustness"""
        try:
            return dirtyjson.loads(json_response)
        except Exception as e:
            # Fallback parsing or logging
            return None
    
    def flag_for_reprocessing(self, image_id: int, reason: str, priority: int = 0):
        """Add image to reprocessing queue"""
        pass
    
    def get_reprocessing_queue(self, status: str = None) -> List[Dict]:
        """Get items from reprocessing queue"""
        pass
    
    def process_reprocessing_queue(self, batch_size: int = 10):
        """Process items in reprocessing queue"""
        pass
```

**Integration with Existing Helpers**:
- Coordinate with `helpers/error_detection.py` for quality patterns
- Use similar patterns to `helpers/ocr_sync/ocr_sync.py` for API calls
- Follow existing helper module patterns and structure

**2. OCR Processing Systems**:
- **`ocr_processor.py`**: Add high-quality reprocessing mode
- **`ocr_processor_lite.py`**: Skip pages flagged for reprocessing
- **Cron Job Management**: Ensure reprocessing doesn't conflict with lite OCR cron
- **Priority Processing**: Implement queue-based processing for flagged pages

**3. Database Schema Updates**:
- Add quality tracking columns to `images` table
- Create `ocr_reprocessing_queue` table
- Update existing queries to include quality data
- Add indexes for performance

**4. Application Routes (`app.py`)**:
- Update `view_image()` route to include quality status
- Add admin endpoints for queue management
- Modify API endpoints to include quality data
- Add reprocessing status indicators

**5. UI/UX Updates**:
- **Document Viewer**: Show quality status and reprocessing indicators
- **Admin Dashboard**: Add reprocessing queue management interface
- **Search Results**: Include quality indicators in search results
- **Progress Tracking**: Show reprocessing progress in admin interface

**6. Configuration & Environment**:
- Add quality threshold settings
- Configure reprocessing priorities
- Set up queue management parameters
- Add monitoring for reprocessing pipeline

**7. Monitoring & Logging**:
- Track reprocessing success/failure rates
- Monitor quality improvement metrics
- Log reprocessing decisions and reasons
- Alert on queue backlog or processing failures

### Quality Assurance

1. **Confidence Scoring**: Every correction gets a 1-100 confidence score
2. **Human Review**: Low-confidence corrections flagged for review
3. **A/B Testing**: Compare different models and prompts
4. **Sample Validation**: Manual review of random corrections
5. **Feedback Loop**: Learn from human corrections to improve prompts
6. **OCR Quality Assessment**: Automated detection of low-quality OCR output
7. **Reprocessing Verification**: Quality checks after high-quality OCR reprocessing

### Rollout Strategy (Safe, Incremental & Idempotent)

1. **Phase 1**: Database schema and basic LLM integration
2. **Phase 2**: Legal document prompts and confidence scoring
3. **Phase 3**: Low-quality OCR detection and reprocessing queue
4. **Phase 4**: Human review workflows and cost monitoring
5. **Phase 5**: Batch processing and optimization
6. **Phase 6**: UI/UX Integration & Display
7. **Phase 7**: Full production deployment with monitoring

**Idempotency Testing**:
- Verify safe re-runs don't duplicate API calls
- Test interrupted process recovery
- Validate cost tracking accuracy
- Confirm database state consistency

## Implementation Priority

**Phase 1: Database Schema & Basic Integration**
- Add correction tables to database with idempotent schema updates
- Implement basic LLM API integration
- Add cost tracking and rate limiting
- Ensure both `index_images.py` and LLM correction script handle schema changes idempotently

**Phase 2: Legal Document Processing**
- Develop specialized legal prompts
- Implement confidence scoring
- Add document type detection

**Phase 3: Low-Quality OCR Detection & Reprocessing**
- Create `helpers/ocr_quality_assessment.py` module
- Implement OCR quality assessment using LLM
- Create reprocessing queue management system
- Add database schema for quality tracking
- Integrate with existing error detection system
- Coordinate with OCR processing pipelines

**Phase 4: Review Workflows**
- Build human review interface
- Implement approval/rejection workflows
- Add correction versioning

**Phase 5: Optimization & Monitoring**
- Add cost monitoring dashboard
- Implement smart batching
- Add performance metrics

**Phase 6: UI/UX Integration & Display**
- **Backend Changes**:
  - Modify `view_image()` route to fetch both original and corrected OCR text
  - Add new template variables: `ocr_original_text`, `ocr_corrected_text`, `correction_confidence`
  - Update `get_ocr_text()` function to support corrected text retrieval
  - Add database queries to fetch correction data from `ocr_corrections` table
- **Frontend Changes**:
  - Enhance text panel header with confidence badge and toggle button
  - Add JavaScript for seamless text switching without page reload
  - Implement smooth fade transitions between original and corrected text
  - Add responsive design considerations for mobile layout
- **Template Updates**:
  - Modify `templates/viewer.html` text panel section
  - Add data attributes for both text versions
  - Include confidence scoring display and correction metadata
- **User Experience**:
  - Display corrected OCR text by default in document viewer
  - Add "View Original" button for historical accuracy
  - Preserve original text accessibility for legal accuracy
  - Maintain existing styling and responsive behavior

## Success Metrics

- **Accuracy**: >95% of corrections improve readability
- **Cost**: <$0.10 per document average
- **Speed**: <30 seconds per document average
- **Coverage**: Process 1000+ documents per day
- **Quality**: <5% of corrections need human review

---

**Note**: This project plan will be updated as the LLM Correction Pass feature is implemented and new requirements are identified.
