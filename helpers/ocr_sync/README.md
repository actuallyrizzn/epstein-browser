# OCR Sync Tools

This directory contains tools for synchronizing OCR text data from a production site to the local data folder.

## Files

### `ocr_sync.py`
Main OCR synchronization script that polls the production site and downloads OCR texts to the local data folder.

**Features:**
- Dry run mode for safe testing
- Limited run mode for testing with small batches
- Batch processing with configurable batch sizes
- Progress tracking and detailed logging
- Automatic directory creation
- Cross-platform path handling

**Usage:**
```bash
# Dry run to see what would be downloaded
python helpers/ocr_sync/ocr_sync.py https://epstein-docs.example.com --dry-run

# Limited run for testing (process only 10 documents)
python helpers/ocr_sync/ocr_sync.py https://epstein-docs.example.com --limited-run 10

# Full sync
python helpers/ocr_sync/ocr_sync.py https://epstein-docs.example.com

# Custom data directory
python helpers/ocr_sync/ocr_sync.py https://epstein-docs.example.com --data-dir /path/to/data

# Verbose logging
python helpers/ocr_sync/ocr_sync.py https://epstein-docs.example.com --verbose
```

**Command Line Options:**
- `prod_url`: Production site base URL (required)
- `--data-dir`: Local data directory (default: data)
- `--dry-run`: Show what would be downloaded without making changes
- `--limited-run N`: Only process N documents (for testing)
- `--batch-size N`: Process N documents per batch (default: 50)
- `--verbose`: Enable verbose logging

### `test_ocr_sync.py`
Test script to verify that API endpoints work correctly before running the full sync.

**Usage:**
```bash
# Test against local development server
python helpers/ocr_sync/test_ocr_sync.py http://localhost:8080

# Test against production server
python helpers/ocr_sync/test_ocr_sync.py https://epstein-docs.example.com
```

## How It Works

1. **API Discovery**: The script uses the `/api/stats` endpoint to get overall statistics
2. **Document Listing**: Uses `/api/search` with OCR filter to get all documents with OCR text
3. **OCR Text Retrieval**: Attempts multiple methods to get OCR text:
   - First tries `/api/document/{id}` endpoint for direct OCR text
   - Falls back to `/api/ocr-text/{file_path}` for file-based access
4. **Local Storage**: Saves OCR text files with `.txt` extension in the same directory structure as the original images

## Safety Features

- **Dry Run Mode**: Shows exactly what would be downloaded without making any changes
- **Limited Run Mode**: Process only a small number of documents for testing
- **Existing File Detection**: Skips documents that already have OCR text locally
- **Error Handling**: Continues processing even if individual documents fail
- **Rate Limiting**: Includes delays between requests to be respectful to the server

## File Structure

The script maintains the same directory structure as the original data:
```
data/
├── Prod 01_20250822/
│   └── VOL00001/
│       └── IMAGES/
│           └── IMAGES001/
│               ├── DOJ-OGR-00000001.tif
│               ├── DOJ-OGR-00000001.txt  # OCR text file
│               ├── DOJ-OGR-00000002.tif
│               └── DOJ-OGR-00000002.txt  # OCR text file
```

## Logging

The script creates detailed logs in `ocr_sync.log` and also outputs to the console. Log levels include:
- INFO: General progress information
- DEBUG: Detailed debugging information (use --verbose)
- WARNING: Non-fatal issues
- ERROR: Fatal errors

## Error Handling

The script handles various error conditions gracefully:
- Network timeouts and connection errors
- Missing OCR text files
- File system permission issues
- Invalid document data
- Server rate limiting

## Testing Workflow

1. **Test API Endpoints**: Run `helpers/ocr_sync/test_ocr_sync.py` to verify the production site is accessible
2. **Dry Run**: Run `helpers/ocr_sync/ocr_sync.py` with `--dry-run` to see what would be downloaded
3. **Limited Test**: Run with `--limited-run 10` to test with a small batch
4. **Full Sync**: Run the full synchronization once testing is complete

## Requirements

- Python 3.7+
- requests library
- Access to the production site
- Write permissions to the local data directory

## License

This code is licensed under the GNU Affero General Public License v3.0 (AGPLv3).
