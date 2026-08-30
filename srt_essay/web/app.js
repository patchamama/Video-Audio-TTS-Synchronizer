const form = document.querySelector('#form');
const file = document.querySelector('#source');
const localSource = document.querySelector('#local-source');
const fileName = document.querySelector('#file-name');
const localSourcePath = document.querySelector('#local-source-path');
const localSourceLink = document.querySelector('#local-source-link');
const status = document.querySelector('#status');
const progress = document.querySelector('#progress');
const percent = document.querySelector('#percent');
const state = document.querySelector('#state');
const logs = document.querySelector('#logs');
const markdownPreview = document.querySelector('#markdown-preview');
const download = document.querySelector('#download');
const submit = document.querySelector('#submit');
const debug = document.querySelector('#debug');
const artifacts = document.querySelector('#artifacts');
const debugPanel = document.querySelector('#debug-panel');
const comparisonPanel = document.querySelector('#comparison-panel');
const comparisons = document.querySelector('#comparisons');
const generateAudio = document.querySelector('#generate-audio');
const generateInputAudio = document.querySelector('#generate-input-audio');
const audioSource = document.querySelector('#audio-source');
const audioLang = document.querySelector('#audio-lang');
const audioTts = document.querySelector('#audio-tts');
const ttsStatus = document.querySelector('#tts-status');
const audioVoice = document.querySelector('#audio-voice');
const testVoice = document.querySelector('#test-voice');
const voiceTestResult = document.querySelector('#voice-test-result');
const voiceTestText = document.querySelector('#voice-test-text');
const voiceTestPlayer = document.querySelector('#voice-test-player');
const audioRate = document.querySelector('#audio-rate');
const audioPause = document.querySelector('#audio-pause');
const audioMergeBatchSize = document.querySelector('#audio-merge-batch-size');
const audioTestFragments = document.querySelector('#audio-test-fragments');
const audioSplitChapters = document.querySelector('#audio-split-chapters');
const audioResult = document.querySelector('#audio-result');
const audioList = document.querySelector('#audio-list');
const audioCacheStatus = document.querySelector('#audio-cache-status');
const checkAudioCache = document.querySelector('#check-audio-cache');
const deleteAudioCache = document.querySelector('#delete-audio-cache');
let inputRoot = '';
const workspacePanel = document.querySelector('#workspace-panel');
const workspacePath = document.querySelector('#workspace-path');
const workspaceLink = document.querySelector('#workspace-link');
const openWorkspace = document.querySelector('#open-workspace');
const resumeAudio = document.querySelector('#resume-audio');
let comparisonSignature = '';
const automaticallyDownloaded = new Set();
const model = document.querySelector('#model');
const provider = document.querySelector('#provider');
const providerStatus = document.querySelector('#provider-status');
const ollamaUrlField = document.querySelector('#ollama-url-field');
const ollamaUrl = document.querySelector('#ollama-url');
const savePromptsButton = document.querySelector('#save-prompts');
const newPromptProfileButton = document.querySelector('#new-prompt-profile');
const promptStatus = document.querySelector('#prompt-status');
const promptProfile = document.querySelector('#prompt-profile');
const promptLabel = document.querySelector('#prompt-label');
const promptTestText = document.querySelector('#prompt-test-text');
const testPromptButton = document.querySelector('#test-prompt');
const promptTestStatus = document.querySelector('#prompt-test-status');
const promptTestResult = document.querySelector('#prompt-test-result');
const preferencesKey = 'srtEssayPreferences';
const preferenceControls = ['provider', 'ollama-url', 'mode', 'chunk-size', 'debug', 'prompt-profile', 'rewrite-system-prompt', 'rewrite-instructions', 'guide-instructions', 'prompt-test-text', 'local-source', 'generate-audio', 'audio-source', 'audio-lang', 'audio-tts', 'audio-voice', 'audio-rate', 'audio-pause', 'audio-merge-batch-size', 'audio-test-fragments', 'audio-split-chapters'];
const storageGet = () => { try { return JSON.parse(localStorage.getItem(preferencesKey) || '{}'); } catch (_) { return {}; } };
const storedPreferences = storageGet();
function restorePreferences() {
  preferenceControls.forEach(id => {
    const control = document.querySelector(`#${id}`); const value = storedPreferences[id];
    if (!control || value === undefined || (control.tagName === 'SELECT' && ![...control.options].some(option => option.value === value))) return;
    if (control.type === 'checkbox') control.checked = Boolean(value); else control.value = value;
  });
}
function savePreferences() {
  const values = {model: model.value};
  preferenceControls.forEach(id => {
    const control = document.querySelector(`#${id}`);
    if (control) values[id] = control.type === 'checkbox' ? control.checked : control.value;
  });
  try { localStorage.setItem(preferencesKey, JSON.stringify(values)); } catch (_) {}
}
restorePreferences();

let promptProfiles = {};
const promptPayload = () => ({
  profile_id: promptProfile.value,
  label: promptLabel.value,
  rewrite_system_prompt: document.querySelector('#rewrite-system-prompt').value,
  rewrite_instructions: document.querySelector('#rewrite-instructions').value,
  guide_instructions: document.querySelector('#guide-instructions').value,
});
function applyPromptProfile(profileId) {
  const profile = promptProfiles[profileId]; if (!profile) return;
  promptProfile.value = profileId; promptLabel.value = profile.label;
  document.querySelector('#rewrite-system-prompt').value = profile.rewrite_system_prompt;
  document.querySelector('#rewrite-instructions').value = profile.rewrite_instructions;
  document.querySelector('#guide-instructions').value = profile.guide_instructions;
  savePreferences();
}
function renderPromptProfiles(document, preferredProfile) {
  promptProfiles = document.profiles || {}; promptProfile.replaceChildren();
  Object.entries(promptProfiles).forEach(([id, profile]) => promptProfile.add(new Option(profile.label, id)));
  const preferred = preferredProfile || storedPreferences['prompt-profile'];
  const selected = preferred in promptProfiles ? preferred : document.active_profile;
  applyPromptProfile(selected);
}
async function loadPrompts() {
  try {
    const response = await fetch('/api/prompts'); const document = await response.json();
    if (!response.ok) throw new Error(document.error || 'No se pudieron cargar los prompts');
    renderPromptProfiles(document);
    savePreferences();
  } catch (error) { promptStatus.textContent = `Error al cargar prompts: ${error.message}`; }
}
async function savePrompts() {
  promptStatus.textContent = 'Guardando prompts…'; savePromptsButton.disabled = true;
  try {
    const response = await fetch('/api/prompts', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(promptPayload())});
    const document = await response.json(); if (!response.ok) throw new Error(document.error || 'No se pudieron guardar los prompts');
    renderPromptProfiles(document);
    savePreferences(); promptStatus.textContent = 'Prompts guardados en .srt-essay-prompts.json.';
    return true;
  } catch (error) { promptStatus.textContent = `Error: ${error.message}`; }
  finally { savePromptsButton.disabled = false; }
  return false;
}
savePromptsButton.addEventListener('click', savePrompts);
promptProfile.addEventListener('change', () => applyPromptProfile(promptProfile.value));
newPromptProfileButton.addEventListener('click', () => {
  const label = window.prompt('Nombre del nuevo perfil:', 'Nuevo perfil'); if (!label?.trim()) return;
  const id = `personalizado-${Date.now()}`;
  promptProfiles[id] = {...promptPayload(), label: label.trim()};
  promptProfile.add(new Option(label.trim(), id)); applyPromptProfile(id); promptStatus.textContent = 'Editá el perfil y guardalo en backend.';
});
void loadPrompts();

function clearLocalSourceInfo() {
  localSourcePath.hidden = true; localSourcePath.textContent = '';
  localSourceLink.hidden = true; localSourceLink.removeAttribute('href');
}
function renderLocalSourceInfo(source) {
  if (!source?.path) { clearLocalSourceInfo(); return; }
  fileName.textContent = `Archivo local: ${localSource.value}`;
  localSourcePath.textContent = source.path; localSourcePath.hidden = false;
  localSourceLink.href = source.uri; localSourceLink.hidden = false;
}
function renderCheckedAudioCache(payload) {
  const caches = payload.caches || []; const fragments = Number(payload.fragments || 0);
  if (!fragments) { audioCacheStatus.textContent = 'No se encontró caché de audio reutilizable para este archivo y velocidad.'; audioCacheStatus.hidden = false; return; }
  audioCacheStatus.replaceChildren(document.createTextNode(`Caché encontrada: ${fragments} archivo${fragments === 1 ? '' : 's'}. `));
  caches.forEach((cache, index) => {
    if (index) audioCacheStatus.append(document.createTextNode(' · '));
    const link = document.createElement('a'); link.href = cache.uri; link.target = '_blank'; link.rel = 'noopener'; link.textContent = cache.path;
    audioCacheStatus.append(link, document.createTextNode(` (${cache.fragments} archivo${cache.fragments === 1 ? '' : 's'}). `));
    (cache.chapters || []).forEach(item => audioCacheStatus.append(document.createTextNode(`Capítulo ${item.chapter}: continuar desde fragmento ${item.next_fragment}. `)));
  });
  audioCacheStatus.hidden = false;
}
async function checkSelectedAudioCache() {
  if (!localSource.value) { audioCacheStatus.textContent = 'Seleccioná un archivo local para revisar su caché.'; audioCacheStatus.hidden = false; return; }
  checkAudioCache.disabled = true; checkAudioCache.textContent = 'Revisando…';
  try {
    const response = await fetch(`/api/audio-cache?source_path=${encodeURIComponent(localSource.value)}&rate=${encodeURIComponent(audioRate.value || 200)}`);
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('El backend en ejecución no incluye /api/audio-cache. Reiniciá SRT Essay y recargá la página.');
    }
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'No se pudo revisar la caché');
    renderLocalSourceInfo(payload.source); renderCheckedAudioCache(payload);
  } catch (error) { audioCacheStatus.textContent = `Error al revisar caché: ${error.message}`; audioCacheStatus.hidden = false; }
  finally { checkAudioCache.disabled = false; checkAudioCache.textContent = 'Check caché'; }
}
file.addEventListener('change', () => { if (file.files[0]) localSource.value = ''; fileName.textContent = file.files[0]?.name || 'Elegí un archivo o usá la lista local.'; clearLocalSourceInfo(); audioCacheStatus.hidden = true; savePreferences(); });
async function loadInputFiles() {
  try {
    const response = await fetch('/api/input-files');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'No se pudo listar los archivos');
    inputRoot = payload.root || '';
    localSource.replaceChildren(new Option('Elegí un archivo local…', ''));
    payload.files.forEach(path => localSource.add(new Option(path, path)));
    if (storedPreferences['local-source'] && [...localSource.options].some(option => option.value === storedPreferences['local-source'])) {
      localSource.value = storedPreferences['local-source'];
      await checkSelectedAudioCache();
    }
    savePreferences();
  } catch (error) {
    localSource.replaceChildren(new Option(`Error: ${error.message}`, ''));
    localSource.disabled = true;
  }
}
localSource.addEventListener('change', () => { if (localSource.value) void checkSelectedAudioCache(); else { clearLocalSourceInfo(); audioCacheStatus.hidden = true; } });
checkAudioCache.addEventListener('click', checkSelectedAudioCache);
deleteAudioCache.addEventListener('click', async () => {
  if (!localSource.value) { audioCacheStatus.textContent = 'Seleccioná un archivo local para eliminar su caché.'; audioCacheStatus.hidden = false; return; }
  if (!window.confirm(`Se eliminará la caché de audio a ${audioRate.value || 200} WPM para ${localSource.value}. Esta acción no se puede deshacer.`)) return;
  deleteAudioCache.disabled = true; deleteAudioCache.textContent = 'Eliminando…';
  try {
    const response = await fetch('/api/audio-cache/delete', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source_path: localSource.value, rate: Number(audioRate.value || 200)})});
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) throw new Error('El backend en ejecución no incluye la eliminación de caché. Reiniciá SRT Essay y recargá la página.');
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'No se pudo eliminar la caché');
    audioCacheStatus.textContent = payload.fragments ? `Caché eliminada: ${payload.fragments} fragmento${payload.fragments === 1 ? '' : 's'} de ${payload.directories} carpeta${payload.directories === 1 ? '' : 's'}.` : 'No había caché para eliminar con esa velocidad.';
    audioCacheStatus.hidden = false;
  } catch (error) { audioCacheStatus.textContent = `Error al eliminar caché: ${error.message}`; audioCacheStatus.hidden = false; }
  finally { deleteAudioCache.disabled = false; deleteAudioCache.textContent = 'Eliminar caché'; }
});
audioRate.addEventListener('change', () => { if (localSource.value) void checkSelectedAudioCache(); });
void loadInputFiles();
document.addEventListener('input', savePreferences);
document.addEventListener('change', event => { if (event.target !== file) savePreferences(); });
async function loadModels() {
  submit.disabled = true; model.disabled = true; model.replaceChildren(new Option('Cargando modelos instalados…', ''));
  try {
    ollamaUrlField.hidden = provider.value !== 'ollama';
    const response = await fetch(`/api/models?provider=${encodeURIComponent(provider.value)}&ollama_url=${encodeURIComponent(ollamaUrl.value)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'No se pudieron cargar los modelos');
    model.replaceChildren();
    const preferred = storedPreferences.model || payload.default_model;
    payload.models.forEach(item => {
      const option = new Option(item.name, item.name);
      if (item.name === preferred) option.selected = true;
      model.add(option);
    });
    if (!model.options.length) throw new Error('Ollama no tiene modelos instalados');
    if (![...model.options].some(option => option.selected)) model.selectedIndex = 0;
    providerStatus.textContent = payload.credits || '';
    model.disabled = false; submit.disabled = false; savePreferences();
  } catch (error) {
    model.replaceChildren(new Option(`Error: ${error.message}`, ''));
  }
}
provider.addEventListener('change', loadModels);
ollamaUrl.addEventListener('change', loadModels);
void loadModels();

testPromptButton.addEventListener('click', async () => {
  promptTestStatus.textContent = 'Probando modelo…'; promptTestResult.hidden = true; testPromptButton.disabled = true;
  try {
    const response = await fetch('/api/prompts/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      ...promptPayload(), text: promptTestText.value, provider: provider.value, model: model.value, ollama_url: ollamaUrl.value,
    })});
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'No se pudo probar el prompt');
    renderMarkdown(payload.markdown, promptTestResult); promptTestResult.hidden = false;
    const usage = payload.usage || {}; const tokens = usage.total_tokens || ((usage.input_tokens || 0) + (usage.output_tokens || 0));
    promptTestStatus.textContent = `${tokens ? `Tokens usados: ${tokens}. ` : ''}${payload.credits || ''}`;
  } catch (error) { promptTestStatus.textContent = `Error: ${error.message}`; }
  finally { testPromptButton.disabled = false; }
});
let ttsEngines = [];
function renderAudioLanguages() {
  const languages = new Set(ttsEngines.flatMap(engine => engine.languages || []));
  const previous = storedPreferences['audio-lang'] || audioLang.value || 'es';
  audioLang.replaceChildren(...[...languages].sort().map(language => new Option(window.languageNames?.[language] || language, language)));
  if ([...audioLang.options].some(option => option.value === previous)) audioLang.value = previous;
}
function renderAudioEngines() {
  const previous = storedPreferences['audio-tts'] || audioTts.value;
  const compatible = ttsEngines.filter(engine => (engine.languages || []).includes(audioLang.value));
  audioTts.replaceChildren(new Option('Elegí un motor TTS…', ''), ...compatible.map(engine => new Option(engine.label, engine.id)));
  if ([...audioTts.options].some(option => option.value === previous)) audioTts.value = previous;
  else if (compatible.length) audioTts.value = compatible[0].id;
  renderAudioVoices();
}
function renderAudioVoices() {
  const engine = ttsEngines.find(item => item.id === audioTts.value);
  const previous = storedPreferences['audio-voice'] || audioVoice.value;
  const voices = (engine?.voices || []).filter(voice => voice.language === audioLang.value || (voice.languages || []).includes(audioLang.value));
  const voiceOptions = voices.map(voice => {
    const restriction = voice.category === 'library' ? ' · Voice Library (puede requerir plan pago)' : '';
    return new Option(`${voice.name}${voice.locale ? ` (${voice.locale})` : ''}${restriction}`, voice.id);
  });
  audioVoice.replaceChildren(new Option(voices.length ? 'Voz predeterminada' : 'No hay voces compatibles', ''), ...voiceOptions);
  if ([...audioVoice.options].some(option => option.value === previous)) audioVoice.value = previous;
  const needsKey = engine?.id === 'elevenlabs' && !engine.configured;
  const noCompatibleVoice = engine?.id === 'elevenlabs' && !voices.length;
  audioVoice.disabled = Boolean(noCompatibleVoice);
  testVoice.disabled = Boolean(needsKey || noCompatibleVoice);
  const statusMessages = [];
  if (needsKey) statusMessages.push('Configurá ELEVENLABS_API_KEY o .srt-essay-secrets.json para cargar voces.');
  if (engine?.id === 'elevenlabs' && engine.credits?.available) {
    statusMessages.push(`Créditos: ${engine.credits.remaining.toLocaleString()} disponibles de ${engine.credits.limit.toLocaleString()} (${engine.credits.used.toLocaleString()} usados).`);
  } else if (engine?.id === 'elevenlabs' && engine.credits?.error) {
    statusMessages.push('Créditos no disponibles: agregá el permiso User read a la API key.');
  }
  if (noCompatibleVoice) statusMessages.push(`No hay voces etiquetadas para ${window.languageNames?.[audioLang.value] || audioLang.value}.`);
  ttsStatus.textContent = statusMessages.join(' ');
}
async function loadTts() {
  try {
    const response = await fetch('/api/tts'); const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'No se pudieron cargar los motores TTS');
    ttsEngines = payload.engines || []; window.languageNames = payload.language_names || {};
    renderAudioLanguages(); renderAudioEngines(); savePreferences();
  } catch (error) {
    audioTts.replaceChildren(new Option(`Error: ${error.message}`, '')); audioTts.disabled = true;
  }
}
testVoice.addEventListener('click', async () => {
  testVoice.disabled = true; testVoice.textContent = 'Probando…'; voiceTestResult.hidden = true;
  try {
    const response = await fetch('/api/tts/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      lang: audioLang.value, tts: audioTts.value || undefined, voice: audioVoice.value || undefined, rate: Number(audioRate.value),
    })});
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'No se pudo generar la prueba de voz');
    voiceTestText.textContent = payload.text; voiceTestPlayer.src = payload.url; voiceTestResult.hidden = false; await voiceTestPlayer.play();
  } catch (error) { voiceTestText.textContent = `Error de prueba: ${error.message}`; voiceTestResult.hidden = false; }
  finally { testVoice.disabled = false; testVoice.textContent = 'Test'; }
});
audioLang.addEventListener('change', renderAudioEngines);
audioTts.addEventListener('change', renderAudioVoices);
void loadTts();
const base64 = input => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result).split(',', 2)[1]);
  reader.onerror = () => reject(new Error('No se pudo leer el archivo seleccionado'));
  reader.readAsDataURL(input);
});
function renderMarkdown(markdown, target = markdownPreview) {
  if (!window.marked || !window.DOMPurify) {
    target.textContent = markdown;
    return;
  }
  const html = window.marked.parse(markdown.replace(/^[\u200B\u200C\u200D\u200E\u200F\uFEFF]/, ''));
  target.innerHTML = window.DOMPurify.sanitize(html, {USE_PROFILES: {html: true}});
  target.querySelectorAll('pre code').forEach(block => window.hljs?.highlightElement(block));
}
function renderArtifacts(items) {
  artifacts.replaceChildren();
  items.forEach(item => {
    const link = document.createElement('a'); link.href = item.url; link.textContent = item.name; link.download = item.name;
    const row = document.createElement('li'); row.append(link); artifacts.append(row);
  });
  debugPanel.hidden = !items.length;
}
async function readArtifact(url) {
  const response = await fetch(url); if (!response.ok) throw new Error('No se pudo leer el archivo intermedio');
  return response.text();
}
function highlightDiff(source, corrected) {
  const output = document.createElement('pre'); output.className = 'inline-diff';
  const parts = window.Diff ? window.Diff.diffWordsWithSpace(source, corrected) : [{value: corrected}];
  parts.forEach(part => {
    const span = document.createElement('span');
    span.className = part.added ? 'diff-added' : part.removed ? 'diff-removed' : '';
    span.textContent = part.value; output.append(span);
  });
  return output;
}
function renderComparisons(items) {
  const signature = JSON.stringify(items.map(item => [item.index, item.source_url, item.corrected_url, item.diff_url]));
  if (signature === comparisonSignature) return;
  comparisonSignature = signature;
  comparisons.replaceChildren(); comparisonPanel.hidden = !items.length;
  items.forEach(item => {
    const details = document.createElement('details'); const summary = document.createElement('summary');
    summary.textContent = `Bloque ${item.index} · enviado vs. corregido`; details.append(summary);
    details.addEventListener('toggle', async () => {
      if (!details.open || details.dataset.loaded || !item.source_url || !item.corrected_url) return;
      details.dataset.loaded = 'true'; const loading = document.createElement('p'); loading.textContent = 'Cargando comparación…'; details.append(loading);
      try {
        const [source, corrected] = await Promise.all([readArtifact(item.source_url), readArtifact(item.corrected_url)]);
        const grid = document.createElement('div'); grid.className = 'compare-grid';
        [['Enviado al modelo', source], ['Devuelto y corregido', corrected]].forEach(([title, text]) => {
          const section = document.createElement('section'); const heading = document.createElement('strong'); const pre = document.createElement('pre');
          heading.textContent = title; pre.textContent = text; section.append(heading, pre); grid.append(section);
        });
        const title = document.createElement('strong'); title.textContent = 'Cambios resaltados'; loading.replaceWith(grid, title, highlightDiff(source, corrected));
      } catch (error) { loading.textContent = `Error: ${error.message}`; }
    });
    comparisons.append(details);
  });
}

function renderAudioCache(cache) {
  const fragments = Number(cache?.fragments || 0);
  if (!fragments) { audioCacheStatus.hidden = true; audioCacheStatus.textContent = ''; return; }
  const chapters = (cache.chapters || []).map(item => `Capítulo ${item.chapter}: ${item.fragments} archivo${item.fragments === 1 ? '' : 's'}; se retomará desde el fragmento ${item.next_fragment}.`);
  audioCacheStatus.textContent = `Caché temporal: ${fragments} archivo${fragments === 1 ? '' : 's'} encontrado${fragments === 1 ? '' : 's'}. ${chapters.join(' ')}`;
  audioCacheStatus.hidden = false;
}

async function refresh(id) {
  const response = await fetch(`/api/jobs/${id}`);
  const job = await response.json();
  if (!response.ok) throw new Error(job.error || 'No se pudo consultar el trabajo');
  progress.value = job.progress; percent.textContent = `${job.progress}%`;
  state.textContent = job.status === 'completed' ? 'Completado' : job.status === 'failed' ? 'Falló el procesamiento' : 'Procesando…';
  logs.textContent = job.logs.join('\n'); logs.scrollTop = logs.scrollHeight;
  if (job.markdown) renderMarkdown(job.markdown);
  renderArtifacts(job.artifacts || []);
  renderComparisons(job.comparisons || []);
  renderAudioCache(job.audio_cache);
  const audioFiles = job.audio_files?.length ? job.audio_files : job.audio_url ? [{name: job.audio_name || 'audio.mp3', title: 'Audio generado', url: job.audio_url}] : [];
  if (audioFiles.length) {
    audioList.replaceChildren();
    audioFiles.forEach(item => {
      const row = document.createElement('section'); const title = document.createElement('strong'); const player = document.createElement('audio'); const link = document.createElement('a');
      title.textContent = item.title || item.name; player.controls = true; player.src = item.url; link.href = item.url; link.download = item.name; link.textContent = `Descargar ${item.name}`;
      row.append(title, player, link); audioList.append(row);
    });
    audioResult.hidden = false;
  }
  const workPath = job.generated_path || job.workspace_path;
  const workUri = job.generated_uri || job.workspace_uri;
  if (workPath) {
    workspacePath.textContent = workPath; workspaceLink.href = workUri; openWorkspace.dataset.jobId = job.id; workspacePanel.hidden = false;
  }
  resumeAudio.hidden = !job.can_resume_audio;
  resumeAudio.dataset.jobId = job.can_resume_audio ? job.id : '';
  if (job.status === 'completed') {
    if (job.download_url) {
      download.href = job.download_url; download.download = job.output_name; download.hidden = false;
      if (!automaticallyDownloaded.has(job.id)) {
        automaticallyDownloaded.add(job.id);
        const automaticDownload = document.createElement('a'); automaticDownload.href = job.download_url; automaticDownload.download = job.output_name;
        automaticDownload.hidden = true; document.body.append(automaticDownload); automaticDownload.click(); automaticDownload.remove();
        logs.textContent = `${logs.textContent}\nDescarga automática del Markdown iniciada.`;
      }
    }
    submit.disabled = false; generateInputAudio.disabled = false; return;
  }
  if (job.status === 'failed') { submit.disabled = false; generateInputAudio.disabled = false; return; }
  window.setTimeout(() => refresh(id).catch(showError), 900);
}
function showError(error) {
  const message = `Error: ${error.message}`;
  status.hidden = false; state.textContent = message;
  logs.textContent = logs.textContent ? `${logs.textContent}\n${message}` : message;
  logs.scrollTop = logs.scrollHeight;
  submit.disabled = false; generateInputAudio.disabled = false;
}

openWorkspace.addEventListener('click', async () => {
  const jobId = openWorkspace.dataset.jobId; if (!jobId) return;
  try {
    const response = await fetch(`/api/jobs/${jobId}/open-workspace`, {method: 'POST'});
    const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'No se pudo abrir la carpeta');
    logs.textContent = `${logs.textContent}\nCarpeta temporal abierta en Finder: ${payload.path}`;
  } catch (error) { showError(error); }
});

resumeAudio.addEventListener('click', async () => {
  const jobId = resumeAudio.dataset.jobId; if (!jobId) return;
  resumeAudio.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${jobId}/resume-audio`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      audio_lang: audioLang.value, audio_tts: audioTts.value || undefined, audio_voice: audioVoice.value || undefined,
      audio_rate: Number(audioRate.value), audio_pause_ms: Number(audioPause.value),
      audio_merge_batch_size: Number(audioMergeBatchSize.value), audio_test_fragments: Number(audioTestFragments.value),
      audio_split_chapters: audioSplitChapters.checked,
    })});
    const job = await response.json(); if (!response.ok) throw new Error(job.error || 'No se pudo reanudar el audio');
    resumeAudio.hidden = true; state.textContent = 'Reanudando audio desde caché…'; refresh(job.id).catch(showError);
  } catch (error) { showError(error); }
  finally { resumeAudio.disabled = false; }
});

function resetJobView(message) {
  status.hidden = false; state.textContent = message; download.hidden = true; audioResult.hidden = true; audioList.replaceChildren(); audioCacheStatus.hidden = true; audioCacheStatus.textContent = ''; workspacePanel.hidden = true; workspacePath.textContent = ''; workspaceLink.removeAttribute('href'); openWorkspace.dataset.jobId = ''; resumeAudio.hidden = true; resumeAudio.dataset.jobId = ''; progress.value = 0; percent.textContent = '0%'; logs.textContent = message; markdownPreview.innerHTML = '<p>Esperando el resultado…</p>'; debugPanel.hidden = true; debugPanel.open = false; artifacts.replaceChildren(); comparisonPanel.hidden = true; comparisonPanel.open = false; comparisons.replaceChildren(); comparisonSignature = ''; submit.disabled = true; generateInputAudio.disabled = true;
  status.scrollIntoView({behavior: 'smooth', block: 'start'});
}

async function sourcePayload() {
  const source = file.files[0]; const sourcePath = localSource.value;
  if (!source && !sourcePath) throw new Error('Elegí un archivo .srt, .md o .txt');
  return {source_name: source?.name, source_data: source ? await base64(source) : undefined, source_path: sourcePath || undefined};
}

generateInputAudio.addEventListener('click', async () => {
  try {
    resetJobView('Subiendo archivo para generar audio…');
    const response = await fetch('/api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      ...await sourcePayload(), audio_only: true, debug: debug.checked, audio_lang: audioLang.value,
      audio_tts: audioTts.value || undefined, audio_voice: audioVoice.value || undefined,
      audio_rate: Number(audioRate.value),
      audio_merge_batch_size: Number(audioMergeBatchSize.value), audio_test_fragments: Number(audioTestFragments.value),
      audio_split_chapters: audioSplitChapters.checked,
      audio_pause_ms: Number(audioPause.value),
    })});
    const job = await response.json(); if (!response.ok) throw new Error(job.error || 'No se pudo iniciar el audio');
    state.textContent = 'Procesando audio de entrada…';
    logs.textContent = `${logs.textContent}\nTrabajo de audio iniciado: ${job.id}.`;
    refresh(job.id).catch(showError);
  } catch (error) { showError(error); generateInputAudio.disabled = false; }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  let input;
  try { input = await sourcePayload(); } catch (error) { showError(error); return; }
  if (!await savePrompts()) return;
  resetJobView('Subiendo archivo…'); markdownPreview.innerHTML = '<p>Esperando el primer bloque…</p>';
  try {
    const response = await fetch('/api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
      ...input, provider: provider.value, model: model.value,
      ollama_url: ollamaUrl.value, mode: document.querySelector('#mode').value,
      chunk_size: Number(document.querySelector('#chunk-size').value),
      debug: debug.checked, prompt_id: promptProfile.value,
      generate_audio: generateAudio.checked, audio_source: audioSource.value, audio_lang: audioLang.value,
      audio_tts: audioTts.value || undefined, audio_voice: audioVoice.value || undefined,
      audio_rate: Number(audioRate.value),
      audio_merge_batch_size: Number(audioMergeBatchSize.value), audio_test_fragments: Number(audioTestFragments.value),
      audio_split_chapters: audioSplitChapters.checked,
      audio_pause_ms: Number(audioPause.value),
    })});
    const job = await response.json(); if (!response.ok) throw new Error(job.error || 'No se pudo iniciar el trabajo');
    refresh(job.id).catch(showError);
  } catch (error) { showError(error); }
});
