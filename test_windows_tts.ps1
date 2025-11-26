# Script PowerShell para TTS nativo de Windows
# Uso: .\test_windows_tts.ps1

Write-Host "🎙️  TEST TTS NATIVO DE WINDOWS" -ForegroundColor Cyan
Write-Host "=" * 60

# Cargar el ensamblado de síntesis de voz
Add-Type -AssemblyName System.Speech

# Crear objeto de síntesis
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

# Mostrar voces disponibles
Write-Host "`n🎤 Voces disponibles en el sistema:" -ForegroundColor Green
$voices = $synth.GetInstalledVoices()
$index = 0
foreach ($voice in $voices) {
    $name = $voice.VoiceInfo.Name
    $culture = $voice.VoiceInfo.Culture.Name
    $gender = $voice.VoiceInfo.Gender
    Write-Host "  [$index] $name ($culture, $gender)"
    $index++
}

# Configurar voz (intentar español, si no usar la primera disponible)
$spanishVoice = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like "es*" } | Select-Object -First 1
if ($spanishVoice) {
    $synth.SelectVoice($spanishVoice.VoiceInfo.Name)
    Write-Host "`n✅ Usando voz en español: $($spanishVoice.VoiceInfo.Name)" -ForegroundColor Green
} else {
    Write-Host "`n⚠️  No hay voz en español, usando voz por defecto" -ForegroundColor Yellow
}

# Configurar velocidad (0 = normal, positivo = más rápido, negativo = más lento)
# Rango: -10 (muy lento) a 10 (muy rápido)
$synth.Rate = 2  # Un poco más rápido que normal

# Texto de prueba
$texto = "Hola, esta es una prueba del sistema de síntesis de voz nativo de Windows. Este motor funciona completamente offline."

# Generar audio a archivo WAV
$outputFile = "test_windows_tts.wav"
Write-Host "`n📝 Texto: $texto" -ForegroundColor Cyan
Write-Host "🎤 Generando audio..." -ForegroundColor Cyan

$synth.SetOutputToWaveFile($outputFile)
$synth.Speak($texto)
$synth.SetOutputToDefaultAudioDevice()

# Verificar archivo
if (Test-Path $outputFile) {
    $size = (Get-Item $outputFile).Length
    Write-Host "`n✅ Audio generado exitosamente!" -ForegroundColor Green
    Write-Host "   Archivo: $outputFile"
    Write-Host "   Tamaño: $([math]::Round($size/1KB, 2)) KB"
    Write-Host "`n💡 Reproduce con: Start-Process $outputFile" -ForegroundColor Cyan

    # Reproducir automáticamente
    Write-Host "`n🔊 Reproduciendo audio..." -ForegroundColor Yellow
    $synth.SetOutputToDefaultAudioDevice()
    $synth.Speak($texto)
} else {
    Write-Host "`n❌ Error: No se pudo generar el archivo" -ForegroundColor Red
}

# Ejemplo de diferentes velocidades
Write-Host "`n" + "=" * 60
Write-Host "🎛️  GENERANDO DIFERENTES VELOCIDADES" -ForegroundColor Cyan
Write-Host "=" * 60

$speeds = @(-2, 0, 2, 4)
$speedNames = @("Lenta", "Normal", "Rápida", "Muy Rápida")

for ($i = 0; $i -lt $speeds.Length; $i++) {
    $speed = $speeds[$i]
    $speedName = $speedNames[$i]
    $outputFile = "test_windows_speed_$speed.wav"

    $synth.Rate = $speed
    $synth.SetOutputToWaveFile($outputFile)
    $synth.Speak("Prueba de velocidad: $speedName")

    if (Test-Path $outputFile) {
        $size = (Get-Item $outputFile).Length
        Write-Host "  ✅ Velocidad $speed ($speedName): $outputFile ($([math]::Round($size/1KB, 2)) KB)"
    }
}

$synth.SetOutputToDefaultAudioDevice()

Write-Host "`n" + "=" * 60
Write-Host "✨ VENTAJAS DEL TTS DE WINDOWS:" -ForegroundColor Green
Write-Host "=" * 60
Write-Host "  ✅ 100% offline - no requiere internet"
Write-Host "  ✅ Rápido - genera audio instantáneamente"
Write-Host "  ✅ Incluido en Windows - no requiere instalación"
Write-Host "  ✅ Múltiples voces si están instaladas"
Write-Host "  ✅ Control de velocidad y tono"
Write-Host "`n⚠️  LIMITACIÓN:"
Write-Host "  - Calidad de voz depende de las voces instaladas"
Write-Host "  - Puede sonar robótica en voces básicas"

Write-Host "`n💡 Para instalar más voces en Windows:"
Write-Host "   Configuración > Hora e idioma > Voz > Agregar voces"

Write-Host "`n✅ Test completado!" -ForegroundColor Green
