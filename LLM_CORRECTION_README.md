# LLM Correction Pass System

This system uses Large Language Models (GPT-4/Claude) to correct and enhance OCR text with contextual understanding, specifically optimized for legal documents from the Epstein case.

## 🚀 Quick Start

### 1. Set up API Keys
```bash
# For OpenAI GPT-4
export OPENAI_API_KEY="your_openai_key_here"

# For Anthropic Claude (alternative)
export ANTHROPIC_API_KEY="your_anthropic_key_here"
```

### 2. Run the Correction Processor
```bash
# Process 10 images with GPT-4
python llm_correction_processor.py --model gpt-4 --batch-size 10

# Process with Claude
python llm_correction_processor.py --model claude-3-sonnet --batch-size 5
```

### 3. View Results
- Open the document viewer in your browser
- Documents with corrections will show a confidence badge and "View Original" button
- Click the button to toggle between corrected and original text

## 📁 File Structure

```
├── helpers/
│   ├── ocr_quality_assessment.py    # Main correction logic
│   └── llm_client.py                # LLM API wrapper
├── llm_correction_processor.py      # Main processing script
├── llm_correction_config.py         # Configuration management
├── test_llm_correction.py           # Test suite
└── LLM_CORRECTION_README.md         # This file
```

## 🔧 Configuration

All configuration is handled via environment variables:

```bash
# Database
DATABASE_PATH=images.db

# LLM Settings
DEFAULT_LLM_MODEL=gpt-4
FALLBACK_LLM_MODEL=claude-3-sonnet

# Cost Control
MAX_DAILY_API_COST_USD=50.0
MAX_TOKENS_PER_REQUEST=8000
BATCH_SIZE=10

# Processing
RATE_LIMIT_DELAY=1.0
MIN_OCR_TEXT_LENGTH=10
```

## 🏗️ Architecture

### Two-Round Process
1. **Round 1**: Correct OCR text using specialized legal prompts
2. **Round 2**: Assess correction quality and return JSON assessment

### Database Schema
- `ocr_corrections` - Stores corrected text and assessments
- `ocr_reprocessing_queue` - Tracks pages needing high-quality reprocessing
- `images` table - Updated with correction status columns

### UI Integration
- Document viewer shows corrected text by default
- Toggle button to view original OCR text
- Confidence badge showing correction quality
- Seamless switching without page reload

## 🧪 Testing

Run the test suite to verify everything is working:

```bash
python test_llm_correction.py
```

This will test:
- Database schema creation
- Token calculation
- Validation functions
- Configuration validation
- Database operations

## 📊 Usage Examples

### Process a Small Batch
```bash
python llm_correction_processor.py --batch-size 5 --max-cost 10.0
```

### Process with Specific Model
```bash
python llm_correction_processor.py --model gpt-4 --batch-size 10
```

### Check Configuration
```bash
python -c "from llm_correction_config import config; print(config.validate_config())"
```

## 🔒 Safety Features

- **Rate Limiting**: Respects API rate limits and exits on 429 responses
- **Cost Control**: Configurable daily cost limits
- **Idempotency**: Safe to re-run without duplicating work
- **Database Backup**: Always backup before making changes
- **Error Handling**: Graceful fallbacks for API failures

## 🚨 Important Notes

- **API Costs**: LLM APIs cost money - monitor usage carefully
- **Rate Limits**: Processing will stop if rate limited (by design)
- **Legal Accuracy**: Only corrects OCR errors, never changes legal content
- **Database Backup**: Always backup before running corrections

## 🔍 Troubleshooting

### "No API keys detected"
Set the appropriate environment variable:
```bash
export OPENAI_API_KEY="your_key_here"
```

### "Rate limited - exiting processing loop"
This is expected behavior. Wait and run again later.

### "Database schema issues"
Run the test suite to verify schema:
```bash
python test_llm_correction.py
```

## 📈 Monitoring

The system tracks:
- Processing time per document
- API costs per request
- Quality scores and confidence levels
- Success/failure rates
- Rate limiting events

Check the database for detailed metrics:
```sql
SELECT * FROM ocr_corrections ORDER BY created_at DESC LIMIT 10;
```

## 🎯 Next Steps

1. Set up API keys
2. Run test suite to verify setup
3. Process a small batch to test
4. Monitor costs and quality
5. Scale up processing as needed

---

**Remember**: This system is designed to be safe and idempotent, but always backup your database before processing!
