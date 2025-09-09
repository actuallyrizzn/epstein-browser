#!/usr/bin/env python3
"""
Explode PDF files into sequentially numbered images using the correct DOJ-OGR naming format.
Starts from the next available ID after the current max ID in the database.
"""

import fitz  # PyMuPDF
import sqlite3
from pathlib import Path
import argparse
import sys
import re

def get_next_available_id(db_path="images.db"):
    """Get the next available ID from the database by parsing DOJ-OGR filenames"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        result = cursor.execute('SELECT file_path FROM images WHERE file_path LIKE "%DOJ-OGR-%.%" ORDER BY file_path DESC LIMIT 1;').fetchone()
        conn.close()
        
        if result:
            # Extract the number from the last DOJ-OGR file
            match = re.search(r'DOJ-OGR-(\d+)', result[0])
            if match:
                return int(match.group(1)) + 1
        
        return 1
    except Exception as e:
        print(f"Error getting next ID: {e}")
        return 1

def explode_pdf_to_images(pdf_path, output_dir, start_id, dpi=300):
    """Convert PDF to sequentially numbered images using DOJ-OGR format"""
    doc = fitz.open(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_name = Path(pdf_path).stem
    current_id = start_id
    images_created = []
    
    print(f"Converting {pdf_name} ({doc.page_count} pages) starting from ID {current_id:08d}")
    
    for page_num in range(doc.page_count):
        page = doc[page_num]
        
        # High-quality conversion
        mat = fitz.Matrix(dpi/72, dpi/72)  # 72 is default DPI
        pix = page.get_pixmap(matrix=mat)
        
        # Create filename using DOJ-OGR format: DOJ-OGR-00000001.jpg
        img_filename = f"DOJ-OGR-{current_id:08d}.jpg"
        img_path = output_dir / img_filename
        
        # Save as JPEG for consistency with existing files
        pix.save(str(img_path), output="jpeg", jpg_quality=85)
        
        images_created.append({
            'id': current_id,
            'filename': img_filename,
            'path': str(img_path),
            'pdf_source': pdf_name,
            'page_number': page_num + 1,
            'size': img_path.stat().st_size
        })
        
        print(f"  Page {page_num + 1:3d} -> {img_filename} ({img_path.stat().st_size / 1024:.1f} KB)")
        current_id += 1
    
    doc.close()
    return images_created, current_id

def main():
    parser = argparse.ArgumentParser(description="Explode PDFs into DOJ-OGR format images")
    parser.add_argument("pdf_dir", help="Directory containing PDF files")
    parser.add_argument("output_dir", help="Output directory for images")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for conversion (default: 300)")
    parser.add_argument("--start-id", type=int, help="Starting ID (auto-detected if not provided)")
    
    args = parser.parse_args()
    
    pdf_dir = Path(args.pdf_dir)
    output_dir = Path(args.output_dir)
    
    if not pdf_dir.exists():
        print(f"Error: PDF directory {pdf_dir} does not exist")
        sys.exit(1)
    
    # Get starting ID
    if args.start_id:
        start_id = args.start_id
        print(f"Using provided start ID: {start_id:08d}")
    else:
        start_id = get_next_available_id()
        print(f"Auto-detected next available ID: {start_id:08d}")
    
    # Find all PDF files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        sys.exit(1)
    
    print(f"Found {len(pdf_files)} PDF files:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name} ({pdf_file.stat().st_size / (1024*1024):.1f} MB)")
    print()
    
    # Process each PDF
    all_images = []
    current_id = start_id
    
    for pdf_file in sorted(pdf_files):
        try:
            images, next_id = explode_pdf_to_images(pdf_file, output_dir, current_id, args.dpi)
            all_images.extend(images)
            current_id = next_id
            print()
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")
            continue
    
    # Summary
    print("=== CONVERSION SUMMARY ===")
    print(f"Total images created: {len(all_images)}")
    print(f"ID range: {start_id:08d} to {current_id - 1:08d}")
    print(f"Output directory: {output_dir}")
    
    # Save mapping file for reference
    mapping_file = output_dir / "pdf_to_images_mapping.txt"
    with open(mapping_file, 'w') as f:
        f.write("PDF to Images Mapping (DOJ-OGR Format)\n")
        f.write("=====================================\n\n")
        f.write(f"Conversion date: {Path().cwd()}\n")
        f.write(f"Total images: {len(all_images)}\n")
        f.write(f"ID range: {start_id:08d} to {current_id - 1:08d}\n\n")
        
        for img in all_images:
            f.write(f"DOJ-OGR-{img['id']:08d}: {img['filename']} (from {img['pdf_source']} page {img['page_number']})\n")
    
    print(f"Mapping saved to: {mapping_file}")
    
    # Show next steps
    print("\n=== NEXT STEPS ===")
    print("1. Run OCR processing:")
    print(f"   python ocr_processor.py --input-dir {output_dir}")
    print()
    print("2. Index into database:")
    print(f"   python index_images.py --input-dir {output_dir}")
    print()
    print("3. Test Error Detection & Rescan Pass:")
    print(f"   python scripts/bad_ocr_detector.py --input-dir {output_dir}")

if __name__ == "__main__":
    main()
