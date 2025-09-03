# Epstein Documents Browser

A simple, Archive.org-style document browser for congressional records released by Congress.

## 🚀 Quick Start

1. **Index the documents:**
   ```bash
   python index_images.py
   ```

2. **Start the web application:**
   ```bash
   python app.py
   ```

3. **Open your browser:**
   - Homepage: http://localhost:8080
   - API Stats: http://localhost:8080/api/stats

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

### Keyboard Shortcuts
- **Arrow Keys** - Navigate between documents
- **Home/End** - Jump to first/last document
- **+/-** - Zoom in/out
- **Escape** - Exit fullscreen

### Search & Navigation
- **Filename search** - Find documents by name
- **Quick navigation** - Jump to first, middle, or last document
- **Random document** - Browse randomly
- **Statistics** - Real-time OCR progress tracking

## 🗂️ File Structure

```
epstein-release/
├── data/                          # Document images
│   └── Prod 01_20250822/
│       └── VOL00001/
│           └── IMAGES/
│               ├── IMAGES001/     # ~3,173 images
│               ├── IMAGES002/     # ~3,014 images
│               └── ...            # 12 total directories
├── templates/                     # HTML templates
│   ├── base.html                 # Base template
│   ├── index.html                # Homepage
│   └── viewer.html               # Document viewer
├── app.py                        # Flask web application
├── index_images.py               # Database indexer
├── images.db                     # SQLite database
└── README.md                     # This file
```

## 🔧 Technical Details

### Database Schema
- **images table** - All document metadata
- **directories table** - Directory structure
- **Indexes** - Fast queries by path, volume, type

### Web Application
- **Flask** - Python web framework
- **Bootstrap 5** - Responsive UI
- **Font Awesome** - Icons
- **SQLite** - Local database

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