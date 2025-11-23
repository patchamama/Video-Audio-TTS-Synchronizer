#!/bin/bash

# Script v2.5 para generar audio TTS con ajuste automático de velocidad
# Compatible con macOS (say) y Linux/otros (gTTS via Python)
# NUEVO v2.5: Opción --no-freeze para truncar audios largos sin congelar video
# NUEVO v2.5: Mejor manejo de errores con logs detallados
# Uso: ./srt_to_video_v2.5.sh [archivo.srt] [video] [carpeta_audios_opcional] [--test] [--solo-audio] [--no-freeze]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Detectar sistema operativo y método TTS
detect_tts_method() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v say &> /dev/null; then
            TTS_METHOD="say"
            echo -e "${GREEN}✓ Sistema: macOS - Usando comando 'say'${NC}"
            return 0
        fi
    fi
    
    if command -v python3 &> /dev/null; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PYTHON_TTS_SCRIPT="$SCRIPT_DIR/generate_tts.py"
        
        if [ ! -f "$PYTHON_TTS_SCRIPT" ]; then
            echo -e "${RED}✗ Error: No se encuentra generate_tts.py${NC}"
            return 1
        fi
        
        if python3 -c "import gtts, pydub" 2>/dev/null; then
            TTS_METHOD="python"
            echo -e "${GREEN}✓ Sistema: Linux/Otro - Usando Python + gTTS${NC}"
            return 0
        else
            echo -e "${RED}✗ Error: Faltan dependencias de Python${NC}"
            echo -e "${YELLOW}Instala con: pip3 install gtts pydub${NC}"
            return 1
        fi
    fi
    
    echo -e "${RED}✗ Error: No se encontró método TTS compatible${NC}"
    return 1
}

TTS_METHOD=""
PYTHON_TTS_SCRIPT=""

usage() {
    echo "Uso: $0 [archivo.srt] [video] [carpeta_audios_opcional] [--test[=N]] [--solo-audio] [--no-freeze] [--remove-breaks]"
    echo ""
    echo "Parámetros:"
    echo "  archivo.srt              - Archivo de subtítulos"
    echo "  video                    - Nombre del video"
    echo "  carpeta_audios_opcional  - Carpeta con audios ya generados"
    echo "  --test                   - Modo test: 30 subtítulos"
    echo "  --test=N                 - Modo test: N subtítulos"
    echo "  --solo-audio             - Solo genera audio, sin video"
    echo "  --no-freeze              - Trunca audios largos en lugar de freeze"
    echo "  --remove-breaks          - Elimina pausas >15min del video final"
    echo ""
    echo "Ejemplos:"
    echo "  $0 subtitulos.srt video.mp4"
    echo "  $0 subtitulos.srt video.mp4 --no-freeze"
    echo "  $0 subtitulos.srt video.mp4 --test=100 --no-freeze"
    echo "  $0 subtitulos.srt video.mp4 --remove-breaks"
    exit 1
}

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

seconds_to_srt_time() {
    local total_seconds=$1
    
    if [ -z "$total_seconds" ] || [ "$total_seconds" = "0" ]; then
        echo "00:00:00,000"
        return
    fi
    
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

get_duration() {
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null
}

create_silence() {
    local duration=$1
    local output=$2
    ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t "$duration" -q:a 9 -acodec pcm_s16le "$output" -y &>/dev/null
}

truncate_audio() {
    local input=$1
    local output=$2
    local duration=$3
    local log_file=$4
    
    echo -e "  ${YELLOW}Truncando audio a ${duration}s...${NC}"
    
    if ffmpeg -i "$input" -t "$duration" -c:a copy "$output" -y 2>"$log_file"; then
        if [ -f "$output" ] && [ -s "$output" ]; then
            echo -e "  ${GREEN}✓ Audio truncado exitosamente${NC}"
            return 0
        fi
    fi
    
    echo -e "  ${RED}✗ Error truncando audio${NC}"
    echo -e "  ${YELLOW}Ver log: $log_file${NC}"
    return 1
}

generate_audio_with_rate() {
    local text=$1
    local rate=$2
    local output=$3
    
    if [ "$TTS_METHOD" = "say" ]; then
        say -v Paulina -r "$rate" "$text" -o "${output%.wav}.aiff" 2>/dev/null
        ffmpeg -i "${output%.wav}.aiff" "$output" -y &>/dev/null
        rm "${output%.wav}.aiff"
    elif [ "$TTS_METHOD" = "python" ]; then
        python3 "$PYTHON_TTS_SCRIPT" "$text" "$output" -r "$rate" -l es 2>/dev/null
        
        if [ ! -f "$output" ]; then
            echo -e "${RED}Error: Python TTS falló para rate $rate${NC}" >&2
            return 1
        fi
    else
        echo -e "${RED}Error: Método TTS no configurado${NC}" >&2
        return 1
    fi
}

# Parsear argumentos
AUDIO_DIR=""
TEST_MODE=false
TEST_LIMIT=30
SOLO_AUDIO=false
NO_FREEZE=false
REMOVE_BREAKS=false

for arg in "$@"; do
    if [ "$arg" = "--test" ]; then
        TEST_MODE=true
    elif [[ "$arg" =~ ^--test=([0-9]+)$ ]]; then
        TEST_MODE=true
        TEST_LIMIT="${BASH_REMATCH[1]}"
    elif [ "$arg" = "--solo-audio" ]; then
        SOLO_AUDIO=true
    elif [ "$arg" = "--no-freeze" ]; then
        NO_FREEZE=true
    elif [ "$arg" = "--remove-breaks" ]; then
        REMOVE_BREAKS=true
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
    read -p "¿Truncar audios largos (no-freeze)? (s/n): " no_freeze_response
    if [ "$no_freeze_response" = "s" ]; then
        NO_FREEZE=true
    fi
    read -p "¿Eliminar pausas >15min (remove-breaks)? (s/n): " remove_breaks_response
    if [ "$remove_breaks_response" = "s" ]; then
        REMOVE_BREAKS=true
    fi
elif [ $# -ge 2 ]; then
    SRT_FILE=$1
    VIDEO_NAME=$2
    
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
        elif [ "$arg" = "--no-freeze" ]; then
            NO_FREEZE=true
        elif [ "$arg" = "--remove-breaks" ]; then
            REMOVE_BREAKS=true
        elif [[ "$arg" =~ ^[0-9]+$ ]] && [ "$TEST_MODE" = true ]; then
            TEST_LIMIT=$arg
        elif [ "$TEST_MODE" = false ] && [ "$SOLO_AUDIO" = false ] && [ "$NO_FREEZE" = false ] && [ "$REMOVE_BREAKS" = false ]; then
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
    echo -e "${CYAN}🎵 MODO SOLO-AUDIO: No se generará video${NC}"
fi

if [ "$NO_FREEZE" = true ]; then
    echo -e "${MAGENTA}🚫 MODO NO-FREEZE: Audios largos serán truncados${NC}"
fi

if [ "$REMOVE_BREAKS" = true ]; then
    echo -e "${MAGENTA}✂️  MODO REMOVE-BREAKS: Se eliminarán pausas >15min del video final${NC}"
fi

# Detectar método TTS
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🔍 DETECTANDO MÉTODO TTS${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if ! detect_tts_method; then
    exit 1
fi

if [ "$TTS_METHOD" = "python" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PYTHON_TTS_SCRIPT="$SCRIPT_DIR/generate_tts.py"
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
    mkdir -p "$TEMP_DIR/logs"
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

# Variables para tracking
declare -A rate_usage_count
rate_usage_count[180]=0
rate_usage_count[200]=0
rate_usage_count[220]=0
rate_usage_count[240]=0
rate_usage_count[freeze]=0
rate_usage_count[truncated]=0

optimal_rate=180
learning_phase=true
processed_count=0

declare -A needs_freeze
declare -A freeze_durations
declare -A audio_files
declare -A segment_starts
declare -A segment_durations
declare -A audio_rates
declare -A was_truncated

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
        
        # Calcular tiempo disponible
        next_idx=$((idx + 1))
        if [ $next_idx -lt ${#subtitle_ids[@]} ]; then
            next_id="${subtitle_ids[$next_idx]}"
            next_start_time="${subtitle_starts[$next_id]}"
            next_start_seconds=$(srt_time_to_seconds "$next_start_time")
            available_time=$(echo "$next_start_seconds - $start_seconds" | bc -l)
        else
            available_time=$subtitle_duration
        fi
        
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Subtítulo $id${NC}"
        echo -e "${YELLOW}  Texto: ${text:0:50}...${NC}"
        echo -e "${BLUE}  Duración subtítulo: ${subtitle_duration}s${NC}"
        echo -e "${BLUE}  Tiempo disponible: ${available_time}s${NC}"
        
        if [ "$learning_phase" = false ]; then
            current_rate=$optimal_rate
            echo -e "${MAGENTA}🎯 Usando rate aprendido: $current_rate wpm${NC}"
        else
            current_rate=180
        fi
        
        audio_created=false
        final_rate=$current_rate
        
        # Determinar rates según modo
        if [ "$NO_FREEZE" = true ] || [ "$SOLO_AUDIO" = true ]; then
            rate_list="$current_rate 200 220 240"
        else
            rate_list="$current_rate 200 220"
        fi
        
        for try_rate in $rate_list; do
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
            
            if (( $(echo "$diff < 0.5" | bc -l) )); then
                mv "$temp_audio" "$TEMP_DIR/$id.wav"
                audio_created=true
                final_rate=$try_rate
                rate_usage_count[$try_rate]=$((${rate_usage_count[$try_rate]} + 1))
                echo -e "  ${GREEN}✅ Audio ajustado con rate $try_rate${NC}"
                
                needs_freeze[$id]=false
                was_truncated[$id]=false
                audio_files[$id]="$TEMP_DIR/$id.wav"
                audio_rates[$id]=$try_rate
                segment_starts[$id]=$start_seconds
                segment_durations[$id]=$subtitle_duration
                
                break
            else
                rm "$temp_audio"
            fi
        done
        
        if [ "$audio_created" = false ]; then
            if [ "$NO_FREEZE" = true ] || [ "$SOLO_AUDIO" = true ]; then
                echo -e "  ${YELLOW}⚠️  Audio muy largo, generando con rate 240 y truncando${NC}"
                generate_audio_with_rate "$text" "240" "$TEMP_DIR/${id}_full.wav"
                
                log_file="$TEMP_DIR/logs/truncate_${id}.log"
                if truncate_audio "$TEMP_DIR/${id}_full.wav" "$TEMP_DIR/$id.wav" "$available_time" "$log_file"; then
                    rm "$TEMP_DIR/${id}_full.wav"
                    
                    needs_freeze[$id]=false
                    was_truncated[$id]=true
                    audio_files[$id]="$TEMP_DIR/$id.wav"
                    audio_rates[$id]=240
                    segment_starts[$id]=$start_seconds
                    segment_durations[$id]=$subtitle_duration
                    
                    rate_usage_count[truncated]=$((${rate_usage_count[truncated]} + 1))
                    
                    echo -e "  ${GREEN}✅ Audio truncado a ${available_time}s${NC}"
                else
                    echo -e "  ${RED}❌ Error truncando audio${NC}"
                    exit 1
                fi
            else
                echo -e "  ${YELLOW}⚠️  Audio muy largo, generando con rate 220 y marcando para freeze${NC}"
                generate_audio_with_rate "$text" "220" "$TEMP_DIR/$id.wav"
                
                audio_duration=$(get_duration "$TEMP_DIR/$id.wav")
                freeze_time=$(echo "$audio_duration - $available_time" | bc -l | awk '{printf "%.6f", $0}')
                
                needs_freeze[$id]=true
                was_truncated[$id]=false
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
        
        if [ $processed_count -eq 50 ] && [ "$learning_phase" = true ]; then
            echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${MAGENTA}📊 ANÁLISIS DE APRENDIZAJE (50 subtítulos)${NC}"
            echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${MAGENTA}Rate 180 wpm: ${rate_usage_count[180]} veces${NC}"
            echo -e "${MAGENTA}Rate 200 wpm: ${rate_usage_count[200]} veces${NC}"
            echo -e "${MAGENTA}Rate 220 wpm: ${rate_usage_count[220]} veces${NC}"
            echo -e "${MAGENTA}Rate 240 wpm: ${rate_usage_count[240]} veces${NC}"
            echo -e "${MAGENTA}Freeze necesario: ${rate_usage_count[freeze]} veces${NC}"
            echo -e "${MAGENTA}Truncados: ${rate_usage_count[truncated]} veces${NC}"
            
            max_count=0
            for rate in 180 200 220 240; do
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
        was_truncated[$id]=false
        
        if [ ! -v audio_rates[$id] ]; then
            audio_rates[$id]=180
        fi
        
        diff=$(echo "$audio_duration - $available_time" | bc -l)
        if (( $(echo "$diff > 0.5" | bc -l) )) && [ "$SOLO_AUDIO" = false ] && [ "$NO_FREEZE" = false ]; then
            needs_freeze[$id]=true
            freeze_durations[$id]=$(echo "$diff" | awk '{printf "%.6f", $0}')
        else
            needs_freeze[$id]=false
        fi
    done
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 RESUMEN DE PROCESAMIENTO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

freeze_count=0
truncated_count=0
for id in "${subtitle_ids[@]}"; do
    if [ "${needs_freeze[$id]}" = true ]; then
        freeze_count=$((freeze_count + 1))
    fi
    if [ "${was_truncated[$id]}" = true ]; then
        truncated_count=$((truncated_count + 1))
    fi
done

echo -e "${GREEN}Total subtítulos: ${#subtitle_ids[@]}${NC}"
if [ "$NO_FREEZE" = true ] || [ "$SOLO_AUDIO" = true ]; then
    echo -e "${YELLOW}Audios truncados: $truncated_count${NC}"
    echo -e "${GREEN}Sin truncar: $((${#subtitle_ids[@]} - truncated_count))${NC}"
else
    echo -e "${YELLOW}Requieren freeze: $freeze_count${NC}"
    echo -e "${GREEN}Sin freeze: $((${#subtitle_ids[@]} - freeze_count))${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📝 PASO 3: GENERAR SRT DEBUG${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

DEBUG_SRT="${VIDEO_NAME%.*}_debug.srt"
time_offset=0
> "$DEBUG_SRT"

for idx in "${!subtitle_ids[@]}"; do
    id="${subtitle_ids[$idx]}"
    
    start_time="${subtitle_starts[$id]}"
    end_time="${subtitle_ends[$id]}"
    start_seconds=$(srt_time_to_seconds "$start_time")
    end_seconds=$(srt_time_to_seconds "$end_time")
    
    new_start_seconds=$(echo "$start_seconds + $time_offset" | bc -l)
    new_end_seconds=$(echo "$end_seconds + $time_offset" | bc -l)
    
    new_start_time=$(seconds_to_srt_time "$new_start_seconds")
    new_end_time=$(seconds_to_srt_time "$new_end_seconds")
    
    original_text="${subtitle_texts[$id]}"
    rate="${audio_rates[$id]}"
    offset_ms=$(echo "$time_offset * 1000" | bc -l | awk '{printf "%.0f", $0}')
    
    if [ "${was_truncated[$id]}" = true ]; then
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            new_text="[#$id r$rate +${offset_ms}ms] [✂️ TRUNCADO] $original_text"
        else
            new_text="[#$id r$rate] [✂️ TRUNCADO] $original_text"
        fi
    elif [ "${needs_freeze[$id]}" = true ]; then
        freeze_dur="${freeze_durations[$id]}"
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            new_text="[#$id r$rate +${offset_ms}ms] [⏸️ FREEZE +${freeze_dur}s] $original_text"
        else
            new_text="[#$id r$rate] [⏸️ FREEZE +${freeze_dur}s] $original_text"
        fi
        time_offset=$(echo "$time_offset + $freeze_dur" | bc -l)
    else
        if (( $(echo "$time_offset > 0" | bc -l) )); then
            new_text="[#$id r$rate +${offset_ms}ms] $original_text"
        else
            new_text="[#$id r$rate] $original_text"
        fi
    fi
    
    echo "$id" >> "$DEBUG_SRT"
    echo "$new_start_time --> $new_end_time" >> "$DEBUG_SRT"
    echo "$new_text" >> "$DEBUG_SRT"
    echo "" >> "$DEBUG_SRT"
done

echo -e "${GREEN}✅ Archivo SRT debug generado: $DEBUG_SRT${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎬 PASO 4: PROCESAR VIDEO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${CYAN}Modo solo-audio: Saltando procesamiento de video${NC}"
    VIDEO_TO_USE=""
elif [ "$NO_FREEZE" = true ]; then
    echo -e "${CYAN}Modo no-freeze: Usando video original${NC}"
    VIDEO_TO_USE="$VIDEO_FILE"
else
    if [ $freeze_count -gt 0 ]; then
        echo -e "${YELLOW}Procesando video con freezes...${NC}"
        
        FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null)
        FPS=$(echo "scale=2; $FPS" | bc -l 2>/dev/null || echo "30")
        echo -e "${GREEN}FPS: $FPS${NC}"
        
        VIDEO_SEGMENTS=()
        
        for id in "${subtitle_ids[@]}"; do
            start_sec="${segment_starts[$id]}"
            duration="${segment_durations[$id]}"
            
            echo -e "${YELLOW}Segmento $id (${start_sec}s, ${duration}s)${NC}"
            
            seg_log="$TEMP_DIR/logs/vseg_${id}.log"
            
            if ! [[ "$start_sec" =~ ^[0-9]+\.?[0-9]*$ ]] || ! [[ "$duration" =~ ^[0-9]+\.?[0-9]*$ ]]; then
                echo -e "${RED}Error: Parámetros inválidos${NC}"
                echo -e "${YELLOW}Saltando segmento...${NC}"
                continue
            fi
            
            if (( $(echo "$start_sec < 0" | bc -l) )) || (( $(echo "$duration <= 0" | bc -l) )); then
                echo -e "${RED}Error: Valores negativos o cero${NC}"
                echo -e "${YELLOW}Saltando segmento...${NC}"
                continue
            fi
            
            echo -e "  ${BLUE}Extrayendo segmento...${NC}"
            if ffmpeg -i "$VIDEO_FILE" -ss "$start_sec" -t "$duration" \
                -c:v libx264 -preset ultrafast -an \
                "$TEMP_DIR/vseg_${id}.mkv" -y 2>"$seg_log"; then
                
                if [ -f "$TEMP_DIR/vseg_${id}.mkv" ] && [ -s "$TEMP_DIR/vseg_${id}.mkv" ]; then
                    seg_size=$(stat -f%z "$TEMP_DIR/vseg_${id}.mkv" 2>/dev/null || stat -c%s "$TEMP_DIR/vseg_${id}.mkv" 2>/dev/null)
                    echo -e "  ${GREEN}✓ Segmento creado (${seg_size} bytes)${NC}"
                    VIDEO_SEGMENTS+=("$TEMP_DIR/vseg_${id}.mkv")
                else
                    echo -e "${RED}Error: Segmento vacío${NC}"
                    echo -e "${YELLOW}Ver log: $seg_log${NC}"
                    continue
                fi
            else
                echo -e "${RED}Error creando segmento${NC}"
                echo -e "${YELLOW}Ver log: $seg_log${NC}"
                if [ -f "$seg_log" ]; then
                    tail -10 "$seg_log"
                fi
                continue
            fi
            
            if [ "${needs_freeze[$id]}" = true ]; then
                freeze_dur="${freeze_durations[$id]}"
                echo -e "  ${YELLOW}+ Creando freeze de ${freeze_dur}s...${NC}"
                
                frame_log="$TEMP_DIR/logs/frame_${id}.log"
                freeze_log="$TEMP_DIR/logs/freeze_${id}.log"
                
                frame_extracted=false
                
                if ffmpeg -sseof -0.1 -i "$TEMP_DIR/vseg_${id}.mkv" -frames:v 1 \
                    "$TEMP_DIR/freeze_${id}.png" -y 2>"$frame_log"; then
                    if [ -f "$TEMP_DIR/freeze_${id}.png" ] && [ -s "$TEMP_DIR/freeze_${id}.png" ]; then
                        frame_extracted=true
                        echo -e "  ${GREEN}✓ Frame extraído${NC}"
                    fi
                fi
                
                if [ "$frame_extracted" = false ]; then
                    echo -e "  ${YELLOW}Omitiendo freeze${NC}"
                    continue
                fi
                
                if ffmpeg -loop 1 -i "$TEMP_DIR/freeze_${id}.png" -t "$freeze_dur" \
                    -r "$FPS" -pix_fmt yuv420p -c:v libx264 -preset ultrafast \
                    "$TEMP_DIR/vfreeze_${id}.mkv" -y 2>"$freeze_log"; then
                    
                    if [ -f "$TEMP_DIR/vfreeze_${id}.mkv" ] && [ -s "$TEMP_DIR/vfreeze_${id}.mkv" ]; then
                        VIDEO_SEGMENTS+=("$TEMP_DIR/vfreeze_${id}.mkv")
                        echo -e "  ${GREEN}✓ Freeze creado${NC}"
                    fi
                fi
            fi
        done
        
        if [ ${#VIDEO_SEGMENTS[@]} -eq 0 ]; then
            echo -e "${RED}Error: No se crearon segmentos${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Concatenando ${#VIDEO_SEGMENTS[@]} segmentos...${NC}"
        VIDEO_LIST="$TEMP_DIR/video_segments.txt"
        > "$VIDEO_LIST"
        
        for seg in "${VIDEO_SEGMENTS[@]}"; do
            if [ -f "$seg" ] && [ -s "$seg" ]; then
                echo "file '$(basename "$seg")'" >> "$VIDEO_LIST"
            fi
        done
        
        seg_count=$(wc -l < "$VIDEO_LIST" | tr -d ' ')
        if [ "$seg_count" -eq 0 ]; then
            echo -e "${RED}Error: No hay segmentos válidos${NC}"
            exit 1
        fi
        
        concat_log="$TEMP_DIR/logs/concat_video.log"
        
        if ffmpeg -f concat -safe 0 -i "$VIDEO_LIST" -c copy \
            "$TEMP_DIR/video_processed.mkv" -y 2>"$concat_log"; then
            
            if [ -f "$TEMP_DIR/video_processed.mkv" ] && [ -s "$TEMP_DIR/video_processed.mkv" ]; then
                VIDEO_TO_USE="$TEMP_DIR/video_processed.mkv"
                echo -e "${GREEN}✓ Video procesado${NC}"
            else
                echo -e "${RED}Error: Video vacío${NC}"
                exit 1
            fi
        else
            echo -e "${RED}Error concatenando${NC}"
            echo -e "${YELLOW}Ver log: $concat_log${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}Sin freezes, usando video original${NC}"
        VIDEO_TO_USE="$VIDEO_FILE"
    fi
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎵 PASO 5: CONSTRUIR AUDIO SINCRONIZADO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

create_silence "0.001" "$TEMP_DIR/audio_master.wav"
current_master_duration=0

for idx in "${!subtitle_ids[@]}"; do
    id="${subtitle_ids[$idx]}"
    start_sec="${segment_starts[$id]}"
    audio_file="${audio_files[$id]}"
    
    audio_duration=$(get_duration "$audio_file")
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Subtítulo $id (inicio: ${start_sec}s)${NC}"
    
    actual_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    current_master_duration=$actual_master_duration
    
    gap=$(echo "$start_sec - $current_master_duration" | bc -l | awk '{printf "%.6f", $0}')
    
    if (( $(echo "$gap > 0.01" | bc -l) )); then
        echo -e "  ${GREEN}→ Agregando silencio de ${gap}s${NC}"
        create_silence "$gap" "$TEMP_DIR/gap_${id}.wav"
        ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$TEMP_DIR/gap_${id}.wav" \
            -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
            -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
        mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
        rm "$TEMP_DIR/gap_${id}.wav"
        current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    fi
    
    echo -e "  ${GREEN}→ Agregando audio TTS (${audio_duration}s)${NC}"
    if [ "${was_truncated[$id]}" = true ]; then
        echo -e "  ${MAGENTA}  (Audio truncado)${NC}"
    fi
    
    ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$audio_file" \
        -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
        -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
    mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
    
    current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    
    next_idx=$((idx + 1))
    if [ $next_idx -lt ${#subtitle_ids[@]} ]; then
        next_id="${subtitle_ids[$next_idx]}"
        next_start="${segment_starts[$next_id]}"
        expected_position=$next_start
    else
        end_sec=$(echo "$start_sec + ${segment_durations[$id]}" | bc -l)
        expected_position=$end_sec
    fi
    
    padding=$(echo "$expected_position - $current_master_duration" | bc -l | awk '{printf "%.6f", $0}')
    
    if (( $(echo "$padding > 0.01" | bc -l) )); then
        echo -e "  ${GREEN}→ Agregando padding de ${padding}s${NC}"
        create_silence "$padding" "$TEMP_DIR/padding_${id}.wav"
        ffmpeg -i "$TEMP_DIR/audio_master.wav" -i "$TEMP_DIR/padding_${id}.wav" \
            -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
            -map "[out]" "$TEMP_DIR/audio_master_temp.wav" -y &>/dev/null
        mv "$TEMP_DIR/audio_master_temp.wav" "$TEMP_DIR/audio_master.wav"
        rm "$TEMP_DIR/padding_${id}.wav"
        current_master_duration=$(get_duration "$TEMP_DIR/audio_master.wav")
    fi
    
    final_diff=$(echo "$current_master_duration - $expected_position" | bc -l | awk '{printf "%.3f", ($0 < 0) ? -$0 : $0}')
    
    if (( $(echo "$final_diff < 0.05" | bc -l) )); then
        echo -e "  ${GREEN}✅ Sincronizado (diff: ${final_diff}s)${NC}"
    else
        echo -e "  ${RED}❌ Desincronizado (diff: ${final_diff}s)${NC}"
    fi
done

mv "$TEMP_DIR/audio_master.wav" "$TEMP_DIR/audio_final.wav"
echo -e "${GREEN}✅ Audio final creado${NC}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎞️  PASO 6: FUSIONAR VIDEO Y AUDIO${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    OUTPUT_AUDIO="${VIDEO_NAME%.*}_tts_audio.wav"
    cp "$TEMP_DIR/audio_final.wav" "$OUTPUT_AUDIO"
    echo -e "${GREEN}✅ Audio: $OUTPUT_AUDIO${NC}"
    
    OUTPUT_AUDIO_AAC="${VIDEO_NAME%.*}_tts_audio.aac"
    ffmpeg -i "$OUTPUT_AUDIO" -c:a aac -b:a 192k "$OUTPUT_AUDIO_AAC" -y &>/dev/null
    if [ -f "$OUTPUT_AUDIO_AAC" ]; then
        echo -e "${GREEN}✅ Audio AAC: $OUTPUT_AUDIO_AAC${NC}"
    fi
else
    OUTPUT_VIDEO="${VIDEO_NAME%.*}_con_tts.mkv"
    
    merge_log="$TEMP_DIR/logs/ffmpeg_merge.log"
    
    ffmpeg -i "$VIDEO_TO_USE" -i "$TEMP_DIR/audio_final.wav" \
        -map 0:v:0 -map 1:a:0 \
        -c:v copy -c:a aac -b:a 192k \
        -shortest \
        "$OUTPUT_VIDEO" -y 2>"$merge_log"
    
    if [ ! -f "$OUTPUT_VIDEO" ]; then
        echo -e "${RED}Error creando video${NC}"
        echo -e "${YELLOW}Ver log: $merge_log${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Video: $OUTPUT_VIDEO${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}✅ VERIFICACIÓN FINAL${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${GREEN}Modo solo-audio completado${NC}"
    if [ "$NO_FREEZE" = true ] && [ $truncated_count -gt 0 ]; then
        echo -e "${MAGENTA}⚠️  $truncated_count audios truncados${NC}"
    fi
else
    audio_stream_count=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUTPUT_VIDEO" 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$audio_stream_count" -eq 0 ]; then
        echo -e "${RED}❌ No hay audio en el video${NC}"
        echo -e "${YELLOW}Intentando método alternativo...${NC}"
        
        OUTPUT_VIDEO_ALT="${VIDEO_NAME%.*}_con_tts_alt.mkv"
        alt_log="$TEMP_DIR/logs/ffmpeg_merge_alt.log"
        
        ffmpeg -i "$VIDEO_TO_USE" -i "$TEMP_DIR/audio_final.wav" \
            -map 0:v:0 -map 1:a:0 \
            -c:v libx264 -preset ultrafast -crf 18 \
            -c:a aac -b:a 192k \
            -shortest \
            "$OUTPUT_VIDEO_ALT" -y 2>"$alt_log"
        
        if [ -f "$OUTPUT_VIDEO_ALT" ]; then
            alt_audio_count=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$OUTPUT_VIDEO_ALT" 2>/dev/null | wc -l | tr -d ' ')
            if [ "$alt_audio_count" -gt 0 ]; then
                mv "$OUTPUT_VIDEO_ALT" "$OUTPUT_VIDEO"
                echo -e "${GREEN}✅ Video creado con método alternativo${NC}"
            else
                echo -e "${RED}❌ Método alternativo falló${NC}"
                exit 1
            fi
        fi
    else
        echo -e "${GREEN}✅ Video con audio verificado${NC}"
    fi
    
    if [ "$NO_FREEZE" = true ] && [ $truncated_count -gt 0 ]; then
        echo -e "${MAGENTA}⚠️  $truncated_count audios truncados${NC}"
    fi
fi

# Procesar video para eliminar pausas largas si está activado --remove-breaks
if [ "$REMOVE_BREAKS" = true ] && [ "$SOLO_AUDIO" = false ]; then
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}✂️  PASO 7: ELIMINAR PAUSAS LARGAS DEL VIDEO${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

    # Configuración
    MIN_GAP_SECONDS=900  # 15 minutos
    MARGIN_SECONDS=60    # 1 minuto de margen

    echo -e "${YELLOW}Analizando gaps en los subtítulos...${NC}"

    # Detectar gaps entre subtítulos
    declare -a gap_starts_final
    declare -a gap_ends_final

    for idx in "${!subtitle_ids[@]}"; do
        if [ $idx -lt $((${#subtitle_ids[@]} - 1)) ]; then
            id="${subtitle_ids[$idx]}"
            next_idx=$((idx + 1))
            next_id="${subtitle_ids[$next_idx]}"

            end_time="${subtitle_ends[$id]}"
            next_start_time="${subtitle_starts[$next_id]}"

            end_seconds=$(srt_time_to_seconds "$end_time")
            next_start_seconds=$(srt_time_to_seconds "$next_start_time")

            gap=$(echo "$next_start_seconds - $end_seconds" | bc -l)

            if (( $(echo "$gap >= $MIN_GAP_SECONDS" | bc -l) )); then
                echo -e "${YELLOW}  ✓ Gap detectado: ${gap}s ($(echo "$gap / 60" | bc -l | awk '{printf "%.1f", $0}') min) entre subtítulo $id y $next_id${NC}"

                # Calcular puntos de corte con márgenes
                cut_start=$(echo "$end_seconds + $MARGIN_SECONDS" | bc -l)
                cut_end=$(echo "$next_start_seconds - $MARGIN_SECONDS" | bc -l)

                cut_duration=$(echo "$cut_end - $cut_start" | bc -l)
                if (( $(echo "$cut_duration > 0" | bc -l) )); then
                    gap_starts_final+=("$cut_start")
                    gap_ends_final+=("$cut_end")
                    echo -e "${GREEN}    → Se eliminará: ${cut_duration}s ($(echo "$cut_duration / 60" | bc -l | awk '{printf "%.1f", $0}') min)${NC}"
                fi
            fi
        fi
    done

    if [ ${#gap_starts_final[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ No se encontraron pausas largas (>15 min)${NC}"
        echo -e "${CYAN}No es necesario generar video sin pausas${NC}"
    else
        echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}Total de pausas a eliminar: ${#gap_starts_final[@]}${NC}"

        # Calcular segmentos a mantener
        declare -a keep_starts
        declare -a keep_ends

        current_pos=0
        for idx in "${!gap_starts_final[@]}"; do
            gap_start="${gap_starts_final[$idx]}"
            gap_end="${gap_ends_final[$idx]}"

            keep_starts+=("$current_pos")
            keep_ends+=("$gap_start")

            current_pos="$gap_end"
        done

        # Agregar segmento final
        video_duration=$(get_duration "$OUTPUT_VIDEO")
        keep_starts+=("$current_pos")
        keep_ends+=("$video_duration")

        echo -e "${YELLOW}Segmentos a mantener: ${#keep_starts[@]}${NC}"

        # Crear segmentos del video final
        BREAK_SEGMENTS_DIR="$TEMP_DIR/break_segments"
        mkdir -p "$BREAK_SEGMENTS_DIR"

        declare -a video_keep_segments

        for idx in "${!keep_starts[@]}"; do
            seg_start="${keep_starts[$idx]}"
            seg_end="${keep_ends[$idx]}"
            seg_dur=$(echo "$seg_end - $seg_start" | bc -l)

            echo -e "${YELLOW}  Extrayendo segmento $((idx+1)): ${seg_start}s a ${seg_end}s (${seg_dur}s)${NC}"

            if (( $(echo "$seg_dur > 0.1" | bc -l) )); then
                seg_file="$BREAK_SEGMENTS_DIR/seg_${idx}.mkv"

                if ffmpeg -i "$OUTPUT_VIDEO" -ss "$seg_start" -t "$seg_dur" \
                    -c copy "$seg_file" -y 2>"$TEMP_DIR/logs/break_seg_${idx}.log"; then

                    if [ -f "$seg_file" ] && [ -s "$seg_file" ]; then
                        video_keep_segments+=("$seg_file")
                        echo -e "${GREEN}    ✓ Segmento creado${NC}"
                    else
                        echo -e "${RED}    ✗ Error: segmento vacío${NC}"
                    fi
                else
                    echo -e "${RED}    ✗ Error creando segmento${NC}"
                fi
            fi
        done

        # Concatenar segmentos
        if [ ${#video_keep_segments[@]} -gt 0 ]; then
            echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
            echo -e "${CYAN}Concatenando ${#video_keep_segments[@]} segmentos...${NC}"

            CONCAT_BREAKS_LIST="$TEMP_DIR/concat_breaks.txt"
            > "$CONCAT_BREAKS_LIST"
            for seg in "${video_keep_segments[@]}"; do
                echo "file '$seg'" >> "$CONCAT_BREAKS_LIST"
            done

            OUTPUT_VIDEO_CLEAN="${VIDEO_NAME%.*}_clean_breaks.mkv"

            if ffmpeg -f concat -safe 0 -i "$CONCAT_BREAKS_LIST" -c copy \
                "$OUTPUT_VIDEO_CLEAN" -y 2>"$TEMP_DIR/logs/concat_clean_breaks.log"; then

                if [ -f "$OUTPUT_VIDEO_CLEAN" ] && [ -s "$OUTPUT_VIDEO_CLEAN" ]; then
                    # Calcular tiempo total eliminado
                    total_removed=0
                    for idx in "${!gap_starts_final[@]}"; do
                        gap_dur=$(echo "${gap_ends_final[$idx]} - ${gap_starts_final[$idx]}" | bc -l)
                        total_removed=$(echo "$total_removed + $gap_dur" | bc -l)
                    done

                    echo -e "${GREEN}✓ Video sin pausas creado: $OUTPUT_VIDEO_CLEAN${NC}"
                    echo -e "${GREEN}✓ Tiempo total eliminado: ${total_removed}s ($(echo "$total_removed / 60" | bc -l | awk '{printf "%.1f", $0}') min)${NC}"
                else
                    echo -e "${RED}✗ Error: video vacío${NC}"
                fi
            else
                echo -e "${RED}✗ Error concatenando segmentos${NC}"
            fi
        else
            echo -e "${RED}✗ No se crearon segmentos válidos${NC}"
        fi
    fi
fi

echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📄 ARCHIVOS GENERADOS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

if [ "$SOLO_AUDIO" = true ]; then
    echo -e "${GREEN}✅ $OUTPUT_AUDIO${NC}"
    [ -f "$OUTPUT_AUDIO_AAC" ] && echo -e "${GREEN}✅ $OUTPUT_AUDIO_AAC${NC}"
else
    echo -e "${GREEN}✅ $OUTPUT_VIDEO${NC}"
    if [ "$REMOVE_BREAKS" = true ] && [ -n "$OUTPUT_VIDEO_CLEAN" ] && [ -f "$OUTPUT_VIDEO_CLEAN" ]; then
        echo -e "${GREEN}✅ $OUTPUT_VIDEO_CLEAN ${CYAN}(sin pausas largas)${NC}"
    fi
fi
echo -e "${GREEN}✅ $DEBUG_SRT${NC}"

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}⚠️  Conservando: $TEMP_DIR${NC}"
elif [ "$SKIP_TTS" = false ]; then
    echo -e "${YELLOW}Limpiando temporales...${NC}"
    rm -rf "$TEMP_DIR"
fi

echo -e "${GREEN}¡Proceso completado!${NC}"