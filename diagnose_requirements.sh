#!/bin/bash

# Epstein Documents OCR Processor - Requirements Diagnostic Script
# This script checks what requirements are missing

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Function to check system requirements
check_system_requirements() {
    echo "=== SYSTEM REQUIREMENTS ==="
    
    # Check Tesseract
    if command -v tesseract >/dev/null 2>&1; then
        tesseract_version=$(tesseract --version 2>&1 | head -n1)
        print_success "Tesseract found: $tesseract_version"
    else
        print_error "Tesseract not found - install with: apt-get install tesseract-ocr"
    fi
    
    # Check Python3
    if command -v python3 >/dev/null 2>&1; then
        python_version=$(python3 --version)
        print_success "Python3 found: $python_version"
    else
        print_error "Python3 not found - install with: apt-get install python3"
    fi
    
    # Check pip3
    if command -v pip3 >/dev/null 2>&1; then
        pip_version=$(pip3 --version)
        print_success "pip3 found: $pip_version"
    else
        print_error "pip3 not found - install with: apt-get install python3-pip"
    fi
    
    # Check venv module
    if python3 -m venv --help >/dev/null 2>&1; then
        print_success "Python venv module available"
    else
        print_error "Python venv module not found - install with: apt-get install python3-venv"
    fi
}

# Function to check Python virtual environment
check_python_env() {
    echo ""
    echo "=== PYTHON VIRTUAL ENVIRONMENT ==="
    
    if [ -d "venv" ]; then
        print_success "Virtual environment directory exists"
        
        if [ -f "venv/bin/python" ]; then
            python_version=$(venv/bin/python --version)
            print_success "Virtual environment Python: $python_version"
        else
            print_error "Virtual environment Python not found"
        fi
        
        if [ -f "venv/bin/activate" ]; then
            print_success "Virtual environment activation script exists"
        else
            print_error "Virtual environment activation script not found"
        fi
    else
        print_error "Virtual environment not found - run: python3 -m venv venv"
    fi
}

# Function to check Python packages
check_python_packages() {
    echo ""
    echo "=== PYTHON PACKAGES ==="
    
    if [ -f "venv/bin/python" ]; then
        # Activate virtual environment and check packages
        source venv/bin/activate 2>/dev/null
        
        # Check each required package
        packages=("flask" "PIL" "pytesseract" "markdown" "dotenv")
        
        for package in "${packages[@]}"; do
            if python -c "import $package" 2>/dev/null; then
                print_success "Package '$package' is installed"
            else
                print_error "Package '$package' is missing - install with: pip install $package"
            fi
        done
        
        # Check specific imports
        echo ""
        print_status "Checking specific imports..."
        
        if python -c "from flask import Flask" 2>/dev/null; then
            print_success "Flask import works"
        else
            print_error "Flask import failed"
        fi
        
        if python -c "from PIL import Image" 2>/dev/null; then
            print_success "PIL (Pillow) import works"
        else
            print_error "PIL (Pillow) import failed"
        fi
        
        if python -c "import pytesseract" 2>/dev/null; then
            print_success "pytesseract import works"
        else
            print_error "pytesseract import failed"
        fi
        
        if python -c "import markdown" 2>/dev/null; then
            print_success "markdown import works"
        else
            print_error "markdown import failed"
        fi
        
        if python -c "from dotenv import load_dotenv" 2>/dev/null; then
            print_success "python-dotenv import works"
        else
            print_error "python-dotenv import failed"
        fi
    else
        print_error "Cannot check Python packages - virtual environment not found"
    fi
}

# Function to check project files
check_project_files() {
    echo ""
    echo "=== PROJECT FILES ==="
    
    # Check required files
    files=("ocr_processor_lite.py" "app.py" "requirements.txt" "images.db" "data")
    
    for file in "${files[@]}"; do
        if [ -e "$file" ]; then
            print_success "File/directory '$file' exists"
        else
            print_error "File/directory '$file' missing"
        fi
    done
}

# Function to check OCR processor specifically
check_ocr_processor() {
    echo ""
    echo "=== OCR PROCESSOR TEST ==="
    
    if [ -f "venv/bin/python" ] && [ -f "ocr_processor_lite.py" ]; then
        source venv/bin/activate 2>/dev/null
        
        # Test if OCR processor can be imported
        if python -c "import ocr_processor_lite" 2>/dev/null; then
            print_success "OCR processor can be imported"
            
            # Test Tesseract availability from Python
            if python -c "import subprocess; subprocess.run(['tesseract', '--version'], capture_output=True, timeout=10)" 2>/dev/null; then
                print_success "Tesseract is accessible from Python"
            else
                print_error "Tesseract is not accessible from Python"
            fi
        else
            print_error "OCR processor cannot be imported"
        fi
    else
        print_error "Cannot test OCR processor - missing requirements"
    fi
}

# Function to provide recommendations
provide_recommendations() {
    echo ""
    echo "=== RECOMMENDATIONS ==="
    
    # Check if we're missing system dependencies
    if ! command -v tesseract >/dev/null 2>&1; then
        print_warning "Install system dependencies:"
        echo "  sudo apt-get update"
        echo "  sudo apt-get install tesseract-ocr python3-pip python3-venv"
    fi
    
    # Check if we're missing Python environment
    if [ ! -d "venv" ]; then
        print_warning "Create Python virtual environment:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
    fi
    
    # Check if we're missing Python packages
    if [ -f "venv/bin/python" ]; then
        source venv/bin/activate 2>/dev/null
        if ! python -c "import pytesseract" 2>/dev/null; then
            print_warning "Install Python packages:"
            echo "  source venv/bin/activate"
            echo "  pip install -r requirements.txt"
        fi
    fi
    
    # Check if we're missing project files
    if [ ! -f "images.db" ]; then
        print_warning "Database not found - run index_images.py first:"
        echo "  source venv/bin/activate"
        echo "  python index_images.py"
    fi
    
    if [ ! -d "data" ]; then
        print_warning "Data directory not found - ensure your document images are in the 'data' directory"
    fi
}

# Main function
main() {
    echo "Epstein Documents OCR Processor - Requirements Diagnostic"
    echo "========================================================"
    echo ""
    
    check_system_requirements
    check_python_env
    check_python_packages
    check_project_files
    check_ocr_processor
    provide_recommendations
    
    echo ""
    echo "=== SUMMARY ==="
    print_status "Run './setup_requirements.sh' to install missing requirements"
    print_status "Run './diagnose_requirements.sh' again to verify installation"
}

# Run main function
main "$@"
