# Epstein Documents Browser

A simple, Archive.org-style document browser for congressional records released by Congress.

## 📖 Documentation

- **[Installation Guide](http://localhost:8080/help/installation)** - Complete setup instructions for running your own mirror
- **[API Documentation](http://localhost:8080/help/api)** - Full API reference with examples
- **[Usage Guide](http://localhost:8080/help/usage)** - How to use the document browser
- **[Features Overview](http://localhost:8080/help/features)** - Key features and capabilities
- **[Official Context](http://localhost:8080/help/context)** - Congressional sources and official document releases

## 🚀 Complete Setup Guide

### Step 1: Download the Documents
1. **Go to the Google Drive folder:** https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz
2. **Select all files** (Ctrl+A or Cmd+A)
3. **Right-click and choose "Download"** - this will create a ZIP file (~71 GB)
4. **Extract the ZIP file** to a folder named `data` in your project directory
5. **Verify the structure:** You should have `data/Prod 01_20250822/VOL00001/IMAGES/` with 12 IMAGES subdirectories

**⚠️ Directory Structure:** This is the official structure as released by Congress. Do not try to reorganize it - the application is designed to work with their unconventional organization.

**⚠️ Storage Requirement:** The complete document collection is approximately **71 GB**. Ensure you have sufficient free space before downloading.

### Step 2: Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Index the Documents
```bash
# Run the image indexer (this will scan all 33,572 images)
python index_images.py

# You should see output like:
# 🔍 Epstein Documents Image Indexer
# ==================================================
# Indexed 33,572 images...
# ✅ Indexing complete!
```

### Step 4: Process PDF Documents (Optional)
```bash
# If you have PDF documents to process, use the PDF explosion tool
python helpers/explode_pdfs.py data/pdf-documents/ data/images/processed/

# Run OCR processing on the new images
python ocr_processor.py --input-dir data/images/processed/

# Index the processed images into the database
python index_images.py --input-dir data/images/processed/
```

### Step 5: Start the Web Application
```bash
# Start the Flask web server
python app.py

# You should see output like:
# 🚀 Starting Epstein Documents Browser...
# 📖 Browse: http://localhost:8080
# 📊 Stats: http://localhost:8080/api/stats
# Press Ctrl+C to stop the server
```

### Step 6: Browse the Documents
- **Homepage:** http://localhost:8080
- **API Stats:** http://localhost:8080/api/stats
- **Document Viewer:** http://localhost:8080/view/1

## 📊 What We Have

- **33,572 images** total
- **30 images with OCR** (0.1% processed)
- **1 volume** (VOL00001)
- **12 IMAGES subdirectories** (IMAGES001 through IMAGES012)

## 🎯 Features

### Archive.org-Style Document Viewer
- **Clean interface** - Dark theme with document focus
- **Simple navigation** - Previous/Next buttons and keyboard shortcuts
- **Progress tracking** - Visual progress bar showing position in document set
- **Zoom controls** - Click to zoom, or use +/- buttons
- **Fullscreen mode** - Press F11 or click fullscreen button

### PDF Processing Pipeline
- **PDF Explosion** - Convert multi-page PDFs to individual images
- **Sequential Numbering** - Maintain consistent DOJ-OGR naming format
- **Quality Assessment** - Automatic detection of poor scan quality
- **Batch Processing** - Handle large document collections efficiently
- **Error Detection** - Identify and flag pages needing manual review

### Advanced OCR Capabilities
- **Multi-Engine Support** - EasyOCR + Tesseract for optimal results
- **Quality Scoring** - Automatic assessment of OCR accuracy
- **Rescan Logic** - Automatic reprocessing of poor quality pages
- **Context-Aware Search** - Full-text search with text excerpts
- **Export Options** - Multiple output formats for processed text

### Keyboard Shortcuts
- **Arrow Keys** - Navigate between documents
- **Home/End** - Jump to first/last document
- **+/-** - Zoom in/out
- **Escape** - Exit fullscreen

### Search & Navigation
- **Filename search** - Find documents by name
- **Content search** - Full-text search across OCR results
- **Context excerpts** - See search matches with surrounding text
- **Quick navigation** - Jump to first, middle, or last document
- **Random document** - Browse randomly
- **Statistics** - Real-time OCR progress tracking

## 📄 PDF Processing Guide

### Processing New PDF Documents

The system now includes comprehensive PDF processing capabilities for handling new document dumps:

#### 1. PDF Explosion
```bash
# Convert PDFs to individual images with proper naming
python helpers/explode_pdfs.py data/new-pdf-dump/ data/images/processed/

# Options:
# --dpi 600          # Higher DPI for better quality
# --start-id 50000   # Custom starting ID
```

#### 2. OCR Processing
```bash
# Process images with OCR
python ocr_processor.py --input-dir data/images/processed/

# Options:
# --quality-check    # Enable quality assessment
# --rescan-poor      # Automatically rescan poor quality pages
```

#### 3. Database Integration
```bash
# Index processed images into searchable database
python index_images.py --input-dir data/images/processed/

# Options:
# --source "9-8-25-release"  # Tag the source
# --quality-threshold 30     # Set quality threshold
```

### PDF Processing Features

- **Sequential Numbering**: Maintains DOJ-OGR-00000001.jpg format
- **Quality Assessment**: Automatic detection of poor scan quality
- **Batch Processing**: Handle large document collections efficiently
- **Error Detection**: Identify pages needing manual review
- **Mapping Files**: Track PDF-to-image conversion for reference

## 🗂️ File Structure

```
epstein-release/
├── data/                          # Document images
│   ├── Prod 01_20250822/         # Original congressional documents
│   │   └── VOL00001/
│   │       └── IMAGES/
│   │           ├── IMAGES001/     # ~3,173 images
│   │           ├── IMAGES002/     # ~3,014 images
│   │           └── ...            # 12 total directories
│   ├── 9-8-25-release/           # New Epstein Estate documents
│   │   ├── Request No. 1.pdf     # 238 pages
│   │   ├── Request No. 2.pdf     # 10 pages
│   │   ├── Request No. 4.pdf     # 9 pages
│   │   └── Request No. 8.pdf     # 99 pages
│   └── images/                    # Processed images
│       └── 9-8-25-release/       # Converted PDF pages
│           ├── DOJ-OGR-00033296.jpg
│           ├── DOJ-OGR-00033297.jpg
│           └── ...                # 356 total images
├── helpers/                       # Utility scripts
│   ├── explode_pdfs.py           # PDF to images converter
│   ├── venice_integration.py     # AI/LLM integration
│   └── venice_sdk/               # Venice AI SDK
├── templates/                     # HTML templates
│   ├── base.html                 # Base template
│   ├── index.html                # Homepage
│   └── viewer.html               # Document viewer
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
├── docs/                         # Documentation
│   └── ERROR_DETECTION_RESCAN_PLAN.md
├── app.py                        # Flask web application
├── index_images.py               # Database indexer
├── ocr_processor.py              # OCR processing
├── images.db                     # SQLite database
└── README.md                     # This file
```

## 🔧 Technical Details

### Database Schema
- **images table** - All document metadata (33,572 records)
- **directories table** - Directory structure (21 directories)
- **Indexes** - Fast queries by path, volume, type

### Web Application
- **Flask** - Python web framework
- **Bootstrap 5** - Responsive UI
- **Font Awesome** - Icons
- **SQLite** - Local database
- **Pillow (PIL)** - TIF to JPEG conversion

### Image Processing
- **TIF files** - Automatically converted to JPEG for browser compatibility
- **JPG files** - Served directly
- **Quality** - 85% JPEG quality for optimal file size vs. readability

## 🛠️ Troubleshooting

### Common Issues

**Images not displaying:**
- Make sure you've run `python index_images.py` first
- Check that the `data` folder exists and contains the documents
- Verify the database file `images.db` was created

**TIF files showing as broken:**
- This is now fixed! TIF files are automatically converted to JPEG
- If you still see issues, restart the Flask app: `python app.py`

**Port 8080 already in use:**
- Change the port in `app.py` line 218: `port=8080` to `port=8081`
- Or stop the other service using port 8080

**Virtual environment issues:**
- Make sure you've activated the venv: `venv\Scripts\activate` (Windows)
- Install dependencies: `pip install -r requirements.txt`

**Database errors:**
- Delete `images.db` and run `python index_images.py` again
- Make sure you have write permissions in the project directory

## 📝 License

- **Code**: AGPLv3
- **Content**: CC-BY-SA-4.0
- **Original Documents**: Public Domain (Congressional Records)

## 🎯 Next Steps

1. **OCR Processing** - Run TrOCR on all 33,572 images
2. **Text Search** - Full-text search across OCR results
3. **VPS Deployment** - 24/7 processing and hosting
4. **Analysis Tools** - Redaction analysis and document categorization

## 🔗 Data Source

Original documents: https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz

---

**Note**: This is a simple, functional document browser. No complex features, no over-engineering - just clean, fast document browsing like Archive.org.
## Environment Configuration

This application uses environment variables for configuration. Copy `.env.example` to `.env` and customize the values for your environment.

### Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your production values:
   ```bash
   nano .env
   ```

3. **Important**: Never commit `.env` to git - it contains sensitive information!

### Environment Variables

- `FLASK_ENV`: Set to `production` for production deployment
- `SECRET_KEY`: Strong secret key for Flask sessions (generate with `openssl rand -hex 32`)
- `DATABASE_PATH`: Path to the SQLite database file
- `DATA_DIR`: Directory containing the document images
- `HOST`: Server host (use `127.0.0.1` for nginx proxy)
- `PORT`: Server port
- `DEBUG`: Enable/disable debug mode
- `TESTING`: Enable/disable testing mode

### Security

- The `.env` file is automatically ignored by git
- Use strong, unique secret keys in production
- Never share your `.env` file or commit it to version control
