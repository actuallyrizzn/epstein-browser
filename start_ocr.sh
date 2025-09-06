#!/bin/bash

# Epstein Documents OCR Processor - Production Startup Script
# This script manages the OCR processor in a screen session

APP_DIR="/root/epstein-browser/epstein-browser"
APP_NAME="epstein-ocr"
SCREEN_NAME="epstein_ocr"
PYTHON_CMD="venv/bin/python"
OCR_FILE="ocr_processor_lite.py"

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

# Function to check if screen session exists
screen_exists() {
    screen -list | grep -q "$SCREEN_NAME"
}

# Function to check if OCR is running in screen
ocr_running() {
    if screen_exists; then
        screen -S "$SCREEN_NAME" -X stuff "echo 'OCR check'\n" > /dev/null 2>&1
        return $?
    fi
    return 1
}

# Function to start the OCR processor
start_ocr() {
    print_status "Starting $APP_NAME..."
    
    # Change to app directory
    cd "$APP_DIR" || {
        print_error "Failed to change to directory: $APP_DIR"
        exit 1
    }
    
    # Check if database exists
    if [ ! -f "images.db" ]; then
        print_error "Database file 'images.db' not found. Please run index_images.py first."
        exit 1
    fi
    
    # Check if data directory exists
    if [ ! -d "data" ]; then
        print_error "Data directory not found. Please ensure the data directory exists."
        exit 1
    fi
    
    # Check if OCR file exists
    if [ ! -f "$OCR_FILE" ]; then
        print_error "OCR processor file '$OCR_FILE' not found."
        exit 1
    fi
    
    # Kill existing screen session if it exists
    if screen_exists; then
        print_warning "Killing existing screen session..."
        screen -S "$SCREEN_NAME" -X quit
        sleep 2
    fi
    
    # Get max images parameter if provided
    MAX_IMAGES=""
    if [ ! -z "$1" ] && [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_IMAGES="$1"
        print_status "Processing limited to $MAX_IMAGES images for testing"
    fi
    
    # Start new screen session
    print_status "Starting new screen session: $SCREEN_NAME"
    if [ ! -z "$MAX_IMAGES" ]; then
        screen -dmS "$SCREEN_NAME" bash -c "cd '$APP_DIR' && source venv/bin/activate && $PYTHON_CMD $OCR_FILE $MAX_IMAGES"
    else
        screen -dmS "$SCREEN_NAME" bash -c "cd '$APP_DIR' && source venv/bin/activate && $PYTHON_CMD $OCR_FILE"
    fi
    
    # Wait a moment for the OCR to start
    sleep 3
    
    # Check if OCR started successfully
    if screen_exists; then
        print_success "$APP_NAME started successfully in screen session: $SCREEN_NAME"
        print_status "To view the OCR: screen -r $SCREEN_NAME"
        print_status "To detach from screen: Ctrl+A then D"
        print_status "OCR processing will continue in the background"
        return 0
    else
        print_error "Failed to start $APP_NAME"
        return 1
    fi
}

# Function to stop the OCR
stop_ocr() {
    print_status "Stopping $APP_NAME..."
    
    if screen_exists; then
        # Send Ctrl+C to gracefully stop the OCR
        screen -S "$SCREEN_NAME" -X stuff $'\003'
        sleep 2
        screen -S "$SCREEN_NAME" -X quit
        print_success "$APP_NAME stopped"
    else
        print_warning "No screen session found for $APP_NAME"
    fi
}

# Function to restart the OCR
restart_ocr() {
    print_status "Restarting $APP_NAME..."
    stop_ocr
    sleep 2
    start_ocr "$1"
}

# Function to show status
show_status() {
    if screen_exists; then
        if ocr_running; then
            print_success "$APP_NAME is running in screen session: $SCREEN_NAME"
            print_status "Screen session info:"
            screen -list | grep "$SCREEN_NAME"
            
            # Show OCR progress
            print_status "OCR Progress:"
            source venv/bin/activate && python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('images.db')
    cursor = conn.cursor()
    total = cursor.execute('SELECT COUNT(*) FROM images').fetchone()[0]
    processed = cursor.execute('SELECT COUNT(*) FROM images WHERE has_ocr_text = TRUE').fetchone()[0]
    remaining = total - processed
    progress = (processed/total*100) if total > 0 else 0
    print(f'  Total images: {total:,}')
    print(f'  Processed: {processed:,}')
    print(f'  Remaining: {remaining:,}')
    print(f'  Progress: {progress:.1f}%')
    conn.close()
except Exception as e:
    print(f'  Error getting progress: {e}')
"
        else
            print_warning "$APP_NAME screen session exists but OCR may not be running"
        fi
    else
        print_warning "$APP_NAME is not running"
    fi
}

# Function to show logs
show_logs() {
    if screen_exists; then
        print_status "Showing recent logs for $APP_NAME:"
        echo "=========================================="
        # Get the last 50 lines from the screen session
        screen -S "$SCREEN_NAME" -X hardcopy /tmp/ocr_logs.txt
        if [ -f /tmp/ocr_logs.txt ]; then
            tail -50 /tmp/ocr_logs.txt
            rm -f /tmp/ocr_logs.txt
        else
            print_warning "Could not retrieve logs from screen session"
        fi
        echo "=========================================="
        print_status "To view live logs: screen -r $SCREEN_NAME"
        print_status "To detach from live view: Ctrl+A then D"
    else
        print_error "No screen session found for $APP_NAME"
    fi
}

# Function to show help
show_help() {
    echo "Epstein Documents OCR Processor Management"
    echo "=========================================="
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|help} [max_images]"
    echo ""
    echo "Commands:"
    echo "  start [N]   - Start OCR processing (optionally limit to N images for testing)"
    echo "  stop        - Stop OCR processing and kill screen session"
    echo "  restart [N] - Restart OCR processing"
    echo "  status      - Show OCR status and progress"
    echo "  logs        - View OCR logs in screen session"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start           # Process all remaining images"
    echo "  $0 start 100       # Process only 100 images for testing"
    echo "  $0 restart 50      # Restart and process 50 images"
    echo "  $0 status          # Check current progress"
    echo "  $0 logs            # View real-time processing logs"
    echo ""
    echo "Notes:"
    echo "  - OCR processing is idempotent (safe to restart)"
    echo "  - Use Ctrl+C in logs view to detach from screen"
    echo "  - Processing continues in background when detached"
}

# Main script logic
case "$1" in
    start)
        start_ocr "$2"
        ;;
    stop)
        stop_ocr
        ;;
    restart)
        restart_ocr "$2"
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|help} [max_images]"
        echo "Use '$0 help' for detailed usage information"
        exit 1
        ;;
esac

