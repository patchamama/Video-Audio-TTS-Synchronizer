#!/bin/bash

# Script v2.3 para generar audio TTS con ajuste automático de velocidad
# Congela frames solo cuando es necesario
# NUEVO: Genera archivo SRT debug con tiempos recalculados y rate info
# NUEVO: Modo --solo-audio para generar audio sin freezes
# Uso: ./srt_to_video_v2.3.sh [archivo.srt] [video] [carpeta_audios_opcional] [--test] [--solo-audio]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Función para mostrar uso
usage() {
    echo "Uso: $0 [archivo.srt] [video] [carpeta_audios_opcional] [--test[=N]] [--solo-audio]"
    echo ""
    echo "Parámetros:"
    echo "  archivo.srt              - Archivo de subtítulos"
    echo "  video                    - Nombre del video"
    echo "  carpeta_audios_opcional  - Carpeta con audios ya generados"
    echo "  --test                   - Modo test: 30 subtítulos (por defecto)"
    echo "  --test=N                 - Modo test: N subtítulos"
    echo "  --solo-audio             - Solo genera audio, sin freezes, sin video"
    echo ""
    echo "Ejemplos:"
    echo "  $0 subtitulos.srt video.mp4"
    echo "  $0 subtitulos.srt video.mp4 --test"
    echo "  $0 subtitulos.srt video.mp4 --test=100"
    echo "  $0 subtitulos.srt video.mp4 --solo-audio"
    echo "  $0 subtitulos.srt video.mp4 temp_audio_12345 --test=50"
    exit 1
}

# Función para convertir tiempo SRT a segundos
srt_time_to_seconds() {
    local time=$1
    local hours minutes seconds milliseconds
    IFS=':,' read -r hours minutes seconds milliseconds <<< "$time"
    
    hours=$(echo "$hours" | tr -d ' ' | sed 's/^0*\([0-9]\)/\1/; s/^$/0/')
    minutes=$(echo "$minutes" | tr -d ' ' | sed 's/^0*\([0-9]\)/\1/; s/^$/0/')
    seconds=$(echo "$seconds" | tr -d ' ' | sed 's/^0*\([0-9]\)/\1/; s/^$/0/')
    milliseconds=$(echo "$milliseconds" | tr -d ' ' | sed 's/^0*\([0-9]\)/\1/; s/^$/0/')
    
    [[ ! "$hours" =~ ^[0-9]+$ ]] && hours=0
    [[ ! "$minutes" =~ ^[0-9]+$ ]] && minutes=0
    [[ ! "$seconds" =~ ^[0-9]+$ ]] && seconds=0
    [[ ! "$milliseconds" =~ ^[0-9]+$ ]] && milliseconds=0
    
    echo "scale=3; $hours * 3600 + $minutes * 60 + $seconds + $milliseconds / 1000" | bc
}

# Función para convertir segundos a tiempo SRT
seconds_to_srt_time() {
    local total_seconds=$1
    
    # Asegurar que tenemos un número válido
    if [ -z "$total_seconds" ] || [ "$total_seconds" = "0" ]; then
        echo "00:00:00,000"
        return
    fi
    
    # Usar awk para cálculos más robustos
    awk -v ts="$total_seconds" 'BEGIN {
        hours = int(ts / 3600)
        remainder = ts - (hours * 3600)
        minutes = int(remainder / 60)
        seconds = remainder - (minutes * 60)
        seconds_int = int(seconds)
        milliseconds = int((seconds - seconds_int) * 1000)
        printf "%02d:%02d:%02d,%03d\n", hours, minutes, seconds_int, milliseconds
    }'
}

# Función para obtener duración
get_duration() {
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null
}

# Función para crear silencio
create_silence() {
    local duration=$1
    local output=$2
    ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t "$duration" -q:a 9 -acodec pcm_s16le "$output" -y &>/dev/null
}

# Función para generar audio TTS con rate específico
generate_audio_with_rate() {
    local text=$1
    local rate=$2
    local output=$3
    
    say -v Paulina -r "$rate" "$text" -o "${output%.wav}.aiff" 2>/dev/null
    ffmpeg -i "${output%.wav}.aiff" "$output" -y &>/dev/null
    rm "${output%.wav}.aiff"
}

# Parsear argumentos
AUDIO_DIR=""
TEST_MODE=false
TEST_LIMIT=30
SOLO_AUDIO=false

for arg in "$@"; do
    if [ "$arg" = "--test" ]; then
        TEST_MODE=true
    elif [[ "$arg" =~ ^--test[[:space:]]+([0-9]+)$ ]]; then
        TEST_MODE=true
        TEST_LIMIT="${BASH_REMATCH[1]}"
    elif [[ "$arg" =~ ^--test=([0-9]+)$ ]]; then
        TEST_MODE=true
        TEST_LIMIT="${BASH_REMATCH[1]}"
    elif [ "$arg" = "--solo-audio" ]; then
        SOLO_AUDIO=true
    fi
done

if [ $# -eq 0 ]; then
    read -p "Archivo SRT: " SRT_FILE
    read -p "Video: " VIDEO_NAME
    read -p "Carpeta audios (Enter para omitir): " AUDIO_DIR
    read -p "¿Modo test? (s/n o número): " test_response
    if [ "$test_response" = "s" ]; then
        TEST_MODE=true
        TEST_LIMIT=30
    elif [[ "$test_response" =~ ^[0-9]+$ ]]; then
        TEST_MODE=true
        TEST_LIMIT=$test_response
    fi
    read -p "¿Solo audio sin video? (s/n): " solo_audio_response
    if [ "$solo_audio_response" = "s" ]; then
        SOLO_AUDIO=true
    fi
elif [ $# -ge 2 ]; then
    SRT_FILE=$1
    VIDEO_NAME=$2
    
    # Procesar argumentos restantes
    shift 2
    for arg in "$@"; do
        if [ "$arg" = "--test" ]; then
            TEST_MODE=true
            TEST_LIMIT=30
        elif [[ "$arg" =~ ^--test=([0-9]+)$ ]]; then
            TEST_MODE=true
            TEST_LIMIT="${BASH_REMATCH[1]}"
        elif [ "$arg" = "--solo-audio" ]; then
            SOLO_AUDIO=true
        elif [[ "$arg" =~ ^[0-9]+$ ]] && [ "$TEST_MODE" = true ]; then
            TEST_LIMIT=$arg
        elif [ "$TEST_MODE" = false ] && [ "$SOLO_AUDIO" = false ]; then
            AUDIO_DIR=$arg
        fi
    done
else
    usage
fi

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}⚠️  MODO TEST: ${TEST_LIMIT} subtítulos${NC}"
fi

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${CYAN}🎵 MODO SOLO-AUDIO: No se generará video, solo audio sin freezes${NC}"
fi

# Verificar archivos
[ ! -f "$SRT_FILE" ] && echo -e "${RED}Error: No existe $SRT_FILE${NC}" && exit 1

VIDEO_FILE=""
for ext in .mkv .mp4 ""; do
    if [ -f "${VIDEO_NAME}${ext}" ]; then
        VIDEO_FILE="${VIDEO_NAME}${ext}"
        break
    fi
done

[ -z "$VIDEO_FILE" ] && echo -e "${RED}Error: No se encuentra el video${NC}" && exit 1

echo -e "${GREEN}SRT: $SRT_FILE${NC}"
echo -e "${GREEN}Video: $VIDEO_FILE${NC}"

# Configurar carpeta temporal
TEMP_DIR=""
SKIP_TTS=false

if [ -n "$AUDIO_DIR" ] && [ -d "$AUDIO_DIR" ]; then
    TEMP_DIR="$AUDIO_DIR"
    SKIP_TTS=true
    echo -e "${GREEN}Usando audios: $TEMP_DIR${NC}"
else
    TEMP_DIR="temp_audio_$$"
    mkdir -p "$TEMP_DIR"
    echo -e "${GREEN}Carpeta temporal: $TEMP_DIR${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📋 PASO 1: PARSEAR SUBTÍTULOS${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Parsear SRT
current_id=""
current_text=""
reading_text=false

declare -a subtitle_ids
declare -A subtitle_starts
declare -A subtitle_ends
declare -A subtitle_texts

while IFS= read -r line || [ -n "$line" ]; do
    if [[ $line =~ ^[0-9]+$ ]]; then
        current_id=$line
        reading_text=false
    elif [[ $line =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}\ --\>\ [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3} ]]; then
        IFS=' --> ' read -r start_time end_time <<< "$line"
        subtitle_starts[$current_id]=$start_time
        subtitle_ends[$current_id]=$end_time
        reading_text=true
        current_text=""
    elif [ -z "$line" ] && [ -n "$current_id" ]; then
        if [ -n "$current_text" ]; then
            subtitle_ids+=("$current_id")
            subtitle_texts[$current_id]=$current_text
        fi
        current_id=""
        current_text=""
        reading_text=false
    elif [ "$reading_text" = true ]; then
        if [ -z "$current_text" ]; then
            current_text=$line
        else
            current_text="$current_text $line"
        fi
    fi
done < "$SRT_FILE"

if [ -n "$current_id" ] && [ -n "$current_text" ]; then
    subtitle_ids+=("$current_id")
    subtitle_texts[$current_id]=$current_text
fi

echo -e "${GREEN}Total: ${#subtitle_ids[@]} subtítulos${NC}"

if [ "$TEST_MODE" = true ] && [ ${#subtitle_ids[@]} -gt $TEST_LIMIT ]; then
    echo -e "${YELLOW}Limitando a ${TEST_LIMIT} subtítulos${NC}"
    subtitle_ids=("${subtitle_ids[@]:0:$TEST_LIMIT}")
fi

echo -e "${GREEN}A procesar: ${#subtitle_ids[@]}${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎤 PASO 2: GENERAR AUDIOS CON AJUSTE INTELIGENTE${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Variables para aprendizaje del rate óptimo
declare -A rate_usage_count
rate_usage_count[180]=0
rate_usage_count[200]=0
rate_usage_count[220]=0
rate_usage_count[freeze]=0

optimal_rate=180  # Rate por defecto
learning_phase=true
processed_count=0

# Arrays para tracking de video segments y freeze info
declare -A needs_freeze
declare -A freeze_durations
declare -A audio_files
declare -A segment_starts
declare -A segment_durations
declare -A audio_rates  # NUEVO: Guardar el rate usado para cada audio

if [ "$SKIP_TTS" = false ]; then
    for idx in "${!subtitle_ids[@]}"; do
        id="${subtitle_ids[$idx]}"
        text="${subtitle_texts[$id]}"
        text=$(echo "$text" | sed 's/<[^>]*>//g')
        
        start_time="${subtitle_starts[$id]}"
        end_time="${subtitle_ends[$id]}"
        start_seconds=$(srt_time_to_seconds "$start_time")
        end_seconds=$(srt_time_to_seconds "$end_time")
        subtitle_duration=$(echo "$end_seconds - $start_seconds" | bc -l)
        
        # Calcular tiempo disponible hasta el siguiente subtítulo
        next_idx=$((idx + 1))
        if [ $next_idx -lt ${#subtitle_ids[@]} ]; then
            # Hay siguiente subtítulo
            next_id="${subtitle_ids[$next_idx]}"
            next_start_time="${subtitle_starts[$next_id]}"
            next_start_seconds=$(srt_time_to_seconds "$next_start_time")
            available_time=$(echo "$next_start_seconds - $start_seconds" | bc -l)
        else
            # Es el último, usar la duración del subtítulo
            available_time=$subtitle_duration
        fi
        
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Subtítulo $id${NC}"
        echo -e "${YELLOW}  Texto: ${text:0:50}...${NC}"
        echo -e "${BLUE}  Duración subtítulo: ${subtitle_duration}s${NC}"
        echo -e "${BLUE}  Tiempo disponible hasta siguiente: ${available_time}s${NC}"
        
        # Determinar rate inicial basado en fase de aprendizaje
        if [ "$learning_phase" = false ]; then
            current_rate=$optimal_rate
            echo -e "${MAGENTA}🎯 Usando rate aprendido: $current_rate wpm${NC}"
        else
            current_rate=180
        fi
        
        # Intentar con diferentes rates
        audio_created=false
        final_rate=$current_rate
        
        # En modo solo-audio, siempre intentar ajustar sin freeze
        if [ "$SOLO_AUDIO" = true ]; then
            for try_rate in $current_rate 200 220 240 260 280 300; do
                temp_audio="$TEMP_DIR/${id}_temp.wav"
                
                echo -e "  ${BLUE}Probando rate $try_rate wpm...${NC}"
                generate_audio_with_rate "$text" "$try_rate" "$temp_audio"
                
                if [ ! -f "$temp_audio" ]; then
                    echo -e "  ${RED}Error generando audio${NC}"
                    continue
                fi
                
                audio_duration=$(get_duration "$temp_audio")
                diff=$(echo "$audio_duration - $available_time" | bc -l)
                
                echo -e "  ${BLUE}→ Duración: ${audio_duration}s (diff: ${diff}s)${NC}"
                
                # Si cabe con margen de 0.5s en el tiempo disponible, usar este rate
                if (( $(echo "$diff < 0.5" | bc -l) )); then
                    mv "$temp_audio" "$TEMP_DIR/$id.wav"
                    audio_created=true
                    final_rate=$try_rate
                    rate_usage_count[$try_rate]=$((${rate_usage_count[$try_rate]} + 1))
                    echo -e "  ${GREEN}✅ Audio ajustado con rate $try_rate${NC}"
                    
                    needs_freeze[$id]=false
                    audio_files[$id]="$TEMP_DIR/$id.wav"
                    audio_rates[$id]=$try_rate
                    segment_starts[$id]=$start_seconds
                    segment_durations[$id]=$subtitle_duration
                    
                    break
                else
                    rm "$temp_audio"
                fi
            done
            
            # Si ningún rate funcionó en modo solo-audio, usar el más rápido posible
            if [ "$audio_created" = false ]; then
                echo -e "  ${YELLOW}⚠️  Usando rate máximo 300 wpm${NC}"
                generate_audio_with_rate "$text" "300" "$TEMP_DIR/$id.wav"
                
                needs_freeze[$id]=false
                audio_files[$id]="$TEMP_DIR/$id.wav"
                audio_rates[$id]=300
                segment_starts[$id]=$start_seconds
                segment_durations[$id]=$subtitle_duration
                
                rate_usage_count[300]=$((${rate_usage_count[300]} + 1))
                echo -e "  ${GREEN}✅ Audio creado con rate 300${NC}"
            fi
        else
            # Modo normal con posibilidad de freeze
            for try_rate in $current_rate 200 220; do
                temp_audio="$TEMP_DIR/${id}_temp.wav"
                
                echo -e "  ${BLUE}Probando rate $try_rate wpm...${NC}"
                generate_audio_with_rate "$text" "$try_rate" "$temp_audio"
                
                if [ ! -f "$temp_audio" ]; then
                    echo -e "  ${RED}Error generando audio${NC}"
                    continue
                fi
                
                audio_duration=$(get_duration "$temp_audio")
                diff=$(echo "$audio_duration - $available_time" | bc -l)
                
                echo -e "  ${BLUE}→ Duración: ${audio_duration}s (diff: ${diff}s)${NC}"
                
                # Si cabe con margen de 0.5s en el tiempo disponible, usar este rate
                if (( $(echo "$diff < 0.5" | bc -l) )); then
                    mv "$temp_audio" "$TEMP_DIR/$id.wav"
                    audio_created=true
                    final_rate=$try_rate
                    rate_usage_count[$try_rate]=$((${rate_usage_count[$try_rate]} + 1))
                    echo -e "  ${GREEN}✅ Audio ajustado con rate $try_rate${NC}"
                    
                    needs_freeze[$id]=false
                    audio_files[$id]="$TEMP_DIR/$id.wav"
                    audio_rates[$id]=$try_rate
                    segment_starts[$id]=$start_seconds
                    segment_durations[$id]=$subtitle_duration
                    
                    break
                else
                    rm "$temp_audio"
                fi
            done
            
            # Si ningún rate funcionó, usar rate 220 y marcar para freeze
            if [ "$audio_created" = false ]; then
                echo -e "  ${YELLOW}⚠️  Audio muy largo, generando con rate 220 y marcando para freeze${NC}"
                generate_audio_with_rate "$text" "220" "$TEMP_DIR/$id.wav"
                
                audio_duration=$(get_duration "$TEMP_DIR/$id.wav")
                freeze_time=$(echo "$audio_duration - $available_time" | bc -l | awk '{printf "%.6f", $0}')
                
                needs_freeze[$id]=true
                freeze_durations[$id]=$freeze_time
                audio_files[$id]="$TEMP_DIR/$id.wav"
                audio_rates[$id]=220
                segment_starts[$id]=$start_seconds
                segment_durations[$id]=$subtitle_duration
                
                rate_usage_count[freeze]=$((${rate_usage_count[freeze]} + 1))
                
                echo -e "  ${RED}🎬 Requerirá freeze de ${freeze_time}s${NC}"
            fi
        fi
        
        processed_count=$((processed_count + 1))
        
        # Después de 50 subtítulos, determinar rate óptimo
        if [ $processed_count -eq 50 ] && [ "$learning_phase" = true ]; then
            echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${MAGENTA}📊 ANÁLISIS DE APRENDIZAJE (50 subtítulos)${NC}"
            echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${MAGENTA}Rate 180 wpm: ${rate_usage_count[180]} veces${NC}"
            echo -e "${MAGENTA}Rate 200 wpm: ${rate_usage_count[200]} veces${NC}"
            echo -e "${MAGENTA}Rate 220 wpm: ${rate_usage_count[220]} veces${NC}"
            echo -e "${MAGENTA}Freeze necesario: ${rate_usage_count[freeze]} veces${NC}"
            
            # Determinar rate más usado (excluyendo freeze)
            max_count=0
            for rate in 180 200 220; do
                if [ ${rate_usage_count[$rate]} -gt $max_count ]; then
                    max_count=${rate_usage_count[$rate]}
                    optimal_rate=$rate
                fi
            done
            
            learning_phase=false
            echo -e "${GREEN}🎯 Rate óptimo determinado: $optimal_rate wpm${NC}"
            echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        fi
    done
    
    echo -e "${GREEN}✅ Audios generados${NC}"
else
    echo -e "${GREEN}Usando audios existentes${NC}"
    # Cargar info de audios existentes
    for idx in "${!subtitle_ids[@]}"; do
        id="${subtitle_ids[$idx]}"
        if [ ! -f "$TEMP_DIR/$id.wav" ]; then
            echo -e "${RED}Error: Falta $TEMP_DIR/$id.wav${NC}"
            exit 1
        fi
        
        start_time="${subtitle_starts[$id]}"
        end_time="${subtitle_ends[$id]}"
        start_seconds=$(srt_time_to_seconds "$start_time")
        end_seconds=$(srt_time_to_seconds "$end_time")
        subtitle_duration=$(echo "$end_seconds - $start_seconds" | bc -l)
        
        # Calcular tiempo disponible hasta el siguiente subtítulo
        next_idx=$((idx + 1))
        if [ $next_idx -lt ${#subtitle_ids[@]} ]; then
            next_id="${subtitle_ids[$next_idx]}"
            next_start_time="${subtitle_starts[$next_id]}"
            next_start_seconds=$(srt_time_to_seconds "$next_start_time")
            available_time=$(echo "$next_start_seconds - $start_seconds" | bc -l)
        else
            available_time=$subtitle_duration
        fi
        
        audio_duration=$(get_duration "$TEMP_DIR/$id.wav")
        
        audio_files[$id]="$TEMP_DIR/$id.wav"
        segment_starts[$id]=$start_seconds
        segment_durations[$id]=$subtitle_duration
        
        # Detectar rate usado (intentar obtener del nombre si existe, sino 180 por defecto)
        if [ ! -v audio_rates[$id] ]; then
            audio_rates[$id]=180
        fi
        
        # Verificar si necesita freeze comparando con tiempo disponible
        diff=$(echo "$audio_duration - $available_time" | bc -l)
        if (( $(echo "$diff > 0.5" | bc -l) )) && [ "$SOLO_AUDIO" = false ]; then
            needs_freeze[$id]=true
            freeze_durations[$id]=$(echo "$diff" | awk '{printf "%.6f", $0}')
            echo -e "${YELLOW}Subtítulo $id necesitará freeze de ${freeze_durations[$id]}s${NC}"
        else
            needs_freeze[$id]=false
        fi
    done
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 RESUMEN DE PROCESAMIENTO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

freeze_count=0
for id in "${subtitle_ids[@]}"; do
    if [ "${needs_freeze[$id]}" = true ]; then
        freeze_count=$((freeze_count + 1))
    fi
done

echo -e "${GREEN}Total subtítulos: ${#subtitle_ids[@]}${NC}"
echo -e "${YELLOW}Requieren freeze: $freeze_count${NC}"
echo -e "${GREEN}Sin freeze: $((${#subtitle_ids[@]} - freeze_count))${NC}"

if [ $freeze_count -gt 0 ]; then
    echo -e "${YELLOW}Los siguientes subtítulos requieren freeze:${NC}"
    for id in "${subtitle_ids[@]}"; do
        if [ "${needs_freeze[$id]}" = true ]; then
            echo -e "  ${YELLOW}• Subtítulo $id: +${freeze_durations[$id]}s${NC}"
        fi
    done
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📝 PASO 3: GENERAR SRT DEBUG${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Generar archivo SRT debug con tiempos recalculados
DEBUG_SRT="${VIDEO_NAME%.*}_debug.srt"
echo -e "${CYAN}Generando archivo SRT debug: $DEBUG_SRT${NC}"

# Variable para acumular el offset de tiempo
time_offset=0

> "$DEBUG_SRT"  # Crear archivo vacío

for idx in "${!subtitle_ids[@]}"; do
    id="${subtitle_ids[$idx]}"
    
    # Obtener tiempos originales
    start_time="${subtitle_starts[$id]}"
    end_time="${subtitle_ends[$id]}"
    start_seconds=$(srt_time_to_seconds "$start_time")
    end_seconds=$(srt_time_to_seconds "$end_time")
    
    # Aplicar offset acumulado
    new_start_seconds=$(echo "$start_seconds + $time_offset" | bc -l)
    new_end_seconds=$(echo "$end_seconds + $time_offset" | bc -l)
    
    # Convertir a formato SRT
    new_start_time=$(seconds_to_srt_time "$new_start_seconds")
    new_end_time=$(seconds_to_srt_time "$new_end_seconds")
    
    # Obtener texto original
    original_text="${subtitle_texts[$id]}"
    
    # Obtener rate usado
    rate="${audio_rates[$id]}"
    
    # Formatear el offset acumulado en milisegundos para mostrar
    offset_ms=$(echo "$time_offset * 1000" | bc -l | awk '{printf "%.0f", $0}')
    
    # Crear nuevo texto con número de subtítulo, rate y offset
    if [ "${needs_freeze[$id]}" = true ]; then
        freeze_dur="${freeze_durations[$id]}"
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            new_text="[#$id r$rate +${offset_ms}ms] [⏸️ FREEZE +${freeze_dur}s] $original_text"
        else
            new_text="[#$id r$rate] [⏸️ FREEZE +${freeze_dur}s] $original_text"
        fi
        
        # Agregar el tiempo de freeze al offset para los siguientes subtítulos
        time_offset=$(echo "$time_offset + $freeze_dur" | bc -l)
    else
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            new_text="[#$id r$rate +${offset_ms}ms] $original_text"
        else
            new_text="[#$id r$rate] $original_text"
        fi
    fi
    
    # Escribir subtítulo en formato SRT
    echo "$id" >> "$DEBUG_SRT"
    echo "$new_start_time --> $new_end_time" >> "$DEBUG_SRT"
    echo "$new_text" >> "$DEBUG_SRT"
    echo "" >> "$DEBUG_SRT"
    
    # Mostrar información
    if [ "${needs_freeze[$id]}" = true ]; then
        echo -e "${YELLOW}Subtítulo $id (CON FREEZE)${NC}"
        echo -e "  ${BLUE}Original: $start_time → $end_time${NC}"
        echo -e "  ${GREEN}Nuevo:    $new_start_time → $new_end_time${NC}"
        echo -e "  ${RED}Offset acumulado: +${time_offset}s${NC}"
    else
        echo -e "${GREEN}Subtítulo $id (sin freeze)${NC}"
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            echo -e "  ${BLUE}Original: $start_time → $end_time${NC}"
            echo -e "  ${GREEN}Nuevo:    $new_start_time → $new_end_time${NC}"
            echo -e "  ${YELLOW}Offset acumulado: +${time_offset}s${NC}"
        fi
    fi
done

echo -e "${GREEN}✅ Archivo SRT debug generado: $DEBUG_SRT${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Offset total acumulado: +${time_offset}s${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎬 PASO 4: PROCESAR VIDEO CON FREEZES${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Si modo solo-audio, saltar procesamiento de video
if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${CYAN}Modo solo-audio: Saltando procesamiento de video${NC}"
    VIDEO_TO_USE=""
else
    # Si hay freezes, necesitamos procesar el video segmento por segmento
    if [ $freeze_count -gt 0 ]; then
    echo -e "${YELLOW}Procesando video con congelamiento de frames...${NC}"
    
    # Obtener FPS
    FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null)
    FPS=$(echo "scale=2; $FPS" | bc -l 2>/dev/null || echo "30")
    echo -e "${GREEN}FPS del video: $FPS${NC}"
    
    VIDEO_SEGMENTS=()
    
    for id in "${subtitle_ids[@]}"; do
        start_sec="${segment_starts[$id]}"
        duration="${segment_durations[$id]}"
        
        echo -e "${YELLOW}Segmento $id (${start_sec}s, ${duration}s)${NC}"
        
        # Extraer segmento normal
        ffmpeg -i "$VIDEO_FILE" -ss "$start_sec" -t "$duration" \
            -c:v libx264 -preset ultrafast -an \
            "$TEMP_DIR/vseg_${id}.mkv" -y 2>&1 | tail -2
        
        if [ ! -f "$TEMP_DIR/vseg_${id}.mkv" ]; then
            echo -e "${RED}Error creando segmento${NC}"
            exit 1
        fi
        
        VIDEO_SEGMENTS+=("$TEMP_DIR/vseg_${id}.mkv")
        
        # Si necesita freeze, crear segmento congelado
        if [ "${needs_freeze[$id]}" = true ]; then
            freeze_dur="${freeze_durations[$id]}"
            end_sec=$(echo "$start_sec + $duration" | bc -l)
            
            echo -e "  ${YELLOW}+ Freeze: ${freeze_dur}s${NC}"
            
            # Extraer último frame del segmento (múltiples métodos)
            frame_extracted=false
            
            # Método 1: Desde el final del segmento recién creado
            if ffmpeg -sseof -0.1 -i "$TEMP_DIR/vseg_${id}.mkv" -frames:v 1 \
                "$TEMP_DIR/freeze_${id}.png" -y 2>&1 | tail -2; then
                if [ -f "$TEMP_DIR/freeze_${id}.png" ] && [ -s "$TEMP_DIR/freeze_${id}.png" ]; then
                    frame_extracted=true
                    echo -e "  ${GREEN}Frame extraído del segmento${NC}"
                fi
            fi
            
            # Método 2: Si falla, extraer del video original en ese timestamp
            if [ "$frame_extracted" = false ]; then
                echo -e "  ${YELLOW}Reintentando desde video original...${NC}"
                if ffmpeg -ss "$end_sec" -i "$VIDEO_FILE" -frames:v 1 \
                    "$TEMP_DIR/freeze_${id}.png" -y 2>&1 | tail -2; then
                    if [ -f "$TEMP_DIR/freeze_${id}.png" ] && [ -s "$TEMP_DIR/freeze_${id}.png" ]; then
                        frame_extracted=true
                        echo -e "  ${GREEN}Frame extraído del video original${NC}"
                    fi
                fi
            fi
            
            # Método 3: Si aún falla, usar el frame del medio del segmento
            if [ "$frame_extracted" = false ]; then
                echo -e "  ${YELLOW}Usando frame del medio del segmento...${NC}"
                mid_time=$(echo "$duration / 2" | bc -l)
                if ffmpeg -ss "$mid_time" -i "$TEMP_DIR/vseg_${id}.mkv" -frames:v 1 \
                    "$TEMP_DIR/freeze_${id}.png" -y 2>&1 | tail -2; then
                    if [ -f "$TEMP_DIR/freeze_${id}.png" ] && [ -s "$TEMP_DIR/freeze_${id}.png" ]; then
                        frame_extracted=true
                        echo -e "  ${GREEN}Frame del medio extraído${NC}"
                    fi
                fi
            fi
            
            if [ "$frame_extracted" = false ]; then
                echo -e "  ${RED}Error: No se pudo extraer frame para freeze${NC}"
                echo -e "  ${YELLOW}Omitiendo freeze para este subtítulo${NC}"
                continue
            fi
            
            # Crear video con frame congelado
            echo -e "  ${YELLOW}Creando video congelado...${NC}"
            if ffmpeg -loop 1 -i "$TEMP_DIR/freeze_${id}.png" -t "$freeze_dur" \
                -r "$FPS" -pix_fmt yuv420p -c:v libx264 -preset ultrafast \
                "$TEMP_DIR/vfreeze_${id}.mkv" -y 2>&1 | tail -2; then
                
                if [ -f "$TEMP_DIR/vfreeze_${id}.mkv" ] && [ -s "$TEMP_DIR/vfreeze_${id}.mkv" ]; then
                    VIDEO_SEGMENTS+=("$TEMP_DIR/vfreeze_${id}.mkv")
                    echo -e "  ${GREEN}Freeze creado exitosamente${NC}"
                else
                    echo -e "  ${RED}Error: Video freeze no creado${NC}"
                fi
            else
                echo -e "  ${RED}Error en ffmpeg al crear freeze${NC}"
            fi
        fi
    done
    
    # Concatenar segmentos de video
    echo -e "${YELLOW}Concatenando segmentos de video...${NC}"
    VIDEO_LIST="$TEMP_DIR/video_segments.txt"
    > "$VIDEO_LIST"
    
    for seg in "${VIDEO_SEGMENTS[@]}"; do
        echo "file '$(basename "$seg")'" >> "$VIDEO_LIST"
    done
    
    ffmpeg -f concat -safe 0 -i "$VIDEO_LIST" -c copy \
        "$TEMP_DIR/video_processed.mkv" -y 2>&1 | tail -3
    
    if [ ! -f "$TEMP_DIR/video_processed.mkv" ]; then
        echo -e "${RED}Error concatenando video${NC}"
        exit 1
    fi
    
    VIDEO_TO_USE="$TEMP_DIR/video_processed.mkv"
    
    processed_video_duration=$(get_duration "$VIDEO_TO_USE")
    echo -e "${GREEN}Video procesado: ${processed_video_duration}s${NC}"
else
    echo -e "${GREEN}No se requieren freezes, usando video original${NC}"
    VIDEO_TO_USE="$VIDEO_FILE"
fi
fi  # Fin del if SOLO_AUDIO

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎵 PASO 5: CONSTRUIR AUDIO SINCRONIZADO (SECUENCIAL)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Crear audio maestro vacío (silencio muy corto)
create_silence "0.001" "$TEMP_DIR/audio_master.wav"

current_master_duration=0

for idx in "${!subtitle_ids[@]}"; do
    id="${subtitle_ids[$idx]}"
    start_sec="${segment_starts[$id]}"
    audio_file="${audio_files[$id]}"
    
    audio_duration=$(get_duration "$audio_file")
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Procesando subtítulo $id (inicio esperado: ${start_sec}s)${NC}"
    echo -e "${BLUE}  Duración actual del master: ${current_master_duration}s${NC}"
    
    # Verificar duración real del master
    actual_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    echo -e "${BLUE}  Duración real del master: ${actual_master_duration}s${NC}"
    
    # Usar la duración real para cálculos
    current_master_duration=$actual_master_duration
    
    # Calcular gap necesario antes de este audio
    gap=$(echo "$start_sec - $current_master_duration" | bc -l | awk '{printf "%.6f", $0}')
    
    if (( $(echo "$gap > 0.01" | bc -l) )); then
        echo -e "  ${GREEN}→ Necesita silencio de ${gap}s antes del audio${NC}"
        
        # Crear silencio temporal
        create_silence "$gap" "$TEMP_DIR/gap_${id}.wav"
        
        # Concatenar: master + gap
        ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$TEMP_DIR/gap_${id}.wav" \
            -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
            -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
        
        mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
        rm "$TEMP_DIR/gap_${id}.wav"
        
        # Verificar duración después de agregar gap
        current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
        echo -e "  ${BLUE}  Duración después del gap: ${current_master_duration}s${NC}"
    elif (( $(echo "$gap < -0.01" | bc -l) )); then
        echo -e "  ${RED}⚠️  Advertencia: Audio se solapa por ${gap}s (master va adelantado)${NC}"
    fi
    
    # Agregar el audio del subtítulo
    echo -e "  ${GREEN}→ Agregando audio TTS (${audio_duration}s)${NC}"
    
    ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$audio_file" \
        -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
        -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
    
    mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
    
    # Verificar duración después de agregar audio
    current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    echo -e "  ${BLUE}  Duración después del audio: ${current_master_duration}s${NC}"
    
    # Calcular dónde DEBERÍA estar el master (inicio del siguiente subtítulo)
    next_idx=$((idx + 1))
    if [ $next_idx -lt ${#subtitle_ids[@]} ]; then
        # Hay siguiente subtítulo
        next_id="${subtitle_ids[$next_idx]}"
        next_start="${segment_starts[$next_id]}"
        expected_position=$next_start
    else
        # Es el último, calcular fin del subtítulo actual
        end_sec=$(echo "$start_sec + ${segment_durations[$id]}" | bc -l)
        expected_position=$end_sec
    fi
    
    # Calcular padding necesario hasta la posición esperada
    padding=$(echo "$expected_position - $current_master_duration" | bc -l | awk '{printf "%.6f", $0}')
    
    echo -e "  ${MAGENTA}  Posición actual: ${current_master_duration}s${NC}"
    echo -e "  ${MAGENTA}  Posición esperada: ${expected_position}s${NC}"
    
    if (( $(echo "$padding > 0.01" | bc -l) )); then
        echo -e "  ${GREEN}→ Agregando padding de ${padding}s hasta siguiente subtítulo${NC}"
        
        # Crear padding temporal
        create_silence "$padding" "$TEMP_DIR/padding_${id}.wav"
        
        # Concatenar: master + padding
        ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$TEMP_DIR/padding_${id}.wav" \
            -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
            -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
        
        mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
        rm "$TEMP_DIR/padding_${id}.wav"
        
        # Verificar duración final
        current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
        echo -e "  ${BLUE}  Duración después del padding: ${current_master_duration}s${NC}"
    elif (( $(echo "$padding < -0.01" | bc -l) )); then
        echo -e "  ${RED}⚠️  Audio sobrepasa posición esperada por ${padding}s${NC}"
    fi
    
    # Verificación final de sincronización
    final_diff=$(echo "$current_master_duration - $expected_position" | bc -l | awk '{printf "%.3f", ($0 < 0) ? -$0 : $0}')
    
    if (( $(echo "$final_diff < 0.05" | bc -l) )); then
        echo -e "  ${GREEN}✅ Sincronizado (diff: ${final_diff}s)${NC}"
    else
        echo -e "  ${RED}❌ Desincronizado (diff: ${final_diff}s)${NC}"
    fi
done

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Renombrar master a final
mv "$TEMP_DIR/audio_master.wav" "$TEMP_DIR/audio_final.wav"

actual_audio_duration=$(get_duration "$TEMP_DIR/audio_final.wav")
echo -e "${GREEN}Audio final creado: ${actual_audio_duration}s${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎵 PASO 6: VERIFICAR AUDIO FINAL${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ ! -f "$TEMP_DIR/audio_final.wav" ]; then
    echo -e "${RED}Error: No se creó audio final${NC}"
    exit 1
fi

# Verificar que el archivo no está vacío
audio_size=$(stat -f%z "$TEMP_DIR/audio_final.wav" 2>/dev/null || stat -c%s "$TEMP_DIR/audio_final.wav" 2>/dev/null)
if [ "$audio_size" -lt 1000 ]; then
    echo -e "${RED}Error: Audio final vacío (${audio_size} bytes)${NC}"
    exit 1
fi

actual_audio_duration=$(get_duration "$TEMP_DIR/audio_final.wav")

if [ -z "$actual_audio_duration" ] || [ "$actual_audio_duration" = "N/A" ]; then
    echo -e "${RED}Error: No se pudo obtener duración del audio final${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Audio final verificado: ${actual_audio_duration}s (${audio_size} bytes)${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎞️  PASO 7: FUSIONAR VIDEO Y AUDIO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${CYAN}Modo solo-audio: Guardando audio final${NC}"
    
    OUTPUT_AUDIO="${VIDEO_NAME%.*}_tts_audio.wav"
    cp "$TEMP_DIR/audio_final.wav" "$OUTPUT_AUDIO"
    
    echo -e "${GREEN}✅ Audio generado: $OUTPUT_AUDIO${NC}"
    
    # Convertir también a AAC para uso directo
    OUTPUT_AUDIO_AAC="${VIDEO_NAME%.*}_tts_audio.aac"
    ffmpeg -i "$OUTPUT_AUDIO" -c:a aac -b:a 192k "$OUTPUT_AUDIO_AAC" -y 2>&1 | tail -3
    
    if [ -f "$OUTPUT_AUDIO_AAC" ]; then
        echo -e "${GREEN}✅ Audio AAC generado: $OUTPUT_AUDIO_AAC${NC}"
    fi
    
else
    # Modo normal: fusionar video y audio
    OUTPUT_VIDEO="${VIDEO_NAME%.*}_con_tts.mkv"

    echo -e "${YELLOW}Fusionando video con audio TTS...${NC}"
    echo -e "${YELLOW}Video fuente: $VIDEO_TO_USE${NC}"
    echo -e "${YELLOW}Audio fuente: $TEMP_DIR/audio_final.wav${NC}"

    # Verificar que los archivos existen
    if [ ! -f "$VIDEO_TO_USE" ]; then
        echo -e "${RED}Error: No existe video fuente${NC}"
        exit 1
    fi

    if [ ! -f "$TEMP_DIR/audio_final.wav" ]; then
        echo -e "${RED}Error: No existe audio final${NC}"
        exit 1
    fi

    # Usar map para asegurar que reemplazamos el audio correctamente
    # -map 0:v toma el video del primer input
    # -map 1:a toma el audio del segundo input
    # -shortest trunca al más corto
    ffmpeg -i "$VIDEO_TO_USE" -i "$TEMP_DIR/audio_final.wav" \
        -map 0:v:0 -map 1:a:0 \
        -c:v copy -c:a aac -b:a 192k \
        -shortest \
        "$OUTPUT_VIDEO" -y 2>&1 | tee "$TEMP_DIR/ffmpeg_merge.log" | tail -10

    if [ ! -f "$OUTPUT_VIDEO" ]; then
        echo -e "${RED}Error creando video final${NC}"
        echo -e "${YELLOW}Ver log completo: $TEMP_DIR/ffmpeg_merge.log${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Video creado: $OUTPUT_VIDEO${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}✅ PASO 8: VERIFICACIÓN FINAL${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    # Verificación para modo solo-audio
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}📊 REPORTE FINAL - MODO SOLO-AUDIO${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    
    audio_duration=$(get_duration "$OUTPUT_AUDIO")
    audio_size=$(stat -f%z "$OUTPUT_AUDIO" 2>/dev/null || stat -c%s "$OUTPUT_AUDIO" 2>/dev/null)
    
    echo -e "${YELLOW}Audio generado: ${audio_duration}s (${audio_size} bytes)${NC}"
    echo -e "${GREEN}✅ Formato WAV: $OUTPUT_AUDIO${NC}"
    
    if [ -f "$OUTPUT_AUDIO_AAC" ]; then
        aac_size=$(stat -f%z "$OUTPUT_AUDIO_AAC" 2>/dev/null || stat -c%s "$OUTPUT_AUDIO_AAC" 2>/dev/null)
        echo -e "${GREEN}✅ Formato AAC: $OUTPUT_AUDIO_AAC (${aac_size} bytes)${NC}"
    fi
    
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}📝 COMANDO PARA AGREGAR AUDIO AL VIDEO:${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}# Opción 1: Agregar como pista de audio adicional (mantiene audio original)${NC}"
    echo -e "${YELLOW}ffmpeg -i \"$VIDEO_FILE\" -i \"$OUTPUT_AUDIO_AAC\" \\${NC}"
    echo -e "${YELLOW}  -map 0:v -map 0:a -map 1:a \\${NC}"
    echo -e "${YELLOW}  -c:v copy -c:a copy \\${NC}"
    echo -e "${YELLOW}  -metadata:s:a:0 language=spa -metadata:s:a:0 title=\"Audio Original\" \\${NC}"
    echo -e "${YELLOW}  -metadata:s:a:1 language=spa -metadata:s:a:1 title=\"Audio TTS\" \\${NC}"
    echo -e "${YELLOW}  \"${VIDEO_NAME%.*}_dual_audio.mkv\"${NC}"
    echo ""
    echo -e "${GREEN}# Opción 2: Reemplazar audio original con TTS${NC}"
    echo -e "${YELLOW}ffmpeg -i \"$VIDEO_FILE\" -i \"$OUTPUT_AUDIO_AAC\" \\${NC}"
    echo -e "${YELLOW}  -map 0:v -map 1:a \\${NC}"
    echo -e "${YELLOW}  -c:v copy -c:a copy \\${NC}"
    echo -e "${YELLOW}  -shortest \\${NC}"
    echo -e "${YELLOW}  \"${VIDEO_NAME%.*}_solo_tts.mkv\"${NC}"
    echo ""
    echo -e "${GREEN}# Opción 3: Audio TTS como default, pero mantener original${NC}"
    echo -e "${YELLOW}ffmpeg -i \"$VIDEO_FILE\" -i \"$OUTPUT_AUDIO_AAC\" \\${NC}"
    echo -e "${YELLOW}  -map 0:v -map 1:a -map 0:a \\${NC}"
    echo -e "${YELLOW}  -c:v copy -c:a copy \\${NC}"
    echo -e "${YELLOW}  -disposition:a:0 default -disposition:a:1 0 \\${NC}"
    echo -e "${YELLOW}  -metadata:s:a:0 language=spa -metadata:s:a:0 title=\"Audio TTS\" \\${NC}"
    echo -e "${YELLOW}  -metadata:s:a:1 language=spa -metadata:s:a:1 title=\"Audio Original\" \\${NC}"
    echo -e "${YELLOW}  \"${VIDEO_NAME%.*}_tts_default.mkv\"${NC}"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    
else
    # Verificación para modo normal con video
echo -e "${YELLOW}Analizando streams del video final...${NC}"

# Método 1: Obtener duración del stream de audio
final_audio_in_video=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO" 2>/dev/null)

# Método 2: Si el método 1 falla, usar format duration
if [ -z "$final_audio_in_video" ] || [ "$final_audio_in_video" = "N/A" ]; then
    echo -e "${YELLOW}Stream duration no disponible, intentando con packet analysis...${NC}"
    final_audio_in_video=$(ffprobe -v error -select_streams a:0 -show_entries packet=pts_time -of csv=p=0 "$OUTPUT_VIDEO" 2>/dev/null | tail -1)
fi

# Método 3: Verificar si hay stream de audio presente
audio_stream_count=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUTPUT_VIDEO" 2>/dev/null | wc -l | tr -d ' ')
audio_codec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO" 2>/dev/null)

final_video_duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO" 2>/dev/null)

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}📊 REPORTE FINAL${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Video final: ${final_video_duration}s${NC}"
echo -e "${YELLOW}Streams de audio: ${audio_stream_count}${NC}"
echo -e "${YELLOW}Codec de audio: ${audio_codec:-NINGUNO}${NC}"

# Verificar si existe audio
if [ "$audio_stream_count" -eq 0 ] || [ -z "$audio_codec" ]; then
    echo -e "${RED}❌ ERROR CRÍTICO: No hay audio en el video final${NC}"
    echo -e "${YELLOW}Posibles causas:${NC}"
    echo -e "${YELLOW}  1. Problema con el codec del video original${NC}"
    echo -e "${YELLOW}  2. Audio final corrupto${NC}"
    echo -e "${YELLOW}  3. Error en el comando ffmpeg de fusión${NC}"
    echo -e "${YELLOW}Archivos para debug:${NC}"
    echo -e "${YELLOW}  - Video procesado: $VIDEO_TO_USE${NC}"
    echo -e "${YELLOW}  - Audio final: $TEMP_DIR/audio_final.wav${NC}"
    echo -e "${YELLOW}  - Logs: $TEMP_DIR/ffmpeg_*.log${NC}"
    
    # Intentar método alternativo
    echo ""
    echo -e "${YELLOW}Intentando método alternativo con re-encoding...${NC}"
    OUTPUT_VIDEO_ALT="${VIDEO_NAME%.*}_con_tts_alt.mkv"
    
    ffmpeg -i "$VIDEO_TO_USE" -i "$TEMP_DIR/audio_final.wav" \
        -map 0:v:0 -map 1:a:0 \
        -c:v libx264 -preset ultrafast -crf 18 \
        -c:a aac -b:a 192k \
        -shortest \
        "$OUTPUT_VIDEO_ALT" -y 2>&1 | tee "$TEMP_DIR/ffmpeg_merge_alt.log" | tail -10
    
    if [ -f "$OUTPUT_VIDEO_ALT" ]; then
        # Verificar si ahora tiene audio
        alt_audio_count=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUTPUT_VIDEO_ALT" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$alt_audio_count" -gt 0 ]; then
            mv "$OUTPUT_VIDEO_ALT" "$OUTPUT_VIDEO"
            echo -e "${GREEN}✅ Video creado exitosamente con método alternativo${NC}"
            
            # Re-verificar
            final_audio_in_video=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO" 2>/dev/null)
            audio_codec=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_VIDEO" 2>/dev/null)
            echo -e "${YELLOW}Audio en video: ${final_audio_in_video}s${NC}"
            echo -e "${YELLOW}Codec: ${audio_codec}${NC}"
        else
            echo -e "${RED}❌ Método alternativo también falló${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ No se pudo crear video con método alternativo${NC}"
        exit 1
    fi
else
    # Hay audio, reportar duración
    if [ -n "$final_audio_in_video" ] && [ "$final_audio_in_video" != "N/A" ]; then
        echo -e "${YELLOW}Audio en video: ${final_audio_in_video}s${NC}"
        
        sync_diff=$(echo "$final_video_duration - $final_audio_in_video" | bc -l | awk '{printf "%.3f", ($0 < 0) ? -$0 : $0}')

        if (( $(echo "$sync_diff < 0.1" | bc -l) )); then
            echo -e "${GREEN}✅ Sincronización perfecta (${sync_diff}s)${NC}"
        elif (( $(echo "$sync_diff < 0.5" | bc -l) )); then
            echo -e "${YELLOW}✅ Sincronización aceptable (${sync_diff}s)${NC}"
        else
            echo -e "${RED}⚠️  Diferencia notable (${sync_diff}s)${NC}"
        fi
    else
        echo -e "${GREEN}✅ Audio presente (duración no disponible en metadata)${NC}"
        echo -e "${YELLOW}Reproducir el video para verificar que el audio funciona${NC}"
    fi
fi  # Fin de if SOLO_AUDIO en verificación final
fi  # Fin de verificación de audio en video

# Generar reporte de freezes para testing
if [ $freeze_count -gt 0 ] && [ "$SOLO_AUDIO" = false ]; then
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}🎬 REPORTE DE FREEZES (para testing)${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Total de freezes: $freeze_count${NC}"
    echo ""
    
    accumulated_time=0
    
    for id in "${subtitle_ids[@]}"; do
        start_sec="${segment_starts[$id]}"
        duration="${segment_durations[$id]}"
        audio_duration=$(get_duration "${audio_files[$id]}")
        
        # Calcular timestamp en video final
        video_timestamp=$accumulated_time
        
        if [ "${needs_freeze[$id]}" = true ]; then
            freeze_dur="${freeze_durations[$id]}"
            freeze_start=$(echo "$video_timestamp + $duration" | bc -l | awk '{printf "%.2f", $0}')
            freeze_end=$(echo "$freeze_start + $freeze_dur" | bc -l | awk '{printf "%.2f", $0}')
            
            # Convertir a formato MM:SS
            freeze_start_min=$(echo "$freeze_start / 60" | bc)
            freeze_start_sec=$(echo "$freeze_start % 60" | bc -l | awk '{printf "%05.2f", $0}')
            freeze_end_min=$(echo "$freeze_end / 60" | bc)
            freeze_end_sec=$(echo "$freeze_end % 60" | bc -l | awk '{printf "%05.2f", $0}')
            
            echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${YELLOW}Subtítulo $id:${NC}"
            echo -e "${YELLOW}  Texto: ${subtitle_texts[$id]:0:60}...${NC}"
            echo -e "${GREEN}  Tiempo SRT: ${subtitle_starts[$id]} → ${subtitle_ends[$id]}${NC}"
            echo -e "${MAGENTA}  Freeze en video final:${NC}"
            echo -e "${MAGENTA}    • Inicio: ${freeze_start_min}:${freeze_start_sec} (${freeze_start}s)${NC}"
            echo -e "${MAGENTA}    • Fin: ${freeze_end_min}:${freeze_end_sec} (${freeze_end}s)${NC}"
            echo -e "${MAGENTA}    • Duración freeze: ${freeze_dur}s${NC}"
            echo -e "${BLUE}  🎥 Para probar: Ir a ${freeze_start_min}:${freeze_start_sec} en el video${NC}"
            
            accumulated_time=$(echo "$accumulated_time + $duration + $freeze_dur" | bc -l)
        else
            accumulated_time=$(echo "$accumulated_time + $audio_duration" | bc -l)
        fi
    done
    
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}💡 TIP: Usa VLC o cualquier reproductor para ir a estos timestamps${NC}"
    echo -e "${GREEN}    y verificar que el frame se congela correctamente.${NC}"
else
    echo ""
    echo -e "${GREEN}✅ No se requirieron freezes - todos los audios cupieron ajustando velocidad${NC}"
fi

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}�� ARCHIVOS GENERADOS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${GREEN}✅ Audio WAV: $OUTPUT_AUDIO${NC}"
    if [ -f "$OUTPUT_AUDIO_AAC" ]; then
        echo -e "${GREEN}✅ Audio AAC: $OUTPUT_AUDIO_AAC${NC}"
    fi
else
    echo -e "${GREEN}✅ Video final: $OUTPUT_VIDEO${NC}"
fi

echo -e "${GREEN}✅ SRT Debug: $DEBUG_SRT${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

# Limpieza
if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}⚠️  MODO TEST: Conservando $TEMP_DIR${NC}"
elif [ "$SKIP_TTS" = false ]; then
    echo -e "${YELLOW}Limpiando archivos temporales...${NC}"
    rm -rf "$TEMP_DIR"
else
    echo -e "${YELLOW}Conservando: $TEMP_DIR${NC}"
fi

echo -e "${GREEN}¡Proceso completado!${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${CYAN}Modo solo-audio: Audio TTS generado sin freezes${NC}"
    echo -e "${CYAN}Usa los comandos mostrados arriba para agregar el audio al video${NC}"
elif [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}⚠️  Video de prueba con ${TEST_LIMIT} subtítulos${NC}"
fi