#!/usr/bin/env python3
"""
Performance Testing Script for Optimized OCR System

Tests and benchmarks the optimized OCR system with various configurations
to find the best performance settings.

Copyright (C) 2025 Epstein Documents Analysis Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any
import multiprocessing as mp

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from optimized_ocr_engine import OptimizedTrOCREngine
from optimized_batch_processor import OptimizedBatchProcessor


def find_test_images(data_dir: str = "data", max_images: int = 20) -> List[Path]:
    """Find test images for benchmarking"""
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"Data directory {data_dir} not found!")
        return []
    
    # Find image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
    test_images = []
    
    for ext in image_extensions:
        pattern = f"**/*{ext}"
        files = list(data_path.glob(pattern))
        test_images.extend(files)
        
        if len(test_images) >= max_images:
            break
    
    return test_images[:max_images]


def benchmark_configuration(config: Dict[str, Any], test_images: List[Path]) -> Dict[str, Any]:
    """Benchmark a specific configuration"""
    print(f"\n{'='*60}")
    print(f"Testing configuration: {config['name']}")
    print(f"{'='*60}")
    
    try:
        # Create engine
        engine = OptimizedTrOCREngine(
            max_workers=config['max_workers'],
            batch_size=config['batch_size'],
            enable_preprocessing=config['enable_preprocessing']
        )
        
        # Convert to string paths
        image_paths = [str(img) for img in test_images]
        
        # Create temporary output directory
        output_dir = Path("test_output") / config['name'].replace(' ', '_').lower()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Benchmark processing
        start_time = time.time()
        
        stats = engine.process_images(
            image_paths=image_paths,
            output_dir=str(output_dir),
            use_multiprocessing=config.get('use_multiprocessing', False)
        )
        
        total_time = time.time() - start_time
        
        # Calculate additional metrics
        images_per_minute = len(test_images) / (total_time / 60)
        estimated_full_time = (67144 / images_per_minute) / 60  # hours for full dataset
        
        results = {
            'config': config,
            'test_images': len(test_images),
            'total_time': total_time,
            'avg_processing_time': stats['avg_processing_time'],
            'images_per_minute': images_per_minute,
            'estimated_full_time_hours': estimated_full_time,
            'success_rate': stats['success_rate'],
            'successful': stats['successful'],
            'failed': stats['failed']
        }
        
        print(f"Results:")
        print(f"  Test images: {len(test_images)}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Avg processing time: {stats['avg_processing_time']:.2f}s")
        print(f"  Images per minute: {images_per_minute:.1f}")
        print(f"  Estimated full dataset time: {estimated_full_time:.1f} hours")
        print(f"  Success rate: {stats['success_rate']:.1f}%")
        
        # Cleanup
        engine.cleanup()
        
        return results
        
    except Exception as e:
        print(f"Error testing configuration {config['name']}: {e}")
        return {
            'config': config,
            'error': str(e)
        }


def run_performance_tests():
    """Run comprehensive performance tests"""
    print("🚀 Starting Performance Optimization Tests")
    print("=" * 60)
    
    # Find test images
    test_images = find_test_images(max_images=20)
    
    if not test_images:
        print("❌ No test images found! Please ensure the data directory exists.")
        return
    
    print(f"📁 Found {len(test_images)} test images")
    
    # Define test configurations
    cpu_count = mp.cpu_count()
    print(f"💻 CPU cores available: {cpu_count}")
    
    configurations = [
        {
            'name': 'Baseline (Original)',
            'max_workers': 1,
            'batch_size': 1,
            'enable_preprocessing': False,
            'use_multiprocessing': False
        },
        {
            'name': 'Threading 2 Workers',
            'max_workers': 2,
            'batch_size': 2,
            'enable_preprocessing': True,
            'use_multiprocessing': False
        },
        {
            'name': 'Threading 4 Workers',
            'max_workers': 4,
            'batch_size': 4,
            'enable_preprocessing': True,
            'use_multiprocessing': False
        },
        {
            'name': 'Threading 8 Workers',
            'max_workers': 8,
            'batch_size': 8,
            'enable_preprocessing': True,
            'use_multiprocessing': False
        },
        {
            'name': 'Threading Max Workers',
            'max_workers': cpu_count,
            'batch_size': cpu_count,
            'enable_preprocessing': True,
            'use_multiprocessing': False
        },
        {
            'name': 'Multiprocessing 2 Workers',
            'max_workers': 2,
            'batch_size': 2,
            'enable_preprocessing': True,
            'use_multiprocessing': True
        },
        {
            'name': 'Multiprocessing 4 Workers',
            'max_workers': 4,
            'batch_size': 4,
            'enable_preprocessing': True,
            'use_multiprocessing': True
        },
        {
            'name': 'No Preprocessing',
            'max_workers': cpu_count,
            'batch_size': cpu_count,
            'enable_preprocessing': False,
            'use_multiprocessing': False
        }
    ]
    
    # Run benchmarks
    results = []
    for config in configurations:
        result = benchmark_configuration(config, test_images)
        results.append(result)
        
        # Small delay between tests
        time.sleep(2)
    
    # Analyze results
    print(f"\n{'='*60}")
    print("📊 PERFORMANCE ANALYSIS")
    print(f"{'='*60}")
    
    # Sort by images per minute
    valid_results = [r for r in results if 'error' not in r]
    valid_results.sort(key=lambda x: x['images_per_minute'], reverse=True)
    
    print(f"\n🏆 TOP PERFORMING CONFIGURATIONS:")
    print("-" * 60)
    
    for i, result in enumerate(valid_results[:5], 1):
        config = result['config']
        print(f"{i}. {config['name']}")
        print(f"   Images/min: {result['images_per_minute']:.1f}")
        print(f"   Est. full time: {result['estimated_full_time_hours']:.1f} hours")
        print(f"   Success rate: {result['success_rate']:.1f}%")
        print(f"   Workers: {config['max_workers']}, Batch: {config['batch_size']}")
        print()
    
    # Find best configuration
    if valid_results:
        best = valid_results[0]
        print(f"🎯 RECOMMENDED CONFIGURATION:")
        print(f"   {best['config']['name']}")
        print(f"   Max workers: {best['config']['max_workers']}")
        print(f"   Batch size: {best['config']['batch_size']}")
        print(f"   Preprocessing: {best['config']['enable_preprocessing']}")
        print(f"   Multiprocessing: {best['config']['use_multiprocessing']}")
        print(f"   Expected performance: {best['images_per_minute']:.1f} images/min")
        print(f"   Estimated full dataset time: {best['estimated_full_time_hours']:.1f} hours")
    
    # Save results
    results_file = Path("performance_test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return results


def test_small_batch():
    """Test with a small batch to verify functionality"""
    print("\n🧪 Testing Small Batch Processing...")
    
    # Find a few test images
    test_images = find_test_images(max_images=5)
    
    if not test_images:
        print("❌ No test images found!")
        return False
    
    try:
        # Create optimized processor
        processor = OptimizedBatchProcessor(
            max_workers=4,
            batch_size=4,
            enable_preprocessing=True,
            use_multiprocessing=False
        )
        
        # Process small batch
        results = processor.run_processing(max_files=5, resume=False)
        
        if 'error' in results:
            print(f"❌ Error: {results['error']}")
            return False
        
        print(f"✅ Small batch test successful!")
        print(f"   Processed: {results['successful']} files")
        print(f"   Failed: {results['failed']} files")
        print(f"   Avg time: {results['avg_processing_time']:.2f}s")
        print(f"   Images/min: {results['images_per_minute']:.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Small batch test failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OCR Performance Testing")
    parser.add_argument("--small-test", action="store_true", help="Run small batch test only")
    parser.add_argument("--full-test", action="store_true", help="Run full performance test")
    
    args = parser.parse_args()
    
    if args.small_test:
        test_small_batch()
    elif args.full_test:
        run_performance_tests()
    else:
        # Default: run both
        print("Running both small batch test and full performance test...")
        
        # Small test first
        if test_small_batch():
            print("\n" + "="*60)
            # Full test
            run_performance_tests()
        else:
            print("❌ Small batch test failed, skipping full test")
