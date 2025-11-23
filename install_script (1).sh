#!/bin/bash

# Script de instalación para SRT to Video TTS
# Compatible con macOS, Linux y Windows (Git Bash/WSL)
# Version 2.5

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}    SRT to Video TTS - Instalador v2.5${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""

# Detectar sistema operativo
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        echo -e "${GREEN}✓ Sistema detectado: macOS${NC}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        echo -e "${GREEN}✓ Sistema detectado: Linux${NC}"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
        echo -e "${GREEN}✓ Sistema detectado: Windows (Git Bash/MSYS)${NC}"
    else
        echo -e "${RED}✗ Sistema operativo no soportado: $OSTYPE${NC}"
        exit 1
    fi
}

# Verificar si un comando existe
command_exists() {
    command -v "$1" &> /dev/null
}

# Instalar dependencias en macOS
install_macos() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Instalando dependencias para macOS${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    
    # Verificar Homebrew
    if ! command_exists brew; then
        echo -e "${YELLOW}Homebrew no encontrado. Instalando...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Agregar Homebrew al PATH según la arquitectura
        if [[ $(uname -m) == "arm64" ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        else
            echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        
        echo -e "${GREEN}✓ Homebrew instalado${NC}"
    else
        echo -e "${GREEN}✓ Homebrew ya instalado${NC}"
    fi
    
    # Actualizar Homebrew
    echo -e "${YELLOW}Actualizando Homebrew...${NC}"
    brew update
    
    # Instalar FFmpeg
    if ! command_exists ffmpeg; then
        echo -e "${YELLOW}Instalando FFmpeg...${NC}"
        brew install ffmpeg
        echo -e "${GREEN}✓ FFmpeg instalado${NC}"
    else
        echo -e "${GREEN}✓ FFmpeg ya instalado${NC}"
    fi
    
    # Instalar BC
    if ! command_exists bc; then
        echo -e "${YELLOW}Instalando BC (calculadora)...${NC}"
        brew install bc
        echo -e "${GREEN}✓ BC instalado${NC}"
    else
        echo -e "${GREEN}✓ BC ya instalado${NC}"
    fi
    
    # Instalar Bash moderno (4.0+)
    echo ""
    echo -e "${YELLOW}Verificando versión de Bash...${NC}"
    BASH_VERSION_INSTALLED=$(bash --version | head -n1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    BASH_MAJOR_VERSION=$(echo $BASH_VERSION_INSTALLED | cut -d. -f1)
    
    echo -e "${BLUE}Versión actual de Bash: $BASH_VERSION_INSTALLED${NC}"
    
    if [ "$BASH_MAJOR_VERSION" -lt 4 ]; then
        echo -e "${YELLOW}⚠️  Bash $BASH_VERSION_INSTALLED es muy antiguo para el script${NC}"
        echo -e "${YELLOW}   Se requiere Bash 4.0 o superior${NC}"
        echo -e "${YELLOW}Instalando Bash moderno...${NC}"
        brew install bash
        echo -e "${GREEN}✓ Bash moderno instalado${NC}"
    else
        echo -e "${GREEN}✓ Versión de Bash adecuada${NC}"
    fi
    
    # Verificar si Bash de Homebrew está instalado
    if [ -f "/opt/homebrew/bin/bash" ] || [ -f "/usr/local/bin/bash" ]; then
        # Determinar ruta de Bash de Homebrew según arquitectura
        if [ -f "/opt/homebrew/bin/bash" ]; then
            BREW_BASH="/opt/homebrew/bin/bash"
        else
            BREW_BASH="/usr/local/bin/bash"
        fi
        
        BREW_BASH_VERSION=$($BREW_BASH --version | head -n1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        echo -e "${BLUE}Bash de Homebrew: $BREW_BASH_VERSION en $BREW_BASH${NC}"
        
        # Agregar a shells permitidos si no está
        if ! grep -q "$BREW_BASH" /etc/shells 2>/dev/null; then
            echo -e "${YELLOW}Agregando Bash de Homebrew a shells permitidos...${NC}"
            echo "$BREW_BASH" | sudo tee -a /etc/shells > /dev/null
            echo -e "${GREEN}✓ Bash agregado a /etc/shells${NC}"
        fi
        
        # Configurar alias bash2
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}Configurando alias 'bash2' para Bash moderno${NC}"
        echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
        
        # Determinar shell del usuario
        USER_SHELL=$(echo $SHELL)
        
        if [[ "$USER_SHELL" == *"zsh"* ]]; then
            SHELL_RC="$HOME/.zshrc"
        elif [[ "$USER_SHELL" == *"bash"* ]]; then
            SHELL_RC="$HOME/.bash_profile"
            # También agregar a .bashrc si existe
            if [ -f "$HOME/.bashrc" ]; then
                SHELL_RC_ALT="$HOME/.bashrc"
            fi
        else
            SHELL_RC="$HOME/.profile"
        fi
        
        # Crear archivo de configuración si no existe
        touch "$SHELL_RC"
        
        # Verificar si el alias ya existe
        if ! grep -q "alias bash2=" "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# Bash moderno de Homebrew para scripts (SRT to Video TTS)" >> "$SHELL_RC"
            echo "alias bash2=\"$BREW_BASH\"" >> "$SHELL_RC"
            echo -e "${GREEN}✓ Alias 'bash2' agregado a $SHELL_RC${NC}"
        else
            echo -e "${GREEN}✓ Alias 'bash2' ya existe en $SHELL_RC${NC}"
        fi
        
        # También agregar a .bashrc si es necesario
        if [ -n "$SHELL_RC_ALT" ] && [ -f "$SHELL_RC_ALT" ]; then
            if ! grep -q "alias bash2=" "$SHELL_RC_ALT" 2>/dev/null; then
                echo "" >> "$SHELL_RC_ALT"
                echo "# Bash moderno de Homebrew para scripts (SRT to Video TTS)" >> "$SHELL_RC_ALT"
                echo "alias bash2=\"$BREW_BASH\"" >> "$SHELL_RC_ALT"
                echo -e "${GREEN}✓ Alias 'bash2' también agregado a $SHELL_RC_ALT${NC}"
            fi
        fi
        
        # Crear symlink en directorio local del usuario
        LOCAL_BIN="$HOME/.local/bin"
        mkdir -p "$LOCAL_BIN"
        
        if [ ! -f "$LOCAL_BIN/bash2" ]; then
            ln -s "$BREW_BASH" "$LOCAL_BIN/bash2"
            echo -e "${GREEN}✓ Symlink creado en $LOCAL_BIN/bash2${NC}"
        else
            echo -e "${GREEN}✓ Symlink ya existe en $LOCAL_BIN/bash2${NC}"
        fi
        
        # Agregar ~/.local/bin al PATH si no está
        if ! grep -q "$LOCAL_BIN" "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# Agregar ~/.local/bin al PATH" >> "$SHELL_RC"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
            echo -e "${GREEN}✓ ~/.local/bin agregado al PATH${NC}"
        fi
        
        echo ""
        echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}Configuración de Bash completada${NC}"
        echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}Para usar Bash moderno, tienes 3 opciones:${NC}"
        echo ""
        echo -e "${GREEN}1. Usar el alias 'bash2':${NC}"
        echo -e "   ${BLUE}bash2 srt_to_video_v2.5.sh subtitulos.srt video.mp4${NC}"
        echo ""
        echo -e "${GREEN}2. Especificar ruta completa de Bash:${NC}"
        echo -e "   ${BLUE}$BREW_BASH srt_to_video_v2.5.sh subtitulos.srt video.mp4${NC}"
        echo ""
        echo -e "${GREEN}3. Cambiar shebang del script:${NC}"
        echo -e "   ${BLUE}#!/opt/homebrew/bin/bash${NC} (o /usr/local/bin/bash)"
        echo ""
        echo -e "${YELLOW}Para activar el alias en la sesión actual:${NC}"
        echo -e "   ${BLUE}source $SHELL_RC${NC}"
        echo ""
    fi
    
    # Verificar comando 'say' (debería estar por defecto en macOS)
    if command_exists say; then
        echo -e "${GREEN}✓ Comando 'say' disponible (TTS nativo de macOS)${NC}"
    else
        echo -e "${RED}⚠️  Comando 'say' no encontrado${NC}"
        echo -e "${YELLOW}   Esto es inusual en macOS. Considera reinstalar el sistema.${NC}"
    fi
}

# Instalar dependencias en Linux
install_linux() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Instalando dependencias para Linux${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    
    # Detectar distribución
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    else
        DISTRO="unknown"
    fi
    
    echo -e "${BLUE}Distribución detectada: $DISTRO${NC}"
    
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            echo -e "${YELLOW}Usando gestor de paquetes APT...${NC}"
            
            # Actualizar repositorios
            echo -e "${YELLOW}Actualizando repositorios...${NC}"
            sudo apt update
            
            # Instalar dependencias
            echo -e "${YELLOW}Instalando ffmpeg, bc, python3 y pip...${NC}"
            sudo apt install -y ffmpeg bc python3 python3-pip
            
            echo -e "${GREEN}✓ Dependencias del sistema instaladas${NC}"
            ;;
            
        fedora|rhel|centos|rocky|almalinux)
            echo -e "${YELLOW}Usando gestor de paquetes DNF/YUM...${NC}"
            
            # Instalar dependencias
            if command_exists dnf; then
                echo -e "${YELLOW}Instalando dependencias con DNF...${NC}"
                sudo dnf install -y ffmpeg bc python3 python3-pip
            else
                echo -e "${YELLOW}Instalando dependencias con YUM...${NC}"
                sudo yum install -y ffmpeg bc python3 python3-pip
            fi
            
            echo -e "${GREEN}✓ Dependencias del sistema instaladas${NC}"
            ;;
            
        arch|manjaro)
            echo -e "${YELLOW}Usando gestor de paquetes Pacman...${NC}"
            
            # Actualizar sistema
            sudo pacman -Sy
            
            # Instalar dependencias
            sudo pacman -S --noconfirm ffmpeg bc python python-pip
            
            echo -e "${GREEN}✓ Dependencias del sistema instaladas${NC}"
            ;;
            
        *)
            echo -e "${RED}⚠️  Distribución no reconocida automáticamente${NC}"
            echo -e "${YELLOW}Por favor, instala manualmente:${NC}"
            echo -e "${YELLOW}  - ffmpeg${NC}"
            echo -e "${YELLOW}  - bc${NC}"
            echo -e "${YELLOW}  - python3${NC}"
            echo -e "${YELLOW}  - python3-pip${NC}"
            exit 1
            ;;
    esac
    
    # Instalar paquetes Python
    echo ""
    echo -e "${YELLOW}Instalando paquetes Python (gTTS y pydub)...${NC}"
    
    # Verificar si pip3 está disponible
    if command_exists pip3; then
        pip3 install --user gtts pydub
        echo -e "${GREEN}✓ Paquetes Python instalados${NC}"
    elif command_exists pip; then
        pip install --user gtts pydub
        echo -e "${GREEN}✓ Paquetes Python instalados${NC}"
    else
        echo -e "${RED}✗ pip no encontrado${NC}"
        exit 1
    fi
    
    # Verificar versión de Bash
    echo ""
    echo -e "${YELLOW}Verificando versión de Bash...${NC}"
    BASH_VERSION_INSTALLED=$(bash --version | head -n1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    BASH_MAJOR_VERSION=$(echo $BASH_VERSION_INSTALLED | cut -d. -f1)
    
    echo -e "${BLUE}Versión de Bash: $BASH_VERSION_INSTALLED${NC}"
    
    if [ "$BASH_MAJOR_VERSION" -ge 4 ]; then
        echo -e "${GREEN}✓ Versión de Bash adecuada${NC}"
    else
        echo -e "${YELLOW}⚠️  Bash $BASH_VERSION_INSTALLED puede tener problemas${NC}"
        echo -e "${YELLOW}   Se recomienda Bash 4.0 o superior${NC}"
    fi
}

# Instalar dependencias en Windows
install_windows() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Instalando dependencias para Windows${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    
    echo -e "${YELLOW}Entorno detectado: Git Bash / MSYS${NC}"
    
    # Verificar FFmpeg
    if ! command_exists ffmpeg; then
        echo -e "${RED}✗ FFmpeg no encontrado${NC}"
        echo -e "${YELLOW}Por favor, instala FFmpeg:${NC}"
        echo -e "${CYAN}  1. Descarga desde: https://ffmpeg.org/download.html${NC}"
        echo -e "${CYAN}  2. O usa Chocolatey: choco install ffmpeg${NC}"
        echo -e "${CYAN}  3. Asegúrate de agregar FFmpeg al PATH${NC}"
        echo ""
        read -p "Presiona ENTER después de instalar FFmpeg..."
        
        if ! command_exists ffmpeg; then
            echo -e "${RED}FFmpeg aún no está disponible. Saliendo.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ FFmpeg instalado${NC}"
    fi
    
    # Verificar BC
    if ! command_exists bc; then
        echo -e "${RED}✗ BC no encontrado${NC}"
        echo -e "${YELLOW}BC debería venir con Git Bash${NC}"
        echo -e "${YELLOW}Si no está disponible, considera usar WSL (Windows Subsystem for Linux)${NC}"
    else
        echo -e "${GREEN}✓ BC disponible${NC}"
    fi
    
    # Verificar Python
    if ! command_exists python && ! command_exists python3; then
        echo -e "${RED}✗ Python no encontrado${NC}"
        echo -e "${YELLOW}Por favor, instala Python:${NC}"
        echo -e "${CYAN}  1. Descarga desde: https://www.python.org/downloads/${NC}"
        echo -e "${CYAN}  2. O usa Chocolatey: choco install python${NC}"
        echo -e "${CYAN}  3. Asegúrate de marcar 'Add Python to PATH' durante instalación${NC}"
        echo ""
        read -p "Presiona ENTER después de instalar Python..."
        
        if ! command_exists python && ! command_exists python3; then
            echo -e "${RED}Python aún no está disponible. Saliendo.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Python instalado${NC}"
    fi
    
    # Instalar paquetes Python
    echo ""
    echo -e "${YELLOW}Instalando paquetes Python (gTTS y pydub)...${NC}"
    
    if command_exists pip3; then
        pip3 install gtts pydub
    elif command_exists pip; then
        pip install gtts pydub
    else
        echo -e "${RED}✗ pip no encontrado${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Paquetes Python instalados${NC}"
}

# Hacer scripts ejecutables
make_executable() {
    echo ""
    echo -e "${YELLOW}Haciendo scripts ejecutables...${NC}"
    
    if [ -f "srt_to_video_v2.5.sh" ]; then
        chmod +x srt_to_video_v2.5.sh
        echo -e "${GREEN}✓ srt_to_video_v2.5.sh ahora es ejecutable${NC}"
    fi
    
    if [ -f "generate_tts.py" ]; then
        chmod +x generate_tts.py
        echo -e "${GREEN}✓ generate_tts.py ahora es ejecutable${NC}"
    fi
}

# Verificar instalación
verify_installation() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Verificando instalación...${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    
    ALL_OK=true
    
    # Verificar FFmpeg
    if command_exists ffmpeg; then
        FFMPEG_VERSION=$(ffmpeg -version | head -n1)
        echo -e "${GREEN}✓ FFmpeg: $FFMPEG_VERSION${NC}"
    else
        echo -e "${RED}✗ FFmpeg no encontrado${NC}"
        ALL_OK=false
    fi
    
    # Verificar BC
    if command_exists bc; then
        echo -e "${GREEN}✓ BC: Instalado${NC}"
    else
        echo -e "${RED}✗ BC no encontrado${NC}"
        ALL_OK=false
    fi
    
    # Verificar según sistema
    if [ "$OS" = "macos" ]; then
        if command_exists say; then
            echo -e "${GREEN}✓ Comando 'say': Disponible${NC}"
        else
            echo -e "${RED}✗ Comando 'say' no encontrado${NC}"
            ALL_OK=false
        fi
        
        # Verificar bash2
        if command_exists bash2 || [ -f "$HOME/.local/bin/bash2" ]; then
            BASH2_VERSION=$(bash2 --version 2>/dev/null | head -n1 || echo "Disponible")
            echo -e "${GREEN}✓ bash2: $BASH2_VERSION${NC}"
        fi
    else
        # Verificar Python
        if command_exists python3 || command_exists python; then
            if command_exists python3; then
                PYTHON_VERSION=$(python3 --version)
            else
                PYTHON_VERSION=$(python --version)
            fi
            echo -e "${GREEN}✓ Python: $PYTHON_VERSION${NC}"
        else
            echo -e "${RED}✗ Python no encontrado${NC}"
            ALL_OK=false
        fi
        
        # Verificar paquetes Python
        if python3 -c "import gtts" 2>/dev/null || python -c "import gtts" 2>/dev/null; then
            echo -e "${GREEN}✓ gTTS: Instalado${NC}"
        else
            echo -e "${RED}✗ gTTS no encontrado${NC}"
            ALL_OK=false
        fi
        
        if python3 -c "import pydub" 2>/dev/null || python -c "import pydub" 2>/dev/null; then
            echo -e "${GREEN}✓ pydub: Instalado${NC}"
        else
            echo -e "${RED}✗ pydub no encontrado${NC}"
            ALL_OK=false
        fi
    fi
    
    echo ""
    if [ "$ALL_OK" = true ]; then
        echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ Instalación completada exitosamente${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
        return 0
    else
        echo -e "${RED}═══════════════════════════════════════════════════${NC}"
        echo -e "${RED}⚠️  Instalación completada con advertencias${NC}"
        echo -e "${RED}═══════════════════════════════════════════════════${NC}"
        return 1
    fi
}

# Mostrar instrucciones finales
show_final_instructions() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}¡Listo para usar!${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    
    if [ "$OS" = "macos" ]; then
        echo -e "${YELLOW}Para macOS, recuerda recargar tu shell:${NC}"
        echo -e "${BLUE}  source ~/.zshrc${NC}  (o ~/.bash_profile si usas Bash)"
        echo ""
        echo -e "${YELLOW}Ejemplo de uso con Bash moderno:${NC}"
        echo -e "${BLUE}  bash2 srt_to_video_v2.5.sh subtitulos.srt video.mp4${NC}"
        echo ""
        echo -e "${YELLOW}O usa directamente:${NC}"
        echo -e "${BLUE}  ./srt_to_video_v2.5.sh subtitulos.srt video.mp4${NC}"
    else
        echo -e "${YELLOW}Ejemplo de uso:${NC}"
        echo -e "${BLUE}  ./srt_to_video_v2.5.sh subtitulos.srt video.mp4${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}Ver más opciones:${NC}"
    echo -e "${BLUE}  ./srt_to_video_v2.5.sh --help${NC}"
    echo ""
    echo -e "${YELLOW}Documentación completa:${NC}"
    echo -e "${BLUE}  cat README.md${NC}"
    echo ""
}

# Main
main() {
    detect_os
    
    case $OS in
        macos)
            install_macos
            ;;
        linux)
            install_linux
            ;;
        windows)
            install_windows
            ;;
    esac
    
    make_executable
    verify_installation
    show_final_instructions
}

# Ejecutar instalación
main