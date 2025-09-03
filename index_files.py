#!/usr/bin/env python3
"""
File Indexer for Epstein Documents Web Database

This script scans the data directory and populates the web database
with all downloaded files for browsing.

Copyright (C) 2025 Epstein Documents OCR Project

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_database import WebDatabase

def main():
    """Main function to index all files"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Check if data directory exists
    data_dir = Path("data")
    if not data_dir.exists():
        logger.error("Data directory not found! Please ensure the data directory exists.")
        sys.exit(1)
    
    # Initialize web database
    logger.info("Initializing web database...")
    db = WebDatabase()
    
    # Index all files
    logger.info("Starting file indexing...")
    try:
        stats = db.index_directory(data_dir)
        
        logger.info("Indexing completed successfully!")
        logger.info(f"Files indexed: {stats['files_indexed']}")
        logger.info(f"Directories indexed: {stats['directories_indexed']}")
        logger.info(f"Errors: {stats['errors']}")
        
        # Show final statistics
        final_stats = db.get_statistics()
        logger.info(f"\nFinal Statistics:")
        logger.info(f"Total files: {final_stats['total_files']}")
        logger.info(f"Files with OCR: {final_stats['files_with_ocr']}")
        logger.info(f"Total directories: {final_stats['total_directories']}")
        logger.info(f"OCR percentage: {final_stats['ocr_percentage']:.1f}%")
        
        # Show volume breakdown
        logger.info(f"\nVolume Breakdown:")
        for vol in final_stats['volumes']:
            logger.info(f"  {vol['volume']}: {vol['file_count']} files")
        
        logger.info("\nFile indexing complete! The web application can now browse all files.")
        
    except Exception as e:
        logger.error(f"Error during indexing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
