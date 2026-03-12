#!/bin/bash
# MediCureFlow Production Deployment Script
# Run this script on the production server to deploy the application

set -e  # Exit on any error

# Configuration
PROJECT_NAME="MediCureFlow"
PROJECT_USER="www-data"
PROJECT_GROUP="www-data"
PROJECT_DIR="/opt/${PROJECT_NAME}"
VENV_DIR="${PROJECT_DIR}/venv"
REPO_URL="https://github.com/your-org/MediCureFlow.git"  # Update this
BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    # Update package list
    apt update
    
    # Install essential packages
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        postgresql \
        postgresql-contrib \
        redis-server \
        nginx \
        supervisor \
        git \
        curl \
        certbot \
        python3-certbot-nginx \
        ufw
    
    # Install additional Python system packages
    apt install -y \
        python3-dev \
        libpq-dev \
        build-essential \
        libjpeg-dev \
        zlib1g-dev
    
    log_info "System dependencies installed successfully"
}

# Create project user if not exists
create_user() {
    if ! id -u $PROJECT_USER > /dev/null 2>&1; then
        log_info "Creating project user: $PROJECT_USER"
        useradd --system --shell /bin/bash --home $PROJECT_DIR --create-home $PROJECT_USER
    else
        log_info "User $PROJECT_USER already exists"
    fi
}

# Setup project directory
setup_project_dir() {
    log_info "Setting up project directory..."
    
    # Create directories
    mkdir -p $PROJECT_DIR/{logs,media,staticfiles}
    
    # Set permissions
    chown -R $PROJECT_USER:$PROJECT_GROUP $PROJECT_DIR
    chmod -R 755 $PROJECT_DIR
}

# Deploy application code
deploy_code() {
    log_info "Deploying application code..."
    
    if [ ! -d "$PROJECT_DIR/.git" ]; then
        log_info "Cloning repository..."
        sudo -u $PROJECT_USER git clone $REPO_URL $PROJECT_DIR/app
    else
        log_info "Updating repository..."
        cd $PROJECT_DIR/app
        sudo -u $PROJECT_USER git fetch origin
        sudo -u $PROJECT_USER git reset --hard origin/$BRANCH
    fi
    
    # Set proper ownership
    chown -R $PROJECT_USER:$PROJECT_GROUP $PROJECT_DIR/app
}

# Setup Python virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        sudo -u $PROJECT_USER python3 -m venv $VENV_DIR
    fi
    
    # Install Python dependencies
    sudo -u $PROJECT_USER $VENV_DIR/bin/pip install --upgrade pip
    sudo -u $PROJECT_USER $VENV_DIR/bin/pip install -r $PROJECT_DIR/app/requirements-production.txt
}

# Setup database
setup_database() {
    log_info "Setting up PostgreSQL database..."
    
    # Start PostgreSQL service
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE ${PROJECT_NAME}_prod;
CREATE USER ${PROJECT_NAME}_user WITH PASSWORD 'secure_password_change_me';
GRANT ALL PRIVILEGES ON DATABASE ${PROJECT_NAME}_prod TO ${PROJECT_NAME}_user;
ALTER USER ${PROJECT_NAME}_user CREATEDB;
\q
EOF
    
    log_warn "Please update the database password in your .env file!"
}

# Setup Redis
setup_redis() {
    log_info "Setting up Redis..."
    
    # Start Redis service
    systemctl start redis-server
    systemctl enable redis-server
    
    # Basic Redis security configuration
    if ! grep -q "requirepass" /etc/redis/redis.conf; then
        echo "requirepass your_redis_password_here" >> /etc/redis/redis.conf
        systemctl restart redis-server
        log_warn "Please update the Redis password in your .env file!"
    fi
}

# Run Django migrations and collect static files
setup_django() {
    log_info "Setting up Django application..."
    
    cd $PROJECT_DIR/app
    
    # Copy and setup environment file
    if [ ! -f ".env" ]; then
        sudo -u $PROJECT_USER cp .env.production .env
        log_warn "Please configure your .env file with actual production values!"
    fi
    
    # Run Django commands
    sudo -u $PROJECT_USER $VENV_DIR/bin/python manage.py migrate --settings=MediCureFlow.settings.production
    sudo -u $PROJECT_USER $VENV_DIR/bin/python manage.py collectstatic --noinput --settings=MediCureFlow.settings.production
    
    # Create superuser (interactive)
    log_info "Creating Django superuser..."
    sudo -u $PROJECT_USER $VENV_DIR/bin/python manage.py createsuperuser --settings=MediCureFlow.settings.production
}

# Setup systemd service
setup_systemd() {
    log_info "Setting up systemd service..."
    
    # Copy service file
    cp $PROJECT_DIR/app/deployment/MediCureFlow.service /etc/systemd/system/
    
    # Update paths in service file
    sed -i "s|/opt/MediCureFlow|$PROJECT_DIR/app|g" /etc/systemd/system/MediCureFlow.service
    sed -i "s|/opt/MediCureFlow/venv|$VENV_DIR|g" /etc/systemd/system/MediCureFlow.service
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable MediCureFlow
}

# Setup Nginx
setup_nginx() {
    log_info "Setting up Nginx..."
    
    # Copy Nginx configuration
    cp $PROJECT_DIR/app/deployment/nginx.conf /etc/nginx/sites-available/MediCureFlow
    
    # Update paths in Nginx config
    sed -i "s|/opt/MediCureFlow|$PROJECT_DIR/app|g" /etc/nginx/sites-available/MediCureFlow
    
    # Enable site
    ln -sf /etc/nginx/sites-available/MediCureFlow /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    nginx -t
    
    # Start and enable Nginx
    systemctl start nginx
    systemctl enable nginx
}

# Setup firewall
setup_firewall() {
    log_info "Setting up firewall..."
    
    # Configure UFW
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow necessary ports
    ufw allow 22    # SSH
    ufw allow 80    # HTTP
    ufw allow 443   # HTTPS
    
    # Enable firewall
    ufw --force enable
    
    log_info "Firewall configured. SSH (22), HTTP (80), and HTTPS (443) are allowed."
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    read -p "Enter your domain name (e.g., yourdomain.com): " domain
    read -p "Enter your email for Let's Encrypt: " email
    
    if [ -n "$domain" ] && [ -n "$email" ]; then
        log_info "Setting up SSL certificate for $domain..."
        
        # Update Nginx config with actual domain
        sed -i "s/yourdomain.com/$domain/g" /etc/nginx/sites-available/MediCureFlow
        
        # Reload Nginx
        systemctl reload nginx
        
        # Get SSL certificate
        certbot --nginx -d $domain -d www.$domain --email $email --agree-tos --no-eff-email
        
        # Setup auto-renewal
        systemctl enable certbot.timer
    else
        log_warn "Skipping SSL setup. You can run 'certbot --nginx' later."
    fi
}

# Start services
start_services() {
    log_info "Starting services..."
    
    # Start MediCureFlow service
    systemctl start MediCureFlow
    
    # Check service status
    if systemctl is-active --quiet MediCureFlow; then
        log_info "MediCureFlow service is running successfully!"
    else
        log_error "Failed to start MediCureFlow service. Check logs with: journalctl -u MediCureFlow -f"
        exit 1
    fi
}

# Setup log rotation
setup_logrotate() {
    log_info "Setting up log rotation..."
    
    cat > /etc/logrotate.d/MediCureFlow << EOF
$PROJECT_DIR/app/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $PROJECT_USER $PROJECT_GROUP
    postrotate
        systemctl reload MediCureFlow
    endscript
}
EOF
}

# Setup monitoring and health checks
setup_monitoring() {
    log_info "Setting up basic monitoring..."
    
    # Create health check script
    cat > /usr/local/bin/MediCureFlow-health-check.sh << 'EOF'
#!/bin/bash
# Basic health check for MediCureFlow

SERVICE_NAME="MediCureFlow"
URL="http://localhost:8000/health/"

# Check if service is running
if ! systemctl is-active --quiet $SERVICE_NAME; then
    echo "$(date): Service $SERVICE_NAME is not running" >> /var/log/MediCureFlow-health.log
    systemctl restart $SERVICE_NAME
fi

# Check if application responds
if ! curl -f -s $URL > /dev/null; then
    echo "$(date): Application not responding at $URL" >> /var/log/MediCureFlow-health.log
    systemctl restart $SERVICE_NAME
fi
EOF
    
    chmod +x /usr/local/bin/MediCureFlow-health-check.sh
    
    # Add to crontab for automated health checks
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/MediCureFlow-health-check.sh") | crontab -
}

# Main deployment function
main() {
    log_info "Starting MediCureFlow deployment..."
    
    check_root
    install_dependencies
    create_user
    setup_project_dir
    deploy_code
    setup_venv
    setup_database
    setup_redis
    setup_django
    setup_systemd
    setup_nginx
    setup_firewall
    setup_logrotate
    setup_monitoring
    start_services
    
    log_info "Basic deployment completed!"
    
    # Optional SSL setup
    read -p "Do you want to setup SSL with Let's Encrypt? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_ssl
    fi
    
    log_info "Deployment completed successfully!"
    log_info "Your MediCureFlow application should now be accessible."
    log_warn "Don't forget to:"
    log_warn "1. Configure your .env file with actual production values"
    log_warn "2. Update database and Redis passwords"
    log_warn "3. Test the application thoroughly"
    log_warn "4. Setup proper backup procedures"
    
    # Show service status
    log_info "Service status:"
    systemctl status MediCureFlow --no-pager -l
}

# Run main function
main "$@"
