const $ = selector => document.querySelector(selector);
const logs = $('#o');
const progress = $('#progress');
const progressLabel = $('#progressLabel');
const favicon = $('#favicon');
const srtFile = $('#srtFile');
const videoFile = $('#videoFile');
const localSrt = $('#localSrt');
const localVideo = $('#localVideo');
const backendBase = $('#backendBase');
const tempDirectory = $('#tempDirectory');
const uiLanguage = $('#uiLanguage');
const themeToggle = $('#themeToggle');
const resetPreferences = $('#resetPreferences');
backendBase.value = location.origin;
let activeBackendBase = backendBase.value;
const backendUrl = path => new URL(path, backendBase.value || location.origin).toString();
const backendFileUrl = url => new URL(url, backendBase.value || location.origin).toString();
const outputFiles = () => $('#results');
let existingResults = [];
let backendOptions = [];
const selectedResultUrls = new Set();
const notesButton = $('#notesButton');
const notesCount = $('#notesCount');
const notesDialog = $('#notesDialog');
const notesEditor = $('#notesEditor');
const notesStatus = $('#notesStatus');
const audioExtensions = new Set(['wav', 'aac', 'mp3', 'ogg', 'm4a']);
const videoExtensions = new Set(['mp4', 'mkv', 'mov', 'avi', 'webm']);
const isMinimalMode = new URLSearchParams(location.search).get('mode') === 'minimal';
if (isMinimalMode) {
  document.body.classList.add('minimal');
  const minimalLink = $('#minimalMode');
  minimalLink.href = '/'; minimalLink.textContent = '↗ Vista avanzada';
}
const subtitleProgress = output => [...output.matchAll(/Subtítulo\s+(\d+)\/(\d+)/gi)].pop();
const storageGet = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
const storageSet = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
const PREFERENCES_KEY = 'videoTtsPreferences';
const readPreferences = () => { try { return JSON.parse(storageGet(PREFERENCES_KEY) || '{}'); } catch (_) { return {}; } };
const controlKey = control => control.id ? `#${control.id}` : control.name ? `name:${control.name}` : '';
function savePreferences() {
  const controls = {};
  document.querySelectorAll('input, select, textarea, details').forEach(control => {
    if (control.type === 'file') return;
    const key = controlKey(control);
    if (!key) return;
    controls[key] = control.tagName === 'DETAILS' ? control.open : control.type === 'checkbox' ? control.checked : control.value;
  });
  storageSet(PREFERENCES_KEY, JSON.stringify({controls}));
}
function restorePreferences() {
  const {controls = {}} = readPreferences();
  document.querySelectorAll('input, select, textarea, details').forEach(control => {
    if (control.type === 'file') return;
    const key = controlKey(control);
    if (!key || !(key in controls)) return;
    const value = controls[key];
    if (control.tagName === 'DETAILS') control.open = Boolean(value);
    else if (control.type === 'checkbox') control.checked = Boolean(value);
    else if (control.tagName !== 'SELECT' || [...control.options].some(option => option.value === value)) control.value = value;
  });
}

const interfaceText = {
  en: {tagline: 'Generate, review and synchronize your audio.', notes: '📝 Notes', process: '✨ Process', subtitles: '📝 Subtitles', language: '🌐 Language', test: '🧪 Test mode · Entries:', reuse: '♻️ Reuse temporary audio', noReuse: 'Do not reuse audio…', minimal: '🪶 Minimal view', connect: 'Connect', reset: '↺ Reset', results: '✨ Results', resultHelp: 'Select an audio, video or SRT to open it in the synced viewer.', selectAll: '☑️ Select all', deselectAll: '☐ Deselect all', downloadSelected: '⬇️ Download selected', deleteSelected: '🗑️ Delete selected', deleteTempFolders: '🧹 Delete temporary folders', selected: count => `${count} selected`, viewer: 'Viewer:', synced: '📝 Synced subtitles', chooseSrt: '📝 Select an SRT file to view its cues', subtitleViewer: '📝 Subtitles:', folderSrt: 'SRT from this folder…', folderVideo: 'Video from this folder…', open: 'Open', download: 'Download', delete: 'Delete', rate: 'Rate', pause: 'Pause between lines (ms)'},
  es: {tagline: 'Generá, revisá y sincronizá tu audio.', notes: '📝 Notas', process: '✨ Procesar', subtitles: '📝 Subtítulos', language: '🌐 Idioma', test: '🧪 Modo test · Entradas:', reuse: '♻️ Reutilizar audio temporal', noReuse: 'No reutilizar audio…', minimal: '🪶 Vista mínima', connect: 'Conectar', reset: '↺ Restablecer', results: '✨ Resultados', resultHelp: 'Seleccioná un audio, video o SRT para abrirlo en el visor sincronizado.', selectAll: '☑️ Seleccionar todo', deselectAll: '☐ Deseleccionar todo', downloadSelected: '⬇️ Descargar seleccionados', deleteSelected: '🗑️ Borrar seleccionados', deleteTempFolders: '🧹 Eliminar carpetas temporales', selected: count => `${count} seleccionado${count === 1 ? '' : 's'}`, viewer: 'Visor:', synced: '📝 Subtítulos sincronizados', chooseSrt: '📝 Elegí un archivo SRT para ver sus cues', subtitleViewer: '📝 Subtítulos:', folderSrt: 'SRT de esta carpeta…', folderVideo: 'Video de esta carpeta…', open: 'Abrir', download: 'Descargar', delete: 'Borrar', rate: 'Rate', pause: 'Pausa entre líneas (ms)'}
};
const tr = key => (interfaceText[uiLanguage?.value || 'en'] || interfaceText.en)[key] || key;
function applyInterfaceLanguage(language = 'en') {
  const text = interfaceText[language] || interfaceText.en;
  document.documentElement.lang = language;
  const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  setText('#appTagline', text.tagline);
  if (notesButton?.firstChild) notesButton.firstChild.textContent = `${text.notes} `;
  setText('#f button[type="submit"]', text.process);
  setText('#f fieldset:first-of-type legend', text.subtitles);
  const languageLabel = $('#f label select[name="lang"]')?.parentElement;
  if (languageLabel?.firstChild) languageLabel.firstChild.textContent = text.language + ' ';
  const testLabel = $('#f .test-option');
  if (testLabel?.childNodes[2]) testLabel.childNodes[2].textContent = ` ${text.test} `;
  if (tempDirectory?.parentElement?.firstChild) tempDirectory.parentElement.firstChild.textContent = text.reuse + ' ';
  if (tempDirectory?.options?.[0]) tempDirectory.options[0].textContent = text.noReuse;
  if (!isMinimalMode) setText('#minimalMode', text.minimal);
  setText('#reloadBackend', text.connect);
  setText('#resetPreferences', text.reset);
  if (backendOptions.length) renderOptions(backendOptions);
  if (existingResults.length) void renderResults(existingResults);
  storageSet('videoTtsLanguage', language);
}
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  if (themeToggle) themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  storageSet('videoTtsTheme', theme);
}
const savedLanguage = storageGet('videoTtsLanguage') || 'en';
if (uiLanguage) uiLanguage.value = savedLanguage;
restorePreferences();
activeBackendBase = backendBase.value;
applyInterfaceLanguage(uiLanguage?.value || savedLanguage);
applyTheme(storageGet('videoTtsTheme') || 'light');
if (uiLanguage) uiLanguage.onchange = () => applyInterfaceLanguage(uiLanguage.value);
if (themeToggle) themeToggle.onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
if (resetPreferences) resetPreferences.onclick = () => {
  try { localStorage.removeItem(PREFERENCES_KEY); localStorage.removeItem('videoTtsLanguage'); localStorage.removeItem('videoTtsTheme'); } catch (_) {}
  location.reload();
};
document.addEventListener('input', savePreferences);
document.addEventListener('change', savePreferences);

function setFaviconProgress(percent) {
  const value = Number.isFinite(percent) ? Math.max(0, Math.min(100, Math.round(percent))) : null;
  const url = value === null ? '/favicon.svg' : `/favicon.svg?progress=${value}&v=${Date.now()}`;
  favicon.href = url;
}

function setNotesCount(count) { notesCount.textContent = String(count || 0); }
async function loadNotes() {
  notesStatus.textContent = 'Cargando notas…';
  try {
    const response = await fetch(backendUrl('/notes'));
    const notes = await response.json();
    if (!response.ok) throw new Error(notes.error || 'No se pudieron cargar las notas');
    notesEditor.value = notes.content || ''; setNotesCount(notes.count); notesStatus.textContent = notes.tracked ? 'Archivo notas.txt con seguimiento local.' : 'Todavía no hay notas guardadas.';
  } catch (error) { notesStatus.textContent = `Error: ${error.message}`; }
}
notesButton.onclick = async () => { notesDialog.showModal(); await loadNotes(); };
$('#closeNotes').onclick = () => notesDialog.close();
$('#addTaskNote').onclick = () => {
  const prefix = notesEditor.value && !notesEditor.value.endsWith('\n') ? '\n' : '';
  notesEditor.setRangeText(`${prefix}- [ ] `, notesEditor.selectionStart, notesEditor.selectionEnd, 'end'); notesEditor.focus();
};
$('#saveNotes').onclick = async () => {
  notesStatus.textContent = 'Guardando…';
  try {
    const response = await fetch(backendUrl('/notes'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: notesEditor.value})});
    const notes = await response.json();
    if (!response.ok) throw new Error(notes.error || 'No se pudieron guardar las notas');
    setNotesCount(notes.count); notesStatus.textContent = notes.github?.message || 'Notas guardadas.';
  } catch (error) { notesStatus.textContent = `Error: ${error.message}`; }
};

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
  title.textContent = `${tr('subtitleViewer')} ${subtitle.name}`;
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
  title.textContent = `${iconFor(media)} ${tr('viewer')} ${media.name}`;
  const player = document.createElement(fileKind(media) === 'video' ? 'video' : 'audio');
  player.controls = true;
  player.preload = 'metadata';
  player.src = media.url;
  const subtitleTitle = document.createElement('h3');
  subtitleTitle.textContent = cues.length ? tr('synced') : tr('chooseSrt');
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
  title.textContent = tr('results');
  const help = document.createElement('p');
  help.className = 'result-help';
  help.textContent = tr('resultHelp');
  const bulkActions = document.createElement('div');
  bulkActions.className = 'bulk-actions';
  const selectionCount = document.createElement('span');
  const selectAll = document.createElement('button');
  selectAll.type = 'button'; selectAll.textContent = tr('selectAll');
  const downloadSelected = document.createElement('button');
  downloadSelected.type = 'button'; downloadSelected.textContent = tr('downloadSelected');
  const deleteSelected = document.createElement('button');
  deleteSelected.type = 'button'; deleteSelected.textContent = tr('deleteSelected'); deleteSelected.className = 'delete-action';
  const deleteTempFolders = document.createElement('button');
  deleteTempFolders.type = 'button'; deleteTempFolders.textContent = tr('deleteTempFolders'); deleteTempFolders.className = 'delete-action';
  const selectedFiles = () => files.filter(file => file.deletable && selectedResultUrls.has(file.url));
  const updateBulkActions = () => {
    const count = selectedFiles().length;
    selectionCount.textContent = tr('selected')(count);
    downloadSelected.disabled = !count; deleteSelected.disabled = !count;
    const selectable = files.filter(file => file.deletable);
    selectAll.textContent = selectable.length && count === selectable.length ? tr('deselectAll') : tr('selectAll');
    selectAll.disabled = !selectable.length;
  };
  selectAll.onclick = () => {
    const selectable = files.filter(file => file.deletable);
    const allSelected = selectable.length && selectable.every(file => selectedResultUrls.has(file.url));
    selectable.forEach(file => allSelected ? selectedResultUrls.delete(file.url) : selectedResultUrls.add(file.url));
    renderResults(files);
  };
  downloadSelected.onclick = () => {
    const query = new URLSearchParams();
    selectedFiles().forEach(file => query.append('name', file.name));
    const link = document.createElement('a');
    link.href = backendUrl(`/download?${query}`); link.download = 'video-tts-resultados.zip'; link.click();
  };
  deleteSelected.onclick = async () => {
    const selected = selectedFiles();
    if (!selected.length || !confirm(`¿Borrar ${selected.length} archivo(s) seleccionado(s)?`)) return;
    const responses = await Promise.all(selected.map(file => fetch(backendUrl('/delete'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: file.name})})));
    if (responses.some(response => !response.ok)) { logs.textContent = 'No se pudieron borrar todos los archivos seleccionados.'; return; }
    selected.forEach(file => selectedResultUrls.delete(file.url));
    existingResults = existingResults.filter(file => !selected.some(candidate => candidate.name === file.name));
    renderResults(files.filter(file => !selected.some(candidate => candidate.name === file.name)));
  };
  deleteTempFolders.onclick = async () => {
    if (!confirm('¿Eliminar todas las carpetas temp_* de este backend? Esta acción no se puede deshacer.')) return;
    try {
      const response = await fetch(backendUrl('/delete-temp-folders'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'No se pudieron eliminar las carpetas temporales');
      logs.textContent = result.count ? `🧹 Se eliminaron ${result.count} carpeta(s) temporal(es).` : '🧹 No había carpetas temporales para eliminar.';
    } catch (error) { logs.textContent = `Error: ${error.message}`; }
  };
  bulkActions.append(selectionCount, selectAll, downloadSelected, deleteSelected, deleteTempFolders);
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
    if (file.deletable) {
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.checked = selectedResultUrls.has(file.url); checkbox.setAttribute('aria-label', `${tr('selectAll')}: ${file.name}`);
      checkbox.onchange = () => { if (checkbox.checked) selectedResultUrls.add(file.url); else selectedResultUrls.delete(file.url); updateBulkActions(); };
      item.append(checkbox);
    }
    const name = resultLink(`${iconFor(file)} ${file.name}`, 'file-name', async () => {
      if (fileKind(file) === 'subtitle') selectedSubtitle = file;
      else if (fileKind(file) === 'audio' || fileKind(file) === 'video') selectedMedia = file;
      await updateViewer(); viewer.scrollIntoView({behavior: 'smooth', block: 'start'});
    });
    const open = document.createElement('a');
    open.href = file.url; open.target = '_blank'; open.rel = 'noopener'; open.textContent = '↗️'; open.title = tr('open'); open.setAttribute('aria-label', tr('open')); open.className = 'result-action';
    const download = document.createElement('a');
    download.href = file.url; download.download = file.name; download.textContent = '⬇️'; download.title = tr('download'); download.setAttribute('aria-label', tr('download')); download.className = 'result-action';
    item.append(name, open, download);
    if (file.deletable) {
      const remove = document.createElement('button');
      remove.type = 'button'; remove.textContent = '🗑️'; remove.title = tr('delete'); remove.setAttribute('aria-label', `${tr('delete')} ${file.name}`); remove.className = 'result-action delete-action';
      remove.onclick = async () => {
        if (!confirm(`¿Borrar ${file.name}?`)) return;
        const response = await fetch(backendUrl('/delete'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: file.name})});
        const result = await response.json();
        if (!response.ok) { logs.textContent = `Error: ${result.error || 'No se pudo borrar el archivo'}`; return; }
        existingResults = existingResults.filter(candidate => candidate.name !== file.name);
        selectedResultUrls.delete(file.url);
        renderResults(files.filter(candidate => candidate.name !== file.name));
      };
      item.append(remove);
    }
    list.append(item);
  });
  updateBulkActions();
  section.append(title, help, bulkActions, list, viewer);
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
    const percent = Number(current) / Number(total) * 100;
    progressLabel.textContent = `⏳ Subtítulo ${current}/${total} · ${Math.round(percent)}%`;
    setFaviconProgress(percent);
  }
  if (!status.done) return setTimeout(() => poll(id), 700);
  progressLabel.textContent = match ? progressLabel.textContent : '✅ Procesamiento finalizado';
  setFaviconProgress(null);
  const jobResults = (status.files || []).map(file => ({...file, url: backendFileUrl(file.url), deletable: true}));
  renderResults([...existingResults, ...jobResults]);
}

function selectedOrUploaded(input) { return input.dataset.local ? {local: input.dataset.local} : readFile(input.files[0]); }
$('#f').onsubmit = async event => {
  event.preventDefault();
  const srt = await selectedOrUploaded(srtFile);
  const youtube = event.currentTarget.elements.youtube.value.trim();
  const continueFrom = tempDirectory?.value || '';
  if (!srt && !youtube && !continueFrom) { logs.textContent = 'Select an SRT, YouTube URL or temporary folder.'; return; }
  progress.max = 1; progress.value = 0; progressLabel.textContent = '⏳ Preparando procesamiento…';
  setFaviconProgress(0);
  const options = Object.fromEntries(new FormData(event.currentTarget));
  ['solo_audio', 'no_truncate', 'optimize_rate', 'fix_rate_not_truncate', 'no_freeze', 'remove_breaks', 'only_remove_breaks', 'test'].forEach(key => { options[key] = options[key] === 'on'; });
  options.fix_rate_not_truncate_rate = Number(options.fix_rate_not_truncate_rate || 200);
  options.fix_rate_not_truncate_pause = Number(options.fix_rate_not_truncate_pause || 1000);
  options.test_count = Number(options.test_count || 30);
  const selectedVideo = await selectedOrUploaded(videoFile);
  if (options.fix_rate_not_truncate && (selectedVideo || youtube)) { logs.textContent = 'Plain audio mode can only be used without video.'; return; }
  const response = await fetch(backendUrl('/run'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({srt, video: selectedVideo, opts: options})});
  const job = await response.json();
  if (!job.id) { logs.textContent = 'Error: ' + (job.error || 'No se pudo crear el trabajo'); setFaviconProgress(null); return; }
  poll(job.id);
};

function populate(select, names) { names.forEach(name => select.add(new Option(name, name))); }
const shellQuote = value => /^[\w./:-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
function updateCliCommand() {
  const form = new FormData($('#f'));
  const srt = localSrt.value || srtFile.files[0]?.name || '<archivo.srt>';
  const video = localVideo.value || videoFile.files[0]?.name;
  const fixedRate = form.get('fix_rate_not_truncate') === 'on';
  const youtube = form.get('youtube')?.trim();
  const continueFrom = form.get('continue_from');
  const args = ['python3', 'create_video_tts_from_srt.py'];
  if (youtube) args.push('--youtube', youtube);
  else if (continueFrom) args.push('--continue', continueFrom);
  else { args.push(srt); if (video && !fixedRate) args.push(video); }
  args.push('--lang', form.get('lang') || 'es');
  if (form.get('tts')) args.push('--tts', form.get('tts'));
  if (form.get('voice')) args.push('--voice', form.get('voice'));
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
  const labelText = uiLanguage?.value === 'es' ? option.label_es || option.label : option.label_en || option.label;
  label.append(input, ` ⚙️ ${labelText}`);
  if (option.rate_name) {
    const rate = document.createElement('input');
    rate.name = option.rate_name; rate.type = 'number'; rate.min = '80'; rate.max = '400'; rate.step = '1'; rate.value = option.default || 200;
    rate.setAttribute('aria-label', `${tr('rate')} (ppm)`);
    label.append(` · ${tr('rate')}: `, rate, ' ppm');
  }
  if (option.pause_name) {
    const pause = document.createElement('input');
    pause.name = option.pause_name; pause.type = 'number'; pause.min = '0'; pause.step = '100'; pause.value = option.pause_default || 1000;
    pause.setAttribute('aria-label', tr('pause'));
    label.append(` · ${tr('pause')}: `, pause);
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
const mainTts = $('#mainTts');
const mainVoice = $('#mainVoice');
const mainLang = $('#f select[name="lang"]');
const apiVoiceTest = $('#apiVoiceTest');
const mainVoiceTest = $('#mainVoiceTest');
const voiceTestText = language => ({
  es: 'Esta es una breve prueba de voz para Video TTS.',
  en: 'This is a short voice sample for Video TTS.',
  de: 'Dies ist eine kurze Sprachprobe für Video TTS.',
  fr: 'Ceci est un court échantillon vocal pour Video TTS.',
  it: 'Questo è un breve esempio vocale per Video TTS.',
  pt: 'Este é um breve exemplo de voz para Video TTS.',
}[language] || 'This is a short voice sample for Video TTS.');
const voiceLanguage = voice => String(voice.language || voice.locale || '').toLowerCase().split(/[-_]/)[0];
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
  const voices = engine?.voices?.filter(voice => voiceLanguage(voice) === apiLang.value) || [];
  if (!voices.length) {
    apiVoice.replaceChildren(new Option('El TTS usa su voz predeterminada', ''));
    apiVoice.disabled = true;
    apiVoiceTest.disabled = !engine;
    return;
  }
  apiVoice.replaceChildren(...voices.map(voice => new Option(`${voice.name} (${voice.locale})`, voice.id)));
  apiVoice.disabled = false;
  apiVoiceTest.disabled = false;
}
function renderMainTts() {
  if (!mainTts || !mainVoice) return;
  const previous = mainTts.value;
  const compatible = availableTts.filter(engine => engine.languages.includes(mainLang.value));
  if (!compatible.length) {
    mainTts.replaceChildren(new Option('No installed TTS for this language', ''));
    mainTts.disabled = true;
    renderMainVoices();
    return;
  }
  mainTts.replaceChildren(...compatible.map(engine => new Option(engine.label, engine.id)));
  mainTts.value = compatible.some(engine => engine.id === previous) ? previous : compatible[0].id;
  mainTts.disabled = false;
  renderMainVoices();
}
function renderMainVoices() {
  if (!mainVoice) return;
  const engine = availableTts.find(item => item.id === mainTts.value);
  const voices = engine?.voices?.filter(voice => voiceLanguage(voice) === mainLang.value) || [];
  if (!voices.length) {
    mainVoice.replaceChildren(new Option('Default TTS voice', ''));
    mainVoice.disabled = true;
    mainVoiceTest.disabled = !engine;
    updateCliCommand();
    return;
  }
  mainVoice.replaceChildren(...voices.map(voice => new Option(`${voice.name} (${voice.locale})`, voice.id)));
  mainVoice.disabled = false;
  mainVoiceTest.disabled = false;
  updateCliCommand();
}
async function testVoice({tts, voice, lang}, button) {
  const original = button.textContent;
  button.disabled = true; button.textContent = '⏳ Testing voice…';
  try {
    const response = await fetch(apiEndpoint.value, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: voiceTestText(lang), lang, tts: tts || undefined, voice: voice || undefined, rate: 180, fixed_rate: true, pause_ms: 0})});
    const generated = await response.json();
    if (!response.ok) throw new Error(generated.error || 'Could not generate voice test');
    const audio = new Audio(new URL(generated.audio.url, apiEndpoint.value).toString());
    audio.play().catch(() => {});
  } catch (error) { logs.textContent = `Error: ${error.message}`; }
  finally { button.disabled = false; button.textContent = original; }
}
apiVoiceTest.onclick = () => testVoice({tts: apiTts.value, voice: apiVoice.disabled ? undefined : apiVoice.value, lang: apiLang.value}, apiVoiceTest);
mainVoiceTest.onclick = () => testVoice({tts: mainTts.value, voice: mainVoice.disabled ? undefined : mainVoice.value, lang: mainLang.value}, mainVoiceTest);
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
    renderMainTts();
    apiLang.onchange = renderTtsForLanguage;
    apiTts.onchange = renderVoicesForTts;
    mainLang.onchange = () => { renderMainTts(); updateCliCommand(); };
    mainTts.onchange = () => { renderMainVoices(); updateCliCommand(); };
    mainVoice.onchange = updateCliCommand;
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
    localSrt.replaceChildren(new Option(tr('folderSrt'), '')); populate(localSrt, files.srt || []);
    localVideo.replaceChildren(new Option(tr('folderVideo'), '')); populate(localVideo, files.video || []);
    if (tempDirectory) tempDirectory.replaceChildren(new Option(interfaceText[uiLanguage?.value || 'en'].noReuse, ''), ...(files.temp_dirs || []).map(name => new Option(name, name)));
    existingResults = (files.results || []).map(file => ({...file, url: backendFileUrl(file.url)}));
    await renderResults(existingResults);
    backendOptions = await fetch(backendUrl('/options')).then(response => response.json());
    renderOptions(backendOptions);
    if (!previousApiEndpoint || previousApiEndpoint === oldDefault) apiEndpoint.value = backendUrl('/api/generate-audio');
    activeBackendBase = backendBase.value;
    await loadAvailableTts();
    restorePreferences();
    renderVoicesForTts();
    renderMainVoices();
    restorePreferences();
    updateCliCommand();
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
