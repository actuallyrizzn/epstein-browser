"""
Test database setup and management.
"""
import os
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch


class TestDatabaseManager:
    """Manages test database setup and teardown."""
    
    def __init__(self):
        self.test_db_path = None
        self.original_db_path = None
        self.original_data_dir = None
    
    def setup_test_database(self):
        """Set up a completely isolated test database."""
        # Create a temporary database file
        self.test_db_path = tempfile.mktemp(suffix='.db')
        
        # Store original values
        self.original_db_path = os.environ.get('DATABASE_PATH')
        self.original_data_dir = os.environ.get('DATA_DIR')
        
        # Set test environment
        os.environ['DATABASE_PATH'] = self.test_db_path
        os.environ['DATA_DIR'] = 'tests/fixtures/test_data'
        
        # Create test data directory
        test_data_dir = Path('tests/fixtures/test_data')
        test_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test image directory structure
        (test_data_dir / 'Prod 01_20250822' / 'VOL00001' / 'IMAGES' / 'IMAGES001').mkdir(parents=True, exist_ok=True)
        (test_data_dir / 'Prod 01_20250822' / 'VOL00001' / 'IMAGES' / 'IMAGES002').mkdir(parents=True, exist_ok=True)
        
        # Create test image files
        test_images = [
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF',
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF',
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-001.TIF',
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-002.TIF',
        ]
        
        for img_path in test_images:
            full_path = test_data_dir / img_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty files for testing
            full_path.touch()
        
        # Initialize the test database
        self._create_test_database()
        
        return self.test_db_path
    
    def _create_test_database(self):
        """Create the test database with proper schema."""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # Create images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                directory_path TEXT NOT NULL,
                volume TEXT,
                subdirectory TEXT,
                file_hash TEXT,
                has_ocr_text BOOLEAN DEFAULT FALSE,
                ocr_text_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create analytics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                path TEXT,
                referer TEXT,
                method TEXT,
                status_code INTEGER,
                response_time REAL,
                session_id TEXT
            )
        """)
        
        # Create search queries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query TEXT NOT NULL,
                search_type TEXT DEFAULT 'all',
                results_count INTEGER DEFAULT 0,
                ip_address TEXT,
                session_id TEXT,
                user_agent TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_path ON analytics(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_ip ON analytics(ip_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_timestamp ON search_queries(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_query ON search_queries(query)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_queries_type ON search_queries(search_type)")
        
        # Insert test data
        test_data = [
            (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 'DOJ-OGR-00022168-001.TIF', 1024, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash1', True, 'ocr1.txt'),
            (2, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF', 'DOJ-OGR-00022168-002.TIF', 2048, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001', 'VOL00001', 'IMAGES001', 'hash2', True, 'ocr2.txt'),
            (3, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-001.TIF', 'DOJ-OGR-00022169-001.TIF', 1536, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002', 'VOL00001', 'IMAGES002', 'hash3', False, None),
            (4, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-002.TIF', 'DOJ-OGR-00022169-002.TIF', 3072, 'TIF', 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002', 'VOL00001', 'IMAGES002', 'hash4', True, 'ocr4.txt'),
        ]
        
        for data in test_data:
            cursor.execute('''
                INSERT INTO images (id, file_path, file_name, file_size, file_type, directory_path, volume, subdirectory, file_hash, has_ocr_text, ocr_text_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
        
        conn.commit()
        conn.close()
    
    def cleanup_test_database(self):
        """Clean up test database and restore original environment."""
        # Remove test database file
        if self.test_db_path and os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
        
        # Restore original environment
        if self.original_db_path:
            os.environ['DATABASE_PATH'] = self.original_db_path
        else:
            os.environ.pop('DATABASE_PATH', None)
            
        if self.original_data_dir:
            os.environ['DATA_DIR'] = self.original_data_dir
        else:
            os.environ.pop('DATA_DIR', None)
    
    def __enter__(self):
        self.setup_test_database()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_test_database()


# Global test database manager
test_db_manager = TestDatabaseManager()
