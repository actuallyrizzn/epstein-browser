#!/bin/bash

# Epstein Documents Browser - Production Startup Script
# This script manages the Flask app in a screen session

APP_DIR="/root/epstein-browser/epstein-browser"
APP_NAME="epstein-browser"
SCREEN_NAME="epstein_app"
PYTHON_CMD="venv/bin/python"
APP_FILE="app.py"

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

# Function to check if app is running in screen
app_running() {
    if screen_exists; then
        screen -S "$SCREEN_NAME" -X stuff "echo 'App check'\n" > /dev/null 2>&1
        return $?
    fi
    return 1
}

# Function to start the app
start_app() {
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
    
    # Kill existing screen session if it exists
    if screen_exists; then
        print_warning "Killing existing screen session..."
        screen -S "$SCREEN_NAME" -X quit
        sleep 2
    fi
    
    # Start new screen session
    print_status "Starting new screen session: $SCREEN_NAME"
    screen -dmS "$SCREEN_NAME" bash -c "cd '$APP_DIR' && FLASK_ENV=production $PYTHON_CMD $APP_FILE"
    
    # Wait a moment for the app to start
    sleep 3
    
    # Check if app started successfully
    if app_running; then
        print_success "$APP_NAME started successfully in screen session: $SCREEN_NAME"
        print_status "To view the app: screen -r $SCREEN_NAME"
        print_status "To detach from screen: Ctrl+A then D"
        return 0
    else
        print_error "Failed to start $APP_NAME"
        return 1
    fi
}

# Function to stop the app
stop_app() {
    print_status "Stopping $APP_NAME..."
    
    if screen_exists; then
        screen -S "$SCREEN_NAME" -X quit
        print_success "$APP_NAME stopped"
    else
        print_warning "No screen session found for $APP_NAME"
    fi
}

# Function to restart the app
restart_app() {
    print_status "Restarting $APP_NAME..."
    stop_app
    sleep 2
    start_app
}

# Function to show status
show_status() {
    if screen_exists; then
        if app_running; then
            print_success "$APP_NAME is running in screen session: $SCREEN_NAME"
            print_status "Screen session info:"
            screen -list | grep "$SCREEN_NAME"
        else
            print_warning "$APP_NAME screen session exists but app may not be running"
        fi
    else
        print_warning "$APP_NAME is not running"
    fi
}

# Function to show logs
show_logs() {
    if screen_exists; then
        print_status "Showing logs for $APP_NAME (Ctrl+C to exit):"
        screen -r "$SCREEN_NAME"
    else
        print_error "No screen session found for $APP_NAME"
    fi
}

# Main script logic
case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the application in a screen session"
        echo "  stop    - Stop the application and kill screen session"
        echo "  restart - Restart the application"
        echo "  status  - Show application status"
        echo "  logs    - View application logs in screen session"
        exit 1
        ;;
esac
