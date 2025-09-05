# Epstein Documents Browser

A simple, Archive.org-style document browser for congressional records released by Congress.

## 🚀 Complete Setup Guide

### Step 1: Download the Documents
1. **Go to the Google Drive folder:** https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz
2. **Select all files** (Ctrl+A or Cmd+A)
3. **Right-click and choose "Download"** - this will create a ZIP file
4. **Extract the ZIP file** to a folder named `data` in your project directory
5. **Verify the structure:** You should have `data/Prod 01_20250822/VOL00001/IMAGES/` with 12 IMAGES subdirectories

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

### Step 4: Start the Web Application
```bash
# Start the Flask web server
python app.py

# You should see output like:
# 🚀 Starting Epstein Documents Browser...
# 📖 Browse: http://localhost:8080
# 📊 Stats: http://localhost:8080/api/stats
# Press Ctrl+C to stop the server
```

### Step 5: Browse the Documents
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
