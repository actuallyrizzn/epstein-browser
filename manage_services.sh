#!/bin/bash

# Service Management Script for Epstein Browser
# Manages both nginx and Flask app services

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to check service status
check_status() {
    print_status "Checking service status..."
    
    # Check nginx
    if systemctl is-active --quiet nginx; then
        print_success "Nginx: Running"
    else
        print_error "Nginx: Not running"
    fi
    
    # Check Flask app
    if screen -list | grep -q "epstein_app"; then
        print_success "Flask App: Running in screen session"
    else
        print_warning "Flask App: Not running"
    fi
    
    # Check OCR processor
    if screen -list | grep -q "epstein_ocr"; then
        print_success "OCR Processor: Running in screen session"
    else
        print_warning "OCR Processor: Not running"
    fi
}

# Function to start all services
start_all() {
    print_status "Starting all services..."
    
    # Start nginx
    systemctl start nginx
    if systemctl is-active --quiet nginx; then
        print_success "Nginx started"
    else
        print_error "Failed to start nginx"
    fi
    
    # Start Flask app
    ./start_app.sh start-if-missing
    
    print_status "Services started. Access the application at: http://localhost"
}

# Function to stop all services
stop_all() {
    print_status "Stopping all services..."
    
    # Stop Flask app
    ./start_app.sh stop
    
    # Stop OCR processor
    ./start_ocr.sh stop
    
    # Stop nginx
    systemctl stop nginx
    print_success "All services stopped"
}

# Function to restart all services
restart_all() {
    print_status "Restarting all services..."
    stop_all
    sleep 2
    start_all
}

# Function to show logs
show_logs() {
    print_status "Showing service logs..."
    echo "=== Nginx Status ==="
    systemctl status nginx --no-pager
    echo ""
    echo "=== Flask App Logs ==="
    ./start_app.sh logs
    echo ""
    echo "=== OCR Processor Logs ==="
    ./start_ocr.sh logs
}

# Function to show help
show_help() {
    echo "Epstein Browser Service Management"
    echo "=================================="
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start    - Start all services (nginx + Flask app)"
    echo "  stop     - Stop all services"
    echo "  restart  - Restart all services"
    echo "  status   - Show status of all services"
    echo "  logs     - Show logs from all services"
    echo "  help     - Show this help message"
    echo ""
    echo "Individual service management:"
    echo "  ./start_app.sh {start|stop|restart|status|logs}"
    echo "  ./start_ocr.sh {start|stop|restart|status|logs}"
}

# Main script logic
case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|help}"
        echo "Use '$0 help' for detailed usage information"
        exit 1
        ;;
esac
