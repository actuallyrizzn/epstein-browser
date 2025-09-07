#!/usr/bin/env python3
"""
Test runner script for the Epstein Documents Browser test suite.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True

def main():
    parser = argparse.ArgumentParser(description='Run Epstein Documents Browser tests')
    parser.add_argument('--type', choices=['unit', 'integration', 'e2e', 'rate_limit', 'all'], 
                       default='all', help='Type of tests to run')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--parallel', '-n', type=int, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    # Set up environment
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DATABASE_PATH'] = ':memory:'
    os.environ['DATA_DIR'] = 'tests/fixtures/test_data'
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add verbosity
    if args.verbose:
        cmd.append('-v')
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(['-n', str(args.parallel)])
    
    # Add coverage
    if args.coverage:
        cmd.extend(['--cov=app', '--cov-report=html', '--cov-report=term-missing'])
    
    # Select test type
    if args.type == 'unit':
        cmd.append('tests/unit/')
    elif args.type == 'integration':
        cmd.append('tests/integration/')
    elif args.type == 'e2e':
        cmd.append('tests/e2e/')
    elif args.type == 'rate_limit':
        cmd.append('-m', 'rate_limit')
    elif args.type == 'all':
        cmd.append('tests/')
    
    # Run tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if success:
        print(f"\n🎉 All {args.type} tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n💥 Some {args.type} tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
