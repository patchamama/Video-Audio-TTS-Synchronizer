const $ = selector => document.querySelector(selector);
const logs = $('#o');
const progress = $('#progress');
const progressLabel = $('#progressLabel');
const srtFile = $('#srtFile');
const videoFile = $('#videoFile');
const localSrt = $('#localSrt');
const localVideo = $('#localVideo');
const backendBase = $('#backendBase');
backendBase.value = location.origin;
let activeBackendBase = backendBase.value;
const backendUrl = path => new URL(path, backendBase.value || location.origin).toString();
const backendFileUrl = url => new URL(url, backendBase.value || location.origin).toString();
const outputFiles = () => $('#results');
const audioExtensions = new Set(['wav', 'aac', 'mp3', 'ogg', 'm4a']);
const videoExtensions = new Set(['mp4', 'mkv', 'mov', 'avi', 'webm']);
const isMinimalMode = new URLSearchParams(location.search).get('mode') === 'minimal';
if (isMinimalMode) {
  document.body.classList.add('minimal');
  const minimalLink = $('#minimalMode');
  minimalLink.href = '/'; minimalLink.textContent = '↗ Vista avanzada';
}
const subtitleProgress = output => [...output.matchAll(/Subtítulo\s+(\d+)\/(\d+)/gi)].pop();

const readFile = async file => file?.name
  ? {name: file.name, data: btoa(String.fromCharCode(...new Uint8Array(await file.arrayBuffer())))}
  : null;
const extension = name => name.split('.').pop().toLowerCase();
const fileKind = file => extension(file.name) === 'srt' ? 'subtitle' : videoExtensions.has(extension(file.name)) ? 'video' : audioExtensions.has(extension(file.name)) || file.audio ? 'audio' : 'file';
const iconFor = file => ({subtitle: '📝', video: '🎬', audio: '🎧', file: '📄'})[fileKind(file)];
const srtSeconds = value => {
  const [hours, minutes, seconds] = value.trim().replace(',', '.').split(':');
  return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds);
};
const formatTime = seconds => new Date(Math.max(0, seconds) * 1000).toISOString().slice(11, 19);

function parseSrt(source) {
  return source.trim().split(/\r?\n\s*\r?\n/).map(block => {
    const lines = block.trim().split(/\r?\n/);
    const timeIndex = lines.findIndex(line => line.includes('-->'));
    if (timeIndex < 0) return null;
    const [start, end] = lines[timeIndex].split('-->').map(srtSeconds);
    const text = lines.slice(timeIndex + 1).join(' ');
    const offset = text.match(/^\((-?[\d.]+)s\)\s*/);
    return {start, end, text: text.replace(/^\((-?[\d.]+)s\)\s*/, ''), offset: offset?.[1]};
  }).filter(Boolean);
}

function createCueList(cues, onSelect) {
  const cueList = document.createElement('ol');
  cueList.className = 'cue-list';
  const rows = cues.map((cue, index) => {
    const item = document.createElement('li');
    item.className = 'cue';
    item.tabIndex = 0;
    const time = document.createElement('span');
    time.className = 'cue-time';
    time.textContent = `${formatTime(cue.start)} → ${formatTime(cue.end)}`;
    const text = document.createElement('span');
    text.className = 'cue-text';
    text.textContent = cue.text;
    item.append(time);
    if (cue.offset !== undefined) {
      const offset = document.createElement('span');
      offset.className = 'cue-offset';
      offset.textContent = `${Number(cue.offset) >= 0 ? '+' : ''}${cue.offset}s`;
      item.append(offset);
    }
    item.append(text);
    item.onclick = () => onSelect(cue);
    item.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(cue); } };
    cueList.append(item);
    return {cue, item, index};
  });
  return {cueList, rows};
}

function createSubtitleViewer(subtitle, cues) {
  const wrapper = document.createElement('section');
  wrapper.className = 'viewer subtitle-viewer';
  const title = document.createElement('h2');
  title.textContent = `📝 Subtítulos: ${subtitle.name}`;
  const {cueList} = createCueList(cues, () => {});
  wrapper.append(title, cueList);
  return wrapper;
}

function seekPlayerToCue(player, cue) {
  const seek = () => {
    if (!Number.isFinite(cue.start)) return;
    const maxTime = Number.isFinite(player.duration) ? Math.max(0, player.duration - 0.01) : cue.start;
    player.currentTime = Math.min(Math.max(0, cue.start), maxTime);
    const playback = player.play();
    if (playback) playback.catch(() => {});
  };
  if (player.readyState < 1) player.addEventListener('loadedmetadata', seek, {once: true});
  else seek();
}

function createSyncedPlayer(media, cues) {
  const wrapper = document.createElement('section');
  wrapper.className = 'viewer';
  const title = document.createElement('h2');
  title.textContent = `${iconFor(media)} Visor: ${media.name}`;
  const player = document.createElement(fileKind(media) === 'video' ? 'video' : 'audio');
  player.controls = true;
  player.preload = 'metadata';
  player.src = media.url;
  const subtitleTitle = document.createElement('h3');
  subtitleTitle.textContent = cues.length ? '📝 Subtítulos sincronizados' : '📝 Elegí un archivo SRT para ver sus cues';
  const {cueList, rows} = createCueList(cues, cue => seekPlayerToCue(player, cue));
  let activeCue;
  player.ontimeupdate = () => {
    const row = rows.find(({cue}) => player.currentTime >= cue.start && player.currentTime < cue.end);
    if (row?.item === activeCue) return;
    activeCue?.classList.remove('active');
    activeCue = row?.item;
    activeCue?.classList.add('active');
    activeCue?.scrollIntoView({block: 'nearest'});
  };
  wrapper.append(title, player, subtitleTitle, cueList);
  return wrapper;
}
window.VideoTTS = {parseSrt, createSyncedPlayer, seekPlayerToCue};

async function fetchCues(file) {
  if (!file || fileKind(file) !== 'subtitle') return [];
  const response = await fetch(file.url);
  return response.ok ? parseSrt(await response.text()) : [];
}

function resultLink(label, className, action) {
  const link = document.createElement('a');
  link.href = '#viewer'; link.className = className; link.textContent = label;
  link.onclick = event => { event.preventDefault(); action(); };
  return link;
}

async function renderResults(files) {
  const panel = outputFiles();
  panel.replaceChildren();
  if (!files.length) return;
  const section = document.createElement('section');
  section.className = 'results-panel';
  const title = document.createElement('h2');
  title.textContent = '✨ Resultados';
  const help = document.createElement('p');
  help.className = 'result-help';
  help.textContent = 'Seleccioná un audio, video o SRT para abrirlo en el visor sincronizado.';
  const list = document.createElement('ul');
  const viewer = document.createElement('div');
  viewer.id = 'viewer';
  let selectedMedia = files.find(file => fileKind(file) === 'audio') || files.find(file => fileKind(file) === 'video');
  let selectedSubtitle = files.find(file => /-to-test\.srt$/i.test(file.name)) || files.find(file => fileKind(file) === 'subtitle');

  const updateViewer = async () => {
    viewer.replaceChildren();
    const cues = await fetchCues(selectedSubtitle);
    if (selectedMedia) viewer.append(createSyncedPlayer(selectedMedia, cues));
    else if (selectedSubtitle) viewer.append(createSubtitleViewer(selectedSubtitle, cues));
  };

  files.forEach(file => {
    const item = document.createElement('li');
    item.className = `result-file ${fileKind(file)}`;
    const name = resultLink(`${iconFor(file)} ${file.name}`, 'file-name', async () => {
      if (fileKind(file) === 'subtitle') selectedSubtitle = file;
      else if (fileKind(file) === 'audio' || fileKind(file) === 'video') selectedMedia = file;
      await updateViewer(); viewer.scrollIntoView({behavior: 'smooth', block: 'start'});
    });
    const open = document.createElement('a');
    open.href = file.url; open.target = '_blank'; open.rel = 'noopener'; open.textContent = 'Abrir';
    const download = document.createElement('a');
    download.href = file.url; download.download = file.name; download.textContent = 'Descargar';
    item.append(name, open, download);
    list.append(item);
  });
  section.append(title, help, list, viewer);
  panel.append(section);
  await updateViewer();
}

async function poll(id) {
  const response = await fetch(backendUrl('/status?id=' + encodeURIComponent(id)));
  const status = await response.json();
  logs.textContent = status.output || status.error || '';
  if ($('#autoScroll').checked) logs.scrollTop = logs.scrollHeight;
  const match = subtitleProgress(status.output || '');
  if (match) {
    const [, current, total] = match;
    progress.max = Number(total); progress.value = Number(current);
    progressLabel.textContent = `⏳ Subtítulo ${current}/${total}`;
  }
  if (!status.done) return setTimeout(() => poll(id), 700);
  progressLabel.textContent = match ? progressLabel.textContent : '✅ Procesamiento finalizado';
  renderResults((status.files || []).map(file => ({...file, url: backendFileUrl(file.url)})));
}

function selectedOrUploaded(input) { return input.dataset.local ? {local: input.dataset.local} : readFile(input.files[0]); }
$('#f').onsubmit = async event => {
  event.preventDefault();
  const srt = await selectedOrUploaded(srtFile);
  if (!srt) { logs.textContent = 'Seleccioná un archivo SRT.'; return; }
  progress.max = 1; progress.value = 0; progressLabel.textContent = '⏳ Preparando procesamiento…'; outputFiles().replaceChildren();
  const options = Object.fromEntries(new FormData(event.currentTarget));
  ['solo_audio', 'no_truncate', 'optimize_rate', 'fix_rate_not_truncate', 'no_freeze', 'remove_breaks', 'only_remove_breaks', 'test'].forEach(key => { options[key] = options[key] === 'on'; });
  options.fix_rate_not_truncate_rate = Number(options.fix_rate_not_truncate_rate || 200);
  options.fix_rate_not_truncate_pause = Number(options.fix_rate_not_truncate_pause || 1000);
  options.test_count = Number(options.test_count || 30);
  const selectedVideo = await selectedOrUploaded(videoFile);
  if (options.fix_rate_not_truncate && selectedVideo) { logs.textContent = 'El modo audio plano solo se puede usar sin video.'; return; }
  const response = await fetch(backendUrl('/run'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({srt, video: selectedVideo, opts: options})});
  const job = await response.json();
  if (!job.id) { logs.textContent = 'Error: ' + (job.error || 'No se pudo crear el trabajo'); return; }
  poll(job.id);
};

function populate(select, names) { names.forEach(name => select.add(new Option(name, name))); }
const shellQuote = value => /^[\w./:-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
function updateCliCommand() {
  const form = new FormData($('#f'));
  const srt = localSrt.value || srtFile.files[0]?.name || '<archivo.srt>';
  const video = localVideo.value || videoFile.files[0]?.name;
  const fixedRate = form.get('fix_rate_not_truncate') === 'on';
  const args = ['python3', 'create_video_tts_from_srt.py', srt];
  if (video && !fixedRate) args.push(video);
  args.push('--lang', form.get('lang') || 'es');
  if (form.get('test') === 'on') args.push('--test', form.get('test_count') || '30');
  if (fixedRate) {
    args.push('--fix-rate-not-truncate', form.get('fix_rate_not_truncate_rate') || '200');
    args.push('--fix-rate-not-truncate-pause', form.get('fix_rate_not_truncate_pause') || '1000');
  }
  ['solo_audio', 'no_truncate', 'optimize_rate', 'no_freeze', 'remove_breaks', 'only_remove_breaks']
    .filter(name => form.get(name) === 'on').forEach(name => args.push(`--${name.replaceAll('_', '-')}`));
  $('#cliCommand').textContent = args.map(shellQuote).join(' ');
}
function renderOptions(options) { $('#options').replaceChildren(...options.map(option => {
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.name = option.name; input.type = 'checkbox';
  label.append(input, ` ⚙️ ${option.label}`);
  if (option.rate_name) {
    const rate = document.createElement('input');
    rate.name = option.rate_name; rate.type = 'number'; rate.min = '80'; rate.max = '400'; rate.step = '1'; rate.value = option.default || 200;
    rate.setAttribute('aria-label', 'Rate de voz en palabras por minuto');
    label.append(' · Rate: ', rate, ' ppm');
  }
  if (option.pause_name) {
    const pause = document.createElement('input');
    pause.name = option.pause_name; pause.type = 'number'; pause.min = '0'; pause.step = '100'; pause.value = option.pause_default || 1000;
    pause.setAttribute('aria-label', 'Pausa entre líneas en milisegundos');
    label.append(' · Pausa entre líneas (ms): ', pause);
  }
  return label;
})); updateCliCommand(); }
localSrt.onchange = () => { srtFile.dataset.local = localSrt.value; updateCliCommand(); };
localVideo.onchange = () => { videoFile.dataset.local = localVideo.value; updateCliCommand(); };
srtFile.onchange = updateCliCommand;
videoFile.onchange = updateCliCommand;
$('#f').addEventListener('input', updateCliCommand);
$('#f').addEventListener('change', updateCliCommand);
$('#copyCliCommand').onclick = async () => {
  const command = $('#cliCommand').textContent;
  if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(command);
  else {
    const textarea = document.createElement('textarea');
    textarea.value = command; document.body.append(textarea); textarea.select(); document.execCommand('copy'); textarea.remove();
  }
  $('#copyCliCommand').textContent = '✅ Copiado';
  setTimeout(() => { $('#copyCliCommand').textContent = 'Copiar comando'; }, 1500);
};
updateCliCommand();
$('#drop').ondragover = event => event.preventDefault();
$('#drop').ondrop = event => { event.preventDefault(); for (const file of event.dataTransfer.files) { if (/\.srt$/i.test(file.name)) srtFile.files = event.dataTransfer.files; else if (file.type.startsWith('video/')) videoFile.files = event.dataTransfer.files; } };


const apiEndpoint = $('#apiEndpoint');
apiEndpoint.value = backendUrl('/api/generate-audio');
const apiTts = $('#apiTts');
const apiLang = $('#apiLang');
const apiVoice = $('#apiVoice');
const languageName = (code, names = {}) => names[code] || code.toUpperCase();
let availableTts = [];
let apiLanguageNames = {};
function setAvailableLanguages(languages, languageNames) {
  const previous = apiLang.value;
  if (!languages.length) return;
  apiLang.replaceChildren(...languages.map(code => new Option(languageName(code, languageNames), code)));
  apiLang.value = languages.includes(previous) ? previous : languages.includes('es') ? 'es' : languages[0];
}
function renderTtsForLanguage() {
  const previous = apiTts.value;
  const compatible = availableTts.filter(engine => engine.languages.includes(apiLang.value));
  if (!compatible.length) {
    apiTts.replaceChildren(new Option('No hay TTS instalado para este idioma', ''));
    apiTts.disabled = true;
    return;
  }
  apiTts.replaceChildren(...compatible.map(engine => {
    const state = engine.offline ? 'sin conexión' : 'requiere Internet';
    const voices = engine.voices?.filter(voice => voice.language === apiLang.value).length || 0;
    const detail = voices ? ` · ${voices} voces instaladas` : '';
    return new Option(`${engine.label} (${state}${detail})`, engine.id);
  }));
  apiTts.value = compatible.some(engine => engine.id === previous) ? previous : compatible[0].id;
  apiTts.disabled = false;
  renderVoicesForTts();
}
function renderVoicesForTts() {
  const engine = availableTts.find(item => item.id === apiTts.value);
  const voices = engine?.voices?.filter(voice => voice.language === apiLang.value) || [];
  if (!voices.length) {
    apiVoice.replaceChildren(new Option('El TTS usa su voz predeterminada', ''));
    apiVoice.disabled = true;
    return;
  }
  apiVoice.replaceChildren(...voices.map(voice => new Option(`${voice.name} (${voice.locale})`, voice.id)));
  apiVoice.disabled = false;
}
async function loadAvailableTts() {
  apiTts.disabled = true;
  apiTts.replaceChildren(new Option('Cargando TTS instalados…', ''));
  try {
    const url = new URL('/api/tts', apiEndpoint.value || location.origin);
    const response = await fetch(url);
    const {tts = [], languages = [], language_names: languageNames = {}} = await response.json();
    if (!response.ok || !tts.length) throw new Error('No hay TTS disponibles');
    availableTts = tts;
    apiLanguageNames = languageNames;
    setAvailableLanguages(languages, apiLanguageNames);
    renderTtsForLanguage();
    apiLang.onchange = renderTtsForLanguage;
    apiTts.onchange = renderVoicesForTts;
  } catch (error) {
    apiTts.replaceChildren(new Option('No se pudieron cargar los TTS', ''));
  }
}
apiEndpoint.addEventListener('change', loadAvailableTts);
async function refreshBackend() {
  const previousApiEndpoint = apiEndpoint.value;
  const oldDefault = new URL('/api/generate-audio', activeBackendBase || location.origin).toString();
  try {
    const info = await fetch(backendUrl('/info')).then(response => response.ok ? response.json() : Promise.reject());
    $('#appVersion').textContent = `v${info.version}`;
    $('#appVersion').hidden = false;
    const files = await fetch(backendUrl('/files')).then(response => response.json());
    delete srtFile.dataset.local;
    delete videoFile.dataset.local;
    localSrt.replaceChildren(new Option('SRT de esta carpeta…', '')); populate(localSrt, files.srt || []);
    localVideo.replaceChildren(new Option('Video de esta carpeta…', '')); populate(localVideo, files.video || []);
    const options = await fetch(backendUrl('/options')).then(response => response.json());
    renderOptions(options);
    if (!previousApiEndpoint || previousApiEndpoint === oldDefault) apiEndpoint.value = backendUrl('/api/generate-audio');
    activeBackendBase = backendBase.value;
    await loadAvailableTts();
  } catch (error) {
    logs.textContent = 'No se pudo conectar al backend seleccionado. Verificá la URL y CORS.';
    $('#appVersion').hidden = true;
  }
}
backendBase.addEventListener('change', refreshBackend);
$('#reloadBackend').onclick = refreshBackend;
refreshBackend();
$('#apiTestForm').onsubmit = async event => {
  event.preventDefault();
  const result = $('#apiResult');
  result.textContent = 'Generando audio…';
  const payload = {
    lang: $('#apiLang').value,
    tts: apiTts.value || undefined,
    voice: apiVoice.value || undefined,
    rate: Number($('#apiRate').value || 180),
    fixed_rate: $('#apiFixedRate').checked,
    duration: $('#apiDuration').value || undefined,
    pause_ms: Number($('#apiPause').value || 0),
  };
  const file = $('#apiSrtFile').files[0];
  if (file) payload.srt_file = await readFile(file);
  else if ($('#apiTextIsSrt').checked) payload.srt_text = $('#apiText').value;
  else payload.text = $('#apiText').value;
  try {
    const response = await fetch(apiEndpoint.value, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const generated = await response.json();
    if (!response.ok) throw new Error(generated.error || 'No se pudo generar audio');
    const meta = document.createElement('p');
    meta.textContent = `TTS: ${generated.tts_used}${generated.voice_used ? ` · Voz: ${generated.voice_used}` : ''} · Idioma: ${generated.language} · Rate: ${generated.rate} ppm · Duración: ${generated.duration.toFixed(3)} s`;
    const audio = document.createElement('audio'); audio.controls = true; audio.src = generated.audio.url;
    const link = document.createElement('a'); link.href = generated.audio.url; link.download = generated.audio.name; link.textContent = 'Descargar audio';
    result.replaceChildren(meta, audio, link);
  } catch (error) { result.textContent = `Error: ${error.message}`; }
};
