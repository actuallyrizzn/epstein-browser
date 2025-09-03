# Epstein Documents Analysis Project

A Python-based analysis tool for the Epstein documents released by Congress in 2025.

## 📁 Project Structure

```
epstein-release/
├── data/                    # Complete document repository (33,657 files)
│   ├── extraction_metadata.json
│   └── [29,773 JPG images, 3,799 TIF images, 56 WAV audio, 27 MP4 videos]
├── src/                     # Source code for analysis tools
├── requirements.txt         # Python dependencies
├── venv/                   # Virtual environment
└── README.md              # This file
```

## 🎯 Repository Status

✅ **Complete Repository Mirrored**
- **33,657 files successfully extracted**
- **File types:** JPG (29,773), TIF (3,799), WAV (56), MP4 (27), DAT (1), OPT (1)
- **Source:** Browser download from Google Drive folder
- **Extraction date:** 2025-09-03

## 🚀 Setup

1. **Activate virtual environment:**
   ```bash
   # Windows
   .\venv\Scripts\Activate.ps1
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 📊 Data Overview

The repository contains the complete set of Epstein documents released by Congress, including:
- **Scanned documents** (JPG/TIF images with DOJ-OGR numbering)
- **Audio recordings** (WAV files)
- **Video files** (MP4 files)
- **Database files** (DAT/OPT binary files)

**Data Source:** [Google Drive Folder - Epstein Documents](https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz)

## 🔧 Next Steps

Ready for development of:
- Document analysis tools for redacted content
- Web interface for browsing and searching
- Database setup for metadata and analysis results
- OCR and text extraction capabilities

## 📝 Notes

- All files are organized in the `data/` directory
- Metadata is tracked in `data/extraction_metadata.json`
- Virtual environment is pre-configured with all dependencies

## 📄 Licensing

### Code License
This project's source code is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE) for full details.

### Content License
All original content created for this project (documentation, analysis, derived works) is licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA-4.0)**. See [CONTENT_LICENSE](CONTENT_LICENSE) for full details.

### Source Documents
The original Epstein documents processed by this system are part of the Congressional Record and are in the public domain. This project does not claim copyright over the original documents, only over the tools and analysis created to process them.

### Third-Party Dependencies
This project uses various open-source libraries and frameworks, each with their own licenses. See `requirements.txt` and individual package documentation for details.