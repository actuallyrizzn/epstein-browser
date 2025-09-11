#!/usr/bin/env python3
"""
Database Migration Script: 0a03ee0 to 35f21d4

This script migrates the database schema from commit 0a03ee021199eb4b6be46593264cc773de37e7a3
to commit 35f21d400776b8e227d1cb677d7a262c652b441e.

Changes:
1. Add ocr_content table for full-text search
2. Add ocr_quality_score column to images table
3. Add ocr_rescan_attempts column to images table
4. Add indexes for new columns

The script is idempotent and safe to run multiple times.
"""

import sqlite3
import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "images.db"
BACKUP_PATH = f"images_backup_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup of the current database"""
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file {DB_PATH} not found!")
        return False
    
    logger.info(f"Creating backup: {BACKUP_PATH}")
    try:
        # Read the entire database file
        with open(DB_PATH, 'rb') as src:
            with open(BACKUP_PATH, 'wb') as dst:
                dst.write(src.read())
        logger.info(f"Backup created successfully: {BACKUP_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_database():
    """Perform the database migration"""
    logger.info("Starting database migration from 0a03ee0 to 35f21d4")
    
    # Create backup first
    if not backup_database():
        logger.error("Failed to create backup. Aborting migration.")
        return False
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if images table exists (basic sanity check)
            if not check_table_exists(cursor, 'images'):
                logger.error("Images table not found. This doesn't look like a valid database.")
                return False
            
            logger.info("✓ Images table found")
            
            # 1. Create OCR content table if it doesn't exist
            if not check_table_exists(cursor, 'ocr_content'):
                logger.info("Creating ocr_content table...")
                cursor.execute("""
                    CREATE TABLE ocr_content (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_hash TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
                    )
                """)
                logger.info("✓ ocr_content table created")
            else:
                logger.info("✓ ocr_content table already exists")
            
            # 2. Add ocr_quality_score column to images table
            if not check_column_exists(cursor, 'images', 'ocr_quality_score'):
                logger.info("Adding ocr_quality_score column to images table...")
                cursor.execute("""
                    ALTER TABLE images ADD COLUMN ocr_quality_score INTEGER DEFAULT NULL
                """)
                logger.info("✓ ocr_quality_score column added")
            else:
                logger.info("✓ ocr_quality_score column already exists")
            
            # 3. Add ocr_rescan_attempts column to images table
            if not check_column_exists(cursor, 'images', 'ocr_rescan_attempts'):
                logger.info("Adding ocr_rescan_attempts column to images table...")
                cursor.execute("""
                    ALTER TABLE images ADD COLUMN ocr_rescan_attempts INTEGER DEFAULT 0
                """)
                logger.info("✓ ocr_rescan_attempts column added")
            else:
                logger.info("✓ ocr_rescan_attempts column already exists")
            
            # 4. Create indexes for new columns
            logger.info("Creating indexes for new columns...")
            
            # Index for ocr_quality_score
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_ocr_quality_score 
                ON images(ocr_quality_score)
            """)
            logger.info("✓ Index for ocr_quality_score created")
            
            # Index for ocr_rescan_attempts
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_ocr_rescan_attempts 
                ON images(ocr_rescan_attempts)
            """)
            logger.info("✓ Index for ocr_rescan_attempts created")
            
            # Index for ocr_content table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ocr_content_image_id 
                ON ocr_content(image_id)
            """)
            logger.info("✓ Index for ocr_content.image_id created")
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ocr_content_search 
                ON ocr_content(content)
            """)
            logger.info("✓ Index for ocr_content.content created")
            
            # Commit all changes
            conn.commit()
            logger.info("✓ All changes committed to database")
            
            # Verify the migration
            logger.info("Verifying migration...")
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            expected_tables = ['analytics', 'directories', 'images', 'ocr_content', 'search_queries']
            
            for table in expected_tables:
                if table in tables:
                    logger.info(f"✓ Table '{table}' exists")
                else:
                    logger.warning(f"⚠ Table '{table}' missing")
            
            # Check columns in images table
            cursor.execute("PRAGMA table_info(images)")
            columns = [row[1] for row in cursor.fetchall()]
            expected_columns = ['ocr_quality_score', 'ocr_rescan_attempts']
            
            for column in expected_columns:
                if column in columns:
                    logger.info(f"✓ Column 'images.{column}' exists")
                else:
                    logger.warning(f"⚠ Column 'images.{column}' missing")
            
            logger.info("🎉 Database migration completed successfully!")
            logger.info(f"Backup saved as: {BACKUP_PATH}")
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        logger.error(f"Database backup available at: {BACKUP_PATH}")
        return False

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Database Migration: 0a03ee0 → 35f21d4")
    logger.info("=" * 60)
    
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file {DB_PATH} not found!")
        logger.error("Please run this script from the project root directory.")
        sys.exit(1)
    
    # Show current database info
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Current database has {len(tables)} tables: {', '.join(tables)}")
            
            # Check if migration is needed
            needs_migration = (
                'ocr_content' not in tables or
                not check_column_exists(cursor, 'images', 'ocr_quality_score') or
                not check_column_exists(cursor, 'images', 'ocr_rescan_attempts')
            )
            
            if not needs_migration:
                logger.info("✓ Database appears to already be migrated!")
                logger.info("No changes needed.")
                return
            
    except Exception as e:
        logger.error(f"Failed to analyze current database: {e}")
        sys.exit(1)
    
    # Confirm migration
    print("\n" + "=" * 60)
    print("MIGRATION PLAN:")
    print("=" * 60)
    print("1. Create backup of current database")
    print("2. Add ocr_content table for full-text search")
    print("3. Add ocr_quality_score column to images table")
    print("4. Add ocr_rescan_attempts column to images table")
    print("5. Create indexes for new columns")
    print("=" * 60)
    
    response = input("\nProceed with migration? (y/N): ").strip().lower()
    if response != 'y':
        logger.info("Migration cancelled by user.")
        return
    
    # Run migration
    success = migrate_database()
    
    if success:
        logger.info("\n🎉 Migration completed successfully!")
        logger.info(f"Backup saved as: {BACKUP_PATH}")
        logger.info("You can now safely use the updated database.")
    else:
        logger.error("\n❌ Migration failed!")
        logger.error(f"Check the backup at: {BACKUP_PATH}")
        logger.error("You may need to restore from backup and investigate the issue.")
        sys.exit(1)

if __name__ == "__main__":
    main()
