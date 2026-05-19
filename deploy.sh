#!/bin/bash

# Virtual Environment Reconstruction Platform - Deployment Script
# Supports Azure, GCP, and local deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_info "Prerequisites check passed!"
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    if [ ! -f .env ]; then
        log_warn ".env file not found. Creating from .env.example..."
        cp .env.example .env
        log_warn "Please edit .env file with your configuration before continuing."
        read -p "Press enter to continue after editing .env..."
    fi
    
    # Source environment variables
    export $(cat .env | grep -v '^#' | xargs)
    
    log_info "Environment setup complete!"
}

# Local deployment
deploy_local() {
    log_info "Starting local deployment..."
    
    # Build images
    log_info "Building Docker images..."
    docker-compose build
    
    # Start services
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose exec -T backend alembic upgrade head
    
    # Check health
    log_info "Checking service health..."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_info "Backend is healthy!"
    else
        log_warn "Backend health check failed. Check logs with: docker-compose logs backend"
    fi
    
    log_info "Local deployment complete!"
    log_info "Access the application at:"
    log_info "  - API: http://localhost:8000"
    log_info "  - API Docs: http://localhost:8000/api/v1/docs"
    log_info "  - Frontend: http://localhost:3000"
}

# Azure deployment
deploy_azure() {
    log_info "Starting Azure deployment..."
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Login to Azure
    log_info "Logging in to Azure..."
    az login
    
    # Set variables
    RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"vr-platform-rg"}
    LOCATION=${AZURE_LOCATION:-"eastus"}
    APP_NAME=${AZURE_APP_NAME:-"vr-platform-api"}
    
    # Create resource group
    log_info "Creating resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
    
    # Deploy infrastructure
    if [ -f "azure/main.bicep" ]; then
        log_info "Deploying infrastructure..."
        az deployment group create \
            --resource-group $RESOURCE_GROUP \
            --template-file azure/main.bicep \
            --parameters azure/parameters.json
    fi
    
    # Build and push Docker image
    log_info "Building and pushing Docker image..."
    REGISTRY_NAME="${APP_NAME}registry"
    
    # Create container registry if it doesn't exist
    az acr create \
        --resource-group $RESOURCE_GROUP \
        --name $REGISTRY_NAME \
        --sku Basic \
        --admin-enabled true || true
    
    # Build and push
    az acr build \
        --registry $REGISTRY_NAME \
        --image backend:latest \
        --file docker/Dockerfile.backend \
        .
    
    # Deploy to App Service
    log_info "Deploying to App Service..."
    az webapp config container set \
        --name $APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --docker-custom-image-name ${REGISTRY_NAME}.azurecr.io/backend:latest
    
    # Configure environment variables
    log_info "Configuring environment variables..."
    az webapp config appsettings set \
        --name $APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --settings @azure/app-settings.json
    
    # Restart app
    log_info "Restarting application..."
    az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
    
    # Get URL
    APP_URL=$(az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query defaultHostName -o tsv)
    
    log_info "Azure deployment complete!"
    log_info "Application URL: https://$APP_URL"
}

# GCP deployment
deploy_gcp() {
    log_info "Starting GCP deployment..."
    
    # Check gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Login to GCP
    log_info "Logging in to GCP..."
    gcloud auth login
    
    # Set variables
    PROJECT_ID=${GCP_PROJECT_ID:-"vr-platform"}
    REGION=${GCP_REGION:-"us-central1"}
    SERVICE_NAME=${GCP_SERVICE_NAME:-"vr-platform-api"}
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    # Enable required APIs
    log_info "Enabling required APIs..."
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        sql-component.googleapis.com \
        storage-api.googleapis.com
    
    # Build image
    log_info "Building Docker image..."
    gcloud builds submit --tag gcr.io/$PROJECT_ID/backend
    
    # Deploy to Cloud Run
    log_info "Deploying to Cloud Run..."
    gcloud run deploy $SERVICE_NAME \
        --image gcr.io/$PROJECT_ID/backend \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 2 \
        --set-env-vars-file .env.production
    
    # Get URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
    
    log_info "GCP deployment complete!"
    log_info "Application URL: $SERVICE_URL"
}

# Run tests
run_tests() {
    log_info "Running tests..."
    
    # Backend tests
    log_info "Running backend tests..."
    docker-compose exec -T backend pytest tests/ -v
    
    # Frontend tests
    log_info "Running frontend tests..."
    docker-compose exec -T frontend npm test
    
    log_info "All tests passed!"
}

# Backup database
backup_database() {
    log_info "Backing up database..."
    
    BACKUP_DIR="backups"
    mkdir -p $BACKUP_DIR
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
    
    docker-compose exec -T postgres pg_dump -U postgres vrplatform > $BACKUP_FILE
    
    # Compress
    gzip $BACKUP_FILE
    
    log_info "Database backed up to: ${BACKUP_FILE}.gz"
}

# Restore database
restore_database() {
    if [ -z "$1" ]; then
        log_error "Please provide backup file path"
        exit 1
    fi
    
    BACKUP_FILE=$1
    
    log_info "Restoring database from: $BACKUP_FILE"
    
    if [[ $BACKUP_FILE == *.gz ]]; then
        gunzip < $BACKUP_FILE | docker-compose exec -T postgres psql -U postgres vrplatform
    else
        docker-compose exec -T postgres psql -U postgres vrplatform < $BACKUP_FILE
    fi
    
    log_info "Database restored successfully!"
}

# Show logs
show_logs() {
    SERVICE=${1:-"all"}
    
    if [ "$SERVICE" = "all" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f $SERVICE
    fi
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    docker-compose down
    log_info "Services stopped!"
}

# Clean up
cleanup() {
    log_info "Cleaning up..."
    
    # Stop services
    docker-compose down -v
    
    # Remove images
    docker-compose down --rmi all
    
    # Clean build cache
    docker system prune -f
    
    log_info "Cleanup complete!"
}

# Main menu
show_menu() {
    echo ""
    echo "========================================="
    echo "  VR Platform Deployment Script"
    echo "========================================="
    echo "1. Deploy Locally"
    echo "2. Deploy to Azure"
    echo "3. Deploy to GCP"
    echo "4. Run Tests"
    echo "5. Backup Database"
    echo "6. Restore Database"
    echo "7. Show Logs"
    echo "8. Stop Services"
    echo "9. Cleanup"
    echo "0. Exit"
    echo "========================================="
    echo ""
}

# Main script
main() {
    check_prerequisites
    
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Select an option: " choice
            
            case $choice in
                1)
                    setup_environment
                    deploy_local
                    ;;
                2)
                    setup_environment
                    deploy_azure
                    ;;
                3)
                    setup_environment
                    deploy_gcp
                    ;;
                4)
                    run_tests
                    ;;
                5)
                    backup_database
                    ;;
                6)
                    read -p "Enter backup file path: " backup_file
                    restore_database $backup_file
                    ;;
                7)
                    read -p "Enter service name (or 'all'): " service
                    show_logs $service
                    ;;
                8)
                    stop_services
                    ;;
                9)
                    read -p "Are you sure? This will remove all data. (yes/no): " confirm
                    if [ "$confirm" = "yes" ]; then
                        cleanup
                    fi
                    ;;
                0)
                    log_info "Exiting..."
                    exit 0
                    ;;
                *)
                    log_error "Invalid option"
                    ;;
            esac
            
            read -p "Press enter to continue..."
        done
    else
        # Command line mode
        case $1 in
            local)
                setup_environment
                deploy_local
                ;;
            azure)
                setup_environment
                deploy_azure
                ;;
            gcp)
                setup_environment
                deploy_gcp
                ;;
            test)
                run_tests
                ;;
            backup)
                backup_database
                ;;
            restore)
                restore_database $2
                ;;
            logs)
                show_logs $2
                ;;
            stop)
                stop_services
                ;;
            cleanup)
                cleanup
                ;;
            *)
                log_error "Unknown command: $1"
                echo "Usage: $0 {local|azure|gcp|test|backup|restore|logs|stop|cleanup}"
                exit 1
                ;;
        esac
    fi
}

# Run main
main "$@"

# Made with Bob
