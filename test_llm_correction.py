#!/usr/bin/env python3
"""
Test script for LLM Correction system

Tests the basic functionality without making actual API calls.
"""

import os
import sys
import sqlite3

# Add helpers to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))

from helpers.ocr_quality_assessment import OCRQualityAssessment
from llm_correction_config import config


def test_database_schema():
    """Test database schema creation"""
    print("Testing database schema...")
    
    conn = sqlite3.connect(config.DATABASE_PATH)
    ocr_assessor = OCRQualityAssessment(config.DATABASE_PATH)
    
    try:
        ocr_assessor.ensure_database_schema(conn)
        print("✓ Database schema updated successfully")
        
        # Check if tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['ocr_corrections', 'ocr_reprocessing_queue']
        for table in required_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' missing")
        
        # Check if images table has new columns
        cursor = conn.execute("PRAGMA table_info(images)")
        columns = [row[1] for row in cursor.fetchall()]
        
        required_columns = ['has_corrected_text', 'ocr_quality_score', 'reprocess_priority']
        for col in required_columns:
            if col in columns:
                print(f"✓ Column 'images.{col}' exists")
            else:
                print(f"✗ Column 'images.{col}' missing")
        
    finally:
        conn.close()


def test_token_calculation():
    """Test token calculation"""
    print("\nTesting token calculation...")
    
    ocr_assessor = OCRQualityAssessment(config.DATABASE_PATH)
    
    test_text = "This is a test OCR text with some errors that need correction."
    prompt = "Correct this OCR text:"
    
    try:
        tokens = ocr_assessor.calculate_token_estimate(prompt, test_text)
        print(f"✓ Token calculation works: {tokens} tokens")
    except Exception as e:
        print(f"✗ Token calculation failed: {e}")


def test_validation():
    """Test validation functions"""
    print("\nTesting validation functions...")
    
    ocr_assessor = OCRQualityAssessment(config.DATABASE_PATH)
    
    # Test change validation
    original = "This is original text"
    corrected = "This is corrected text"
    identical = "This is original text"
    
    if ocr_assessor.validate_correction_changes(original, corrected):
        print("✓ Change validation works (different text)")
    else:
        print("✗ Change validation failed (different text)")
    
    if not ocr_assessor.validate_correction_changes(original, identical):
        print("✓ Change validation works (identical text)")
    else:
        print("✗ Change validation failed (identical text)")


def test_configuration():
    """Test configuration validation"""
    print("\nTesting configuration...")
    
    validation = config.validate_config()
    
    if validation["valid"]:
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration has issues:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
    
    if validation["warnings"]:
        print("⚠ Configuration warnings:")
        for warning in validation["warnings"]:
            print(f"  - {warning}")


def test_database_operations():
    """Test database operations"""
    print("\nTesting database operations...")
    
    ocr_assessor = OCRQualityAssessment(config.DATABASE_PATH)
    
    # Test reprocessing queue operations
    try:
        # Add test item to queue
        ocr_assessor.flag_for_reprocessing(999, "Test reprocessing", 1)
        print("✓ Flag for reprocessing works")
        
        # Get queue items
        queue_items = ocr_assessor.get_reprocessing_queue()
        print(f"✓ Get reprocessing queue works ({len(queue_items)} items)")
        
    except Exception as e:
        print(f"✗ Database operations failed: {e}")


def main():
    """Run all tests"""
    print("LLM Correction System Test Suite")
    print("=" * 40)
    
    test_database_schema()
    test_token_calculation()
    test_validation()
    test_configuration()
    test_database_operations()
    
    print("\n" + "=" * 40)
    print("Test suite completed!")
    
    # Check if API keys are available for full testing
    if config.VENICE_API_KEY:
        print("\n✓ Venice API key detected - ready for full testing")
    else:
        print("\n⚠ No Venice API key detected - set VENICE_API_KEY for full testing")


if __name__ == "__main__":
    main()
