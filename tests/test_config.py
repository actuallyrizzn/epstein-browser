"""
Test configuration and utilities.
"""
import os
import tempfile
import shutil
from pathlib import Path


class TestConfig:
    """Configuration for test environment."""
    
    # Test database settings
    TEST_DATABASE_PATH = ':memory:'
    TEST_DATA_DIR = 'tests/fixtures/test_data'
    
    # Test image settings
    TEST_IMAGE_COUNT = 4
    TEST_IMAGE_FORMATS = ['.TIF', '.tif']
    
    # Rate limiting test settings
    RATE_LIMIT_TEST_ITERATIONS = 5  # Reduced for faster tests
    
    # Performance test settings
    PERFORMANCE_TEST_REQUESTS = 20
    PERFORMANCE_TEST_TIMEOUT = 5.0
    
    # Test data
    SAMPLE_QUERIES = [
        'test',
        'DOJ',
        'Epstein',
        'document',
        'OCR',
        'search'
    ]
    
    SAMPLE_FILTERS = {
        'search_types': ['all', 'filename', 'ocr'],
        'ocr_filters': ['all', 'with-ocr', 'without-ocr'],
        'sort_options': ['relevance', 'filename', 'id']
    }
    
    @classmethod
    def setup_test_environment(cls):
        """Set up the test environment."""
        # Set environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['DATABASE_PATH'] = cls.TEST_DATABASE_PATH
        os.environ['DATA_DIR'] = cls.TEST_DATA_DIR
        
        # Create test data directory
        test_data_dir = Path(cls.TEST_DATA_DIR)
        test_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test image directory structure
        image_dirs = [
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES001',
            'Prod 01_20250822/VOL00001/IMAGES/IMAGES002',
            'Prod 01_20250822/VOL00001/NATIVES/NATIVE001',
        ]
        
        for img_dir in image_dirs:
            (test_data_dir / img_dir).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def cleanup_test_environment(cls):
        """Clean up the test environment."""
        # Remove test data directory if it exists
        test_data_dir = Path(cls.TEST_DATA_DIR)
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)
    
    @classmethod
    def create_test_images(cls):
        """Create test image files."""
        test_data_dir = Path(cls.TEST_DATA_DIR)
        
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
        
        return test_images
    
    @classmethod
    def get_test_database_data(cls):
        """Get test data for database population."""
        return [
            (1, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF', 
             'DOJ-OGR-00022168-001.TIF', 'VOL00001', 'IMAGES001', True, 
             'This is test OCR text for document 001'),
            (2, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF', 
             'DOJ-OGR-00022168-002.TIF', 'VOL00001', 'IMAGES001', True, 
             'This is test OCR text for document 002'),
            (3, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-001.TIF', 
             'DOJ-OGR-00022169-001.TIF', 'VOL00001', 'IMAGES002', False, None),
            (4, 'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-002.TIF', 
             'DOJ-OGR-00022169-002.TIF', 'VOL00001', 'IMAGES002', True, 
             'This is test OCR text for document 004'),
        ]
    
    @classmethod
    def get_test_blog_posts(cls):
        """Get test blog posts data."""
        return [
            {
                'id': 1,
                'title': 'Test Blog Post 1',
                'slug': 'test-blog-post-1',
                'date': '2025-09-06',
                'excerpt': 'This is a test blog post excerpt',
                'content': '## Test Content\n\nThis is test content for the blog post.',
                'author': 'Test Author',
                'tags': ['test', 'example']
            },
            {
                'id': 2,
                'title': 'Test Blog Post 2',
                'slug': 'test-blog-post-2',
                'date': '2025-09-07',
                'excerpt': 'This is another test blog post excerpt',
                'content': '## Another Test Content\n\nThis is more test content.',
                'author': 'Test Author',
                'tags': ['test', 'example', 'update']
            }
        ]
