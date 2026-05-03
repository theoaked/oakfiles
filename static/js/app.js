/* ── CSRF ──────────────────────────────────────────────────── */
const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || '';

/* ── State ─────────────────────────────────────────────────── */
let currentPath = null;
let pendingRenameSource = null;
let pendingMovePaths = [];
let pendingDeletePaths = [];
let pendingUploadFiles = [];
let pendingConflictResolve = null;

const isAdmin = document.getElementById('browser')?.dataset.isAdmin === 'true';

function showHiddenEnabled() {
  return isAdmin && document.getElementById('show-hidden-toggle')?.checked === true;
}

function onShowHiddenChange() {
  if (currentPath) loadPath(currentPath);
}

/* ── Modal helpers ─────────────────────────────────────────── */
function showModal(id) {
  const el = document.getElementById(id);
  if (el) { el.hidden = false; el.querySelector('input,select')?.focus(); }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = true;
}

/* Close modal on Escape */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal:not([hidden])').forEach(m => { m.hidden = true; });
  }
});

/* ── API helpers ───────────────────────────────────────────── */
async function apiJson(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

/* Serialize a value as JSON safe for embedding in a double-quoted HTML attribute.
   Without this, Windows paths like C:\Users\... lose their backslashes when the
   browser evaluates the onclick as a JS string literal. */
function jsAttr(val) {
  return JSON.stringify(val).replace(/[&"<>]/g, c =>
    ({ '&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;' }[c])
  );
}

function formatSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB';
}

/* ── Directory loading ─────────────────────────────────────── */
async function loadPath(path) {
  currentPath = path;
  document.getElementById('search-results-container').style.display = 'none';
  document.getElementById('file-list-container').style.display = '';

  const uploadBtn = document.getElementById('upload-btn');
  const mkdirBtn = document.getElementById('new-folder-btn');
  if (uploadBtn) uploadBtn.disabled = false;
  if (mkdirBtn) mkdirBtn.disabled = false;

  try {
    const params = new URLSearchParams({ path });
    if (showHiddenEnabled()) params.set('show_hidden', 'true');
    const data = await apiJson('GET', '/api/ls?' + params);
    renderFileList(data);
  } catch (e) {
    document.getElementById('file-list-container').innerHTML =
      `<p class="alert alert--error">Error: ${escHtml(e.message)}</p>`;
  }
}

function buildBreadcrumbs(path) {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  const segs = [];
  for (let i = 0; i < parts.length; i++) {
    const sep = path.includes('\\') ? '\\' : '/';
    const full = parts.slice(0, i + 1).join(sep);
    segs.push({ name: parts[i], path: (path.startsWith('\\') || /^[A-Z]:/i.test(parts[0]) ? '' : '/') + full });
  }
  // Fix Windows drive letter
  if (/^[A-Z]:/i.test(parts[0])) {
    segs[0].path = parts[0] + '\\';
    for (let i = 1; i < segs.length; i++) {
      segs[i].path = parts.slice(0, i + 1).join('\\');
    }
  }
  return segs;
}

function renderFileList(data) {
  const container = document.getElementById('file-list-container');
  const breadcrumbs = buildBreadcrumbs(data.path);

  let bcHtml = breadcrumbs.map((seg, i) =>
    i < breadcrumbs.length - 1
      ? `<button class="breadcrumb__item btn btn--link btn--sm" onclick="loadPath(${jsAttr(seg.path)})">${escHtml(seg.name)}</button><span class="breadcrumb__sep">/</span>`
      : `<span class="breadcrumb__item breadcrumb__item--current">${escHtml(seg.name)}</span>`
  ).join('');

  let rows = '';
  if (!data.entries.length) {
    rows = '<tr><td colspan="5"><p class="hint hint--center">This folder is empty.</p></td></tr>';
  } else {
    for (const e of data.entries) {
      const safeName = escHtml(e.name);
      const nameCell = e.is_dir
        ? `<button class="file-name file-name--dir btn btn--link" onclick="loadPath(${jsAttr(e.path)})"><span aria-hidden="true">📁</span>${safeName}</button>`
        : `<button class="file-name btn btn--link" onclick="previewOrDownload(${jsAttr(e.path)},${jsAttr(e.name)})"><span aria-hidden="true">📄</span>${safeName}</button>`;

      let actions = '';
      if (isAdmin) {
        actions = `
          <button class="btn btn--ghost btn--xs" onclick="showRename(${jsAttr(e.path)},${jsAttr(e.name)})">Rename</button>
          <button class="btn btn--ghost btn--xs" onclick="showMove(${jsAttr([e.path])},${jsAttr(e.name)})">Move</button>
          ${e.is_dir ? `<button class="btn btn--ghost btn--xs" onclick="downloadZip(${jsAttr(e.path)},${jsAttr(e.name)})">ZIP</button>` : ''}
          <button class="btn btn--danger btn--xs" onclick="showDelete(${jsAttr([e.path])},${jsAttr(e.name)})">Delete</button>`;
      }

      rows += `<tr class="file-row${e.is_dir ? ' file-row--dir' : ''}">
        <td class="file-table__name">${nameCell}</td>
        <td class="file-table__size hide-mobile">${e.is_dir ? '' : formatSize(e.size)}</td>
        <td class="file-table__mtime hide-mobile">${e.mtime ? e.mtime.slice(0, 10) : ''}</td>
        ${isAdmin ? `<td class="file-table__actions">${actions}</td>` : ''}
      </tr>`;
    }
  }

  container.innerHTML = `
    <div class="breadcrumb" style="padding:.5rem 0">${bcHtml}</div>
    <table class="file-table">
      <thead><tr>
        <th>Name</th>
        <th class="file-table__size hide-mobile">Size</th>
        <th class="file-table__mtime hide-mobile">Modified</th>
        ${isAdmin ? '<th class="file-table__actions">Actions</th>' : ''}
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/* ── Search ────────────────────────────────────────────────── */
async function runSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q || !currentPath) return;

  const src = document.getElementById('search-results-container');
  const lst = document.getElementById('file-list-container');
  src.style.display = '';
  lst.style.display = 'none';

  src.innerHTML = '<p class="hint">Searching…</p>';
  try {
    const params = new URLSearchParams({ q, path: currentPath });
    if (showHiddenEnabled()) params.set('show_hidden', 'true');
    const data = await apiJson('GET', `/api/search?${params}`);
    renderSearchResults(data);
  } catch (e) {
    src.innerHTML = `<p class="alert alert--error">Search error: ${escHtml(e.message)}</p>`;
  }
}

function renderSearchResults(data) {
  const src = document.getElementById('search-results-container');
  const count = data.results.length;
  let rows = data.results.map(r => {
    const safeName = escHtml(r.name);
    const safePath = escHtml(r.path);
    const nameCell = r.is_dir
      ? `<button class="file-name file-name--dir btn btn--link" onclick="loadPath(${jsAttr(r.path)})"><span>📁</span>${safeName}</button>`
      : `<button class="file-name btn btn--link" onclick="previewOrDownload(${jsAttr(r.path)},${jsAttr(r.name)})"><span>📄</span>${safeName}</button>`;
    return `<tr><td>${nameCell}</td><td class="hide-mobile muted" style="font-size:.8rem">${safePath}</td>
      <td class="hide-mobile">${r.is_dir ? '' : formatSize(r.size)}</td>
      <td class="hide-mobile">${r.mtime ? r.mtime.slice(0, 10) : ''}</td></tr>`;
  }).join('');

  src.innerHTML = `
    <div class="search-results__header">
      <strong>${count} result${count !== 1 ? 's' : ''}</strong> for "${escHtml(data.query)}"
      <button class="btn btn--ghost btn--sm" onclick="clearSearch()">✕ Clear</button>
    </div>
    ${count ? `<table class="file-table"><thead><tr>
      <th>Name</th><th class="hide-mobile">Path</th>
      <th class="hide-mobile">Size</th><th class="hide-mobile">Modified</th>
    </tr></thead><tbody>${rows}</tbody></table>` : '<p class="hint hint--center">No files found.</p>'}`;
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-results-container').style.display = 'none';
  document.getElementById('file-list-container').style.display = '';
}

document.getElementById('search-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') runSearch();
});

/* ── Rename ────────────────────────────────────────────────── */
function showRename(path, name) {
  pendingRenameSource = path;
  document.getElementById('rename-input').value = name;
  showModal('modal-rename');
}

async function submitRename() {
  const newName = document.getElementById('rename-input').value.trim();
  if (!newName) return;
  try {
    await apiJson('POST', '/api/rename', { path: pendingRenameSource, new_name: newName });
    closeModal('modal-rename');
    if (currentPath) loadPath(currentPath);
  } catch (e) { alert(e.message); }
}

document.getElementById('rename-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitRename();
});

/* ── Move ──────────────────────────────────────────────────── */
function showMove(paths, label) {
  pendingMovePaths = paths;
  document.getElementById('move-dest-input').value = '';
  document.getElementById('modal-move').querySelector('.modal__title').textContent = `Move "${label}"`;
  showModal('modal-move');
}

async function submitMove() {
  const dest = document.getElementById('move-dest-input').value.trim();
  if (!dest) return;
  try {
    await apiJson('POST', '/api/move', { paths: pendingMovePaths, destination: dest });
    closeModal('modal-move');
    if (currentPath) loadPath(currentPath);
  } catch (e) { alert(e.message); }
}

/* ── Delete ────────────────────────────────────────────────── */
function showDelete(paths, label) {
  pendingDeletePaths = paths;
  document.getElementById('delete-confirm-msg').textContent =
    `Are you sure you want to delete "${label}"? This cannot be undone.`;
  showModal('modal-delete');
}

async function submitDelete() {
  try {
    await apiJson('DELETE', '/api/delete', { paths: pendingDeletePaths });
    closeModal('modal-delete');
    if (currentPath) loadPath(currentPath);
  } catch (e) { alert(e.message); }
}

/* ── Mkdir ─────────────────────────────────────────────────── */
async function submitMkdir() {
  const name = document.getElementById('mkdir-input').value.trim();
  if (!name || !currentPath) return;
  try {
    await apiJson('POST', '/api/mkdir', { path: currentPath, name });
    closeModal('modal-mkdir');
    loadPath(currentPath);
  } catch (e) { alert(e.message); }
}

document.getElementById('mkdir-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitMkdir();
});

/* ── ZIP Download ──────────────────────────────────────────── */
function downloadZip(path, name) {
  window.location.href = '/api/zip?path=' + encodeURIComponent(path);
}

/* ── Upload ────────────────────────────────────────────────── */
if (isAdmin) {
  const fileInput = document.getElementById('file-input');
  const dropZone = document.getElementById('drop-zone');
  const browser = document.getElementById('browser');

  fileInput?.addEventListener('change', () => {
    if (fileInput.files.length) uploadFiles(Array.from(fileInput.files));
    fileInput.value = '';
  });

  browser?.addEventListener('dragover', e => {
    e.preventDefault();
    if (currentPath && dropZone) { dropZone.classList.remove('drop-zone--hidden'); dropZone.classList.add('drop-zone--active'); }
  });
  browser?.addEventListener('dragleave', e => {
    if (!browser.contains(e.relatedTarget)) {
      dropZone?.classList.add('drop-zone--hidden');
      dropZone?.classList.remove('drop-zone--active');
    }
  });
  browser?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone?.classList.add('drop-zone--hidden');
    dropZone?.classList.remove('drop-zone--active');
    if (!currentPath) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length) uploadFiles(files);
  });
}

function uploadFiles(files) {
  if (!currentPath) { alert('Navigate into a folder first.'); return; }
  pendingUploadFiles = files;
  startUpload('keep');
}

function resolveConflict(choice) {
  closeModal('modal-conflict');
  if (pendingConflictResolve) pendingConflictResolve(choice);
}

async function startUpload(conflict) {
  const progressEl = document.getElementById('upload-progress');
  progressEl.style.display = '';
  progressEl.innerHTML = '';

  for (const file of pendingUploadFiles) {
    await uploadSingleFile(file, conflict, progressEl);
  }

  loadPath(currentPath);
}

function uploadSingleFile(file, conflict, progressEl) {
  return new Promise(resolve => {
    const itemEl = document.createElement('div');
    itemEl.className = 'upload-progress__item';
    itemEl.innerHTML = `<span>${escHtml(file.name)}</span>
      <div class="progress-bar"><div class="progress-bar__fill" style="width:0%"></div></div>`;
    progressEl.appendChild(itemEl);
    const fill = itemEl.querySelector('.progress-bar__fill');

    const formData = new FormData();
    formData.append('path', currentPath);
    formData.append('conflict', conflict);
    formData.append('files', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.setRequestHeader('X-CSRF-Token', CSRF);

    xhr.upload.onprogress = e => {
      if (e.lengthComputable) fill.style.width = (e.loaded / e.total * 100) + '%';
    };

    xhr.onload = () => {
      fill.style.width = '100%';
      itemEl.querySelector('span').textContent += ' ✓';
      setTimeout(() => itemEl.remove(), 2000);
      resolve();
    };
    xhr.onerror = () => {
      itemEl.querySelector('span').textContent += ' ✗ Error';
      resolve();
    };

    xhr.send(formData);
  });
}
