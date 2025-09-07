#!/bin/bash

# Epstein Documents OCR Processor - Requirements Setup Script
# This script installs both system and Python dependencies

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root or with sudo"
        exit 1
    fi
}

# Function to detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    print_status "Detected OS: $OS $VER"
}

# Function to install system dependencies
install_system_deps() {
    print_status "Installing system dependencies..."
    
    if command -v apt-get >/dev/null 2>&1; then
        # Ubuntu/Debian
        print_status "Installing packages via apt-get..."
        apt-get update
        apt-get install -y tesseract-ocr python3-pip python3-venv
        print_success "System dependencies installed successfully"
    elif command -v yum >/dev/null 2>&1; then
        # CentOS/RHEL
        print_status "Installing packages via yum..."
        yum update -y
        yum install -y tesseract python3-pip python3-venv
        print_success "System dependencies installed successfully"
    elif command -v dnf >/dev/null 2>&1; then
        # Fedora
        print_status "Installing packages via dnf..."
        dnf update -y
        dnf install -y tesseract python3-pip python3-venv
        print_success "System dependencies installed successfully"
    else
        print_error "Unsupported package manager. Please install tesseract-ocr manually."
        print_status "See system-requirements.txt for installation instructions"
        exit 1
    fi
}

# Function to create virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    # Check if virtual environment already exists
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing old one..."
        rm -rf venv
    fi
    
    # Create new virtual environment
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created successfully"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Activate virtual environment and install packages
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        print_success "Python dependencies installed successfully"
    else
        print_error "Failed to install Python dependencies"
        exit 1
    fi
}

# Function to verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check Tesseract
    if command -v tesseract >/dev/null 2>&1; then
        tesseract_version=$(tesseract --version 2>&1 | head -n1)
        print_success "Tesseract found: $tesseract_version"
    else
        print_error "Tesseract not found in PATH"
        return 1
    fi
    
    # Check Python virtual environment
    if [ -f "venv/bin/python" ]; then
        python_version=$(venv/bin/python --version)
        print_success "Python virtual environment: $python_version"
    else
        print_error "Python virtual environment not found"
        return 1
    fi
    
    # Check Python packages
    source venv/bin/activate
    if python -c "import pytesseract, PIL, flask" 2>/dev/null; then
        print_success "Python packages verified successfully"
    else
        print_error "Some Python packages are missing"
        return 1
    fi
    
    return 0
}

# Function to show usage
show_help() {
    echo "Epstein Documents OCR Processor - Requirements Setup"
    echo "=================================================="
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --system-only    Install only system dependencies"
    echo "  --python-only    Install only Python dependencies"
    echo "  --verify-only    Only verify existing installation"
    echo "  --help           Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Install Tesseract OCR engine"
    echo "  2. Create Python virtual environment"
    echo "  3. Install Python dependencies"
    echo "  4. Verify installation"
    echo ""
    echo "Note: This script must be run as root or with sudo"
}

# Main script logic
main() {
    print_status "Starting requirements setup..."
    
    # Parse command line arguments
    SYSTEM_ONLY=false
    PYTHON_ONLY=false
    VERIFY_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --system-only)
                SYSTEM_ONLY=true
                shift
                ;;
            --python-only)
                PYTHON_ONLY=true
                shift
                ;;
            --verify-only)
                VERIFY_ONLY=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check if we're running as root (unless verify-only)
    if [ "$VERIFY_ONLY" = false ]; then
        check_root
    fi
    
    # Detect OS
    detect_os
    
    # Verify only mode
    if [ "$VERIFY_ONLY" = true ]; then
        verify_installation
        exit $?
    fi
    
    # Install system dependencies
    if [ "$PYTHON_ONLY" = false ]; then
        install_system_deps
    fi
    
    # Setup Python environment
    if [ "$SYSTEM_ONLY" = false ]; then
        setup_python_env
        install_python_deps
    fi
    
    # Verify installation
    if verify_installation; then
        print_success "All requirements installed successfully!"
        print_status "You can now run: ./start_ocr.sh start"
    else
        print_error "Installation verification failed"
        exit 1
    fi
}

# Run main function
main "$@"
