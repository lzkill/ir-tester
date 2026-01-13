#!/bin/bash
#
# IR Tester - Build Script for .deb Package
# Creates a .deb package with embedded Python virtual environment
#

set -e

# Configuration
APP_NAME="ir-tester"
ARCH="amd64"
MAINTAINER="IR Tester Dev <dev@ir-tester.local>"
DESCRIPTION="Impulse Response Tester for Guitar"

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

# Read version from VERSION file
if [ -f "${PROJECT_DIR}/VERSION" ]; then
    APP_VERSION=$(cat "${PROJECT_DIR}/VERSION" | tr -d '[:space:]')
else
    APP_VERSION="0.0.0"
fi

BUILD_DIR="${SCRIPT_DIR}/build"
PKG_DIR="${BUILD_DIR}/${APP_NAME}_${APP_VERSION}_${ARCH}"
INSTALL_DIR="${PKG_DIR}/opt/${APP_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking build dependencies..."
    
    local missing_deps=()
    
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    if ! command -v dpkg-deb &> /dev/null; then
        missing_deps+=("dpkg-deb (install dpkg)")
    fi
    
    if ! python3 -c "import venv" &> /dev/null; then
        missing_deps+=("python3-venv")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        echo "Install them with:"
        echo "  sudo apt install python3 python3-venv dpkg"
        exit 1
    fi
    
    log_success "All build dependencies found"
}

# Clean previous builds
clean_build() {
    log_info "Cleaning previous build..."
    rm -rf "${BUILD_DIR}"
    log_success "Build directory cleaned"
}

# Create directory structure
create_structure() {
    log_info "Creating package directory structure..."
    
    mkdir -p "${INSTALL_DIR}"
    mkdir -p "${PKG_DIR}/DEBIAN"
    mkdir -p "${PKG_DIR}/usr/share/applications"
    mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"
    mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "${PKG_DIR}/opt/${APP_NAME}/bin"
    
    log_success "Directory structure created"
}

# Create virtual environment and install dependencies
create_venv() {
    log_info "Creating Python virtual environment..."
    
    python3 -m venv "${INSTALL_DIR}/venv"
    
    log_info "Installing Python dependencies..."
    
    # Activate venv and install requirements
    source "${INSTALL_DIR}/venv/bin/activate"
    pip install --upgrade pip wheel
    pip install -r "${PROJECT_DIR}/requirements.txt"
    deactivate
    
    log_success "Virtual environment created and dependencies installed"
}

# Copy application files
copy_app_files() {
    log_info "Copying application files..."
    
    # Copy Python source files
    cp "${PROJECT_DIR}/main.py" "${INSTALL_DIR}/"
    cp "${PROJECT_DIR}/requirements.txt" "${INSTALL_DIR}/"
    cp -r "${PROJECT_DIR}/audio" "${INSTALL_DIR}/"
    cp -r "${PROJECT_DIR}/ui" "${INSTALL_DIR}/"
    
    # Copy sample directory if it exists
    if [ -d "${PROJECT_DIR}/sample" ]; then
        cp -r "${PROJECT_DIR}/sample" "${INSTALL_DIR}/"
    fi
    
    # Remove __pycache__ directories
    find "${INSTALL_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Application files copied"
}

# Create launcher script
create_launcher() {
    log_info "Creating launcher script..."
    
    cat > "${PKG_DIR}/opt/${APP_NAME}/bin/${APP_NAME}" << 'EOF'
#!/bin/bash
#
# IR Tester Launcher
#

APP_DIR="/opt/ir-tester"
VENV_DIR="${APP_DIR}/venv"

# Activate virtual environment and run the application
source "${VENV_DIR}/bin/activate"
cd "${APP_DIR}"
python3 main.py "$@"
deactivate
EOF

    chmod +x "${PKG_DIR}/opt/${APP_NAME}/bin/${APP_NAME}"
    
    log_success "Launcher script created"
}

# Install desktop entry and icons
install_desktop_files() {
    log_info "Installing desktop entry and icons..."
    
    # Copy desktop entry
    cp "${SCRIPT_DIR}/assets/ir-tester.desktop" "${PKG_DIR}/usr/share/applications/"
    
    # Copy SVG icon
    cp "${SCRIPT_DIR}/assets/icons/ir-tester.svg" "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/"
    
    # Generate PNG from SVG if rsvg-convert is available, otherwise copy SVG
    if command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w 256 -h 256 "${SCRIPT_DIR}/assets/icons/ir-tester.svg" \
            -o "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/ir-tester.png"
        log_success "PNG icon generated from SVG"
    else
        log_warning "rsvg-convert not found, using SVG only"
        cp "${SCRIPT_DIR}/assets/icons/ir-tester.svg" "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/"
    fi
    
    log_success "Desktop files installed"
}

# Create DEBIAN control files
create_debian_control() {
    log_info "Creating DEBIAN control files..."
    
    # Calculate installed size (in KB)
    INSTALLED_SIZE=$(du -sk "${PKG_DIR}" | cut -f1)
    
    # Create control file
    cat > "${PKG_DIR}/DEBIAN/control" << EOF
Package: ${APP_NAME}
Version: ${APP_VERSION}
Section: sound
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Depends: libportaudio2, libsndfile1, python3 (>= 3.9), libxcb-cursor0
Maintainer: ${MAINTAINER}
Description: ${DESCRIPTION}
 Desktop application for testing Impulse Responses (IR) of guitar
 cabinets and amplifiers with Direct Input (DI) files.
 .
 Features:
  - 10-band graphic equalizer
  - Real-time frequency visualization (20Hz-20kHz)
  - Instant convolution processing
  - Mix A/B with Dry/Wet slider
  - Dark modern interface
  - Complete playback controls
Homepage: https://github.com/ir-tester/ir-tester
EOF

    # Create postinst script
    cat > "${PKG_DIR}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Update desktop database
if [ -x "$(command -v update-desktop-database)" ]; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

# Update icon cache
if [ -x "$(command -v gtk-update-icon-cache)" ]; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
fi

exit 0
EOF
    chmod 755 "${PKG_DIR}/DEBIAN/postinst"

    # Create postrm script
    cat > "${PKG_DIR}/DEBIAN/postrm" << 'EOF'
#!/bin/bash
set -e

# Update desktop database
if [ -x "$(command -v update-desktop-database)" ]; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

# Update icon cache
if [ -x "$(command -v gtk-update-icon-cache)" ]; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
fi

exit 0
EOF
    chmod 755 "${PKG_DIR}/DEBIAN/postrm"
    
    log_success "DEBIAN control files created"
}

# Build the .deb package
build_deb() {
    log_info "Building .deb package..."
    
    # Set correct permissions
    find "${PKG_DIR}" -type d -exec chmod 755 {} \;
    find "${PKG_DIR}" -type f -exec chmod 644 {} \;
    chmod 755 "${PKG_DIR}/opt/${APP_NAME}/bin/${APP_NAME}"
    chmod 755 "${PKG_DIR}/DEBIAN/postinst"
    chmod 755 "${PKG_DIR}/DEBIAN/postrm"
    
    # Make venv executables executable
    find "${INSTALL_DIR}/venv/bin" -type f -exec chmod 755 {} \;
    
    # Build package with faster compression (gzip instead of default xz)
    log_info "Compressing package (this may take a minute)..."
    dpkg-deb -Zgzip --build --root-owner-group "${PKG_DIR}"
    
    # Move to dist directory
    mkdir -p "${SCRIPT_DIR}/dist"
    mv "${BUILD_DIR}/${APP_NAME}_${APP_VERSION}_${ARCH}.deb" "${SCRIPT_DIR}/dist/"
    
    log_success "Package built: dist/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
}

# Print package info
print_info() {
    echo ""
    echo "=========================================="
    echo "   IR Tester .deb Package Built!"
    echo "=========================================="
    echo ""
    echo "Package: dist/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
    echo ""
    echo "To install:"
    echo "  sudo dpkg -i dist/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
    echo ""
    echo "To fix missing dependencies (if any):"
    echo "  sudo apt install -f"
    echo ""
    echo "To uninstall:"
    echo "  sudo dpkg -r ${APP_NAME}"
    echo ""
    echo "After installation, find 'IR Tester' in your"
    echo "application menu or run: ${APP_NAME}"
    echo "=========================================="
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "   IR Tester .deb Package Builder"
    echo "=========================================="
    echo ""
    
    check_dependencies
    clean_build
    create_structure
    create_venv
    copy_app_files
    create_launcher
    install_desktop_files
    create_debian_control
    build_deb
    print_info
}

# Run main
main "$@"
