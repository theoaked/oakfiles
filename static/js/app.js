'use strict';

/* ════════════════════════════════════════════════════════════
   Shared (all pages): theme, sidebar, toasts, modals, API
   ════════════════════════════════════════════════════════════ */

const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || '';

document.getElementById('theme-toggle')?.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('oakfiles-theme', next);
});

const _sidebar = document.getElementById('sidebar');
document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
  _sidebar?.classList.toggle('sidebar--open');
});
document.getElementById('sidebar-backdrop')?.addEventListener('click', () => {
  _sidebar?.classList.remove('sidebar--open');
});
function closeMobileSidebar() {
  _sidebar?.classList.remove('sidebar--open');
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

function toast(message, type = 'info', timeout = 4000) {
  const box = document.getElementById('toasts');
  if (!box) { alert(message); return; }
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = message;
  box.appendChild(el);
  setTimeout(() => {
    el.classList.add('toast--leaving');
    setTimeout(() => el.remove(), 300);
  }, timeout);
}

function showModal(id) {
  const el = document.getElementById(id);
  if (el) { el.hidden = false; el.querySelector('input,select')?.focus(); }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = true;
  if (id === 'modal-preview') stopPreviewPlayback();
}

/* Hiding the preview modal does not stop <video>/<audio> playback by
   itself — the element keeps playing in the background. */
function stopPreviewPlayback() {
  document.querySelectorAll('#preview-content video, #preview-content audio').forEach(m => {
    m.pause();
    m.removeAttribute('src');
    try { m.load(); } catch { /* already detached */ }
  });
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal:not([hidden])').forEach(m => { m.hidden = true; });
    stopPreviewPlayback();
    ctxClose();
  }
});

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

/* ════════════════════════════════════════════════════════════
   File browser
   ════════════════════════════════════════════════════════════ */

const browserEl = document.getElementById('browser');
const isAdmin = browserEl?.dataset.isAdmin === 'true';
const zipEnabled = browserEl?.dataset.zipEnabled === 'true';
const ROOTS = Array.from(document.querySelectorAll('.root-link')).map(b => b.dataset.path);

const state = {
  path: null,          // current directory (stays set during search)
  items: [],           // entries currently displayed (listing or search results)
  searchQuery: null,   // non-null => showing search results
  view: localStorage.getItem('oakfiles-view') || 'grid',
  sort: { key: 'name', dir: 1 },
  selection: new Set(),  // indices into state.items
  anchorIndex: null,
};

/* ── File-type helpers ─────────────────────────────────────── */
const KIND_EXTS = {
  image:   ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'avif'],
  video:   ['mp4', 'webm', 'ogg', 'mov', 'm4v', 'mkv', 'avi'],
  audio:   ['mp3', 'wav', 'flac', 'oga', 'm4a', 'aac', 'wma'],
  pdf:     ['pdf'],
  archive: ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso'],
  code:    ['py', 'js', 'ts', 'jsx', 'tsx', 'html', 'css', 'java', 'c', 'cpp', 'cs',
            'go', 'rb', 'rs', 'sh', 'bat', 'ps1', 'json', 'xml', 'yaml', 'yml', 'toml', 'sql'],
  text:    ['txt', 'md', 'csv', 'log', 'ini', 'cfg'],
};

function fileExt(name) {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
}

function fileKind(item) {
  if (item.is_dir) return 'folder';
  const ext = fileExt(item.name);
  for (const [kind, exts] of Object.entries(KIND_EXTS)) {
    if (exts.includes(ext)) return kind;
  }
  return 'file';
}

const KIND_ICON = {
  folder: 'folder', image: 'image', video: 'video', audio: 'audio',
  pdf: 'pdf', archive: 'archive', code: 'code', text: 'file', file: 'file',
};

function iconHtml(kind) {
  return `<span class="fi fi--${kind}"><svg><use href="#i-${KIND_ICON[kind]}"/></svg></span>`;
}

const THUMB_IMG_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']);
const THUMB_VID_EXTS = new Set(['mp4', 'webm', 'ogg', 'mov', 'm4v']);

function mediaHtml(item) {
  const ext = fileExt(item.name);
  // inline=1 → `Content-Disposition: inline` so iOS Safari renders the media
  // in place instead of forcing a download.
  const url = '/api/download?path=' + encodeURIComponent(item.path) + '&inline=1';
  if (THUMB_IMG_EXTS.has(ext)) {
    return `<img loading="lazy" decoding="async" src="${url}" alt="">`;
  }
  if (THUMB_VID_EXTS.has(ext)) {
    // No src yet: loaded on demand by the IntersectionObserver so a folder
    // full of videos doesn't saturate the browser's connections to the host.
    return `<video preload="metadata" muted playsinline webkit-playsinline data-src="${url}#t=0.1"></video>`;
  }
  return iconHtml(fileKind(item));
}

const videoObserver = ('IntersectionObserver' in window)
  ? new IntersectionObserver(entries => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const v = en.target;
        if (v.dataset.src) { v.src = v.dataset.src; v.removeAttribute('data-src'); }
        videoObserver.unobserve(v);
      }
    }, { rootMargin: '200px' })
  : null;

function observeLazyVideos() {
  document.querySelectorAll('#file-area video[data-src]').forEach(v => {
    if (videoObserver) videoObserver.observe(v);
    else { v.src = v.dataset.src; v.removeAttribute('data-src'); }
  });
}

function abortMediaLoads() {
  document.querySelectorAll('#file-area video').forEach(v => {
    videoObserver?.unobserve(v);
    v.removeAttribute('src');
    try { v.load(); } catch { /* already detached */ }
  });
}

function formatSize(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 ** 3) return (bytes / 1024 ** 2).toFixed(1) + ' MB';
  return (bytes / 1024 ** 3).toFixed(2) + ' GB';
}

function formatDate(mtime) {
  return mtime ? mtime.slice(0, 10) : '';
}

/* ── Root-aware paths & breadcrumbs ────────────────────────── */
function normPath(p) {
  return String(p).replace(/\\/g, '/').replace(/\/+$/, '');
}

function rootLabel(root) {
  const parts = normPath(root).split('/').filter(Boolean);
  return parts[parts.length - 1] || root;
}

function findRoot(path) {
  const np = normPath(path).toLowerCase();
  return ROOTS.find(r => {
    const nr = normPath(r).toLowerCase();
    return np === nr || np.startsWith(nr + '/');
  });
}

function breadcrumbSegments(path) {
  const root = findRoot(path);
  if (!root) return [{ name: path, path }];
  const segs = [{ name: rootLabel(root), path: root }];
  let cur = normPath(root);
  for (const part of normPath(path).slice(cur.length).split('/').filter(Boolean)) {
    cur += '/' + part;
    segs.push({ name: part, path: cur });
  }
  return segs;
}

/* ── Show hidden (admin) ───────────────────────────────────── */
function showHiddenEnabled() {
  return isAdmin && document.getElementById('show-hidden-toggle')?.checked === true;
}
function onShowHiddenChange() {
  if (state.searchQuery) runSearch();
  else if (state.path) loadPath(state.path);
}

/* ── Loading & search ──────────────────────────────────────── */
async function loadPath(path) {
  state.path = path;
  state.searchQuery = null;
  document.getElementById('upload-btn')?.removeAttribute('disabled');
  document.getElementById('new-folder-btn')?.removeAttribute('disabled');
  closeMobileSidebar();
  markActiveRoot();
  abortMediaLoads();
  document.getElementById('file-area').innerHTML =
    '<p class="hint hint--center">Loading…</p>';

  try {
    const params = new URLSearchParams({ path });
    if (showHiddenEnabled()) params.set('show_hidden', 'true');
    const data = await apiJson('GET', '/api/ls?' + params);
    state.path = data.path;
    state.items = data.entries;
    resetSelection();
    render();
  } catch (e) {
    document.getElementById('file-area').innerHTML =
      `<p class="alert alert--error">Error: ${escHtml(e.message)}</p>`;
  }
}

function markActiveRoot() {
  const root = state.path ? findRoot(state.path) : null;
  document.querySelectorAll('.root-link').forEach(b => {
    b.classList.toggle('sidebar__link--active',
      !!root && normPath(b.dataset.path).toLowerCase() === normPath(root).toLowerCase());
  });
}

async function runSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  if (!state.path) { toast('Pick a location in the sidebar first.'); return; }

  abortMediaLoads();
  document.getElementById('file-area').innerHTML = '<p class="hint hint--center">Searching…</p>';
  try {
    const params = new URLSearchParams({ q, path: state.path });
    if (showHiddenEnabled()) params.set('show_hidden', 'true');
    const data = await apiJson('GET', '/api/search?' + params);
    state.searchQuery = data.query;
    state.items = data.results;
    resetSelection();
    render();
  } catch (e) {
    document.getElementById('file-area').innerHTML =
      `<p class="alert alert--error">Search error: ${escHtml(e.message)}</p>`;
  }
}

function clearSearch() {
  const input = document.getElementById('search-input');
  input.value = '';
  document.getElementById('search-box')?.classList.remove('has-value');
  if (state.searchQuery !== null && state.path) loadPath(state.path);
}

/* ── View & sorting ────────────────────────────────────────── */
function setView(view) {
  state.view = view;
  localStorage.setItem('oakfiles-view', view);
  render();
}

function setSort(key) {
  if (state.sort.key === key) state.sort.dir *= -1;
  else state.sort = { key, dir: 1 };
  render();
}

function sortedIndices() {
  const { key, dir } = state.sort;
  const idx = state.items.map((_, i) => i);
  idx.sort((a, b) => {
    const A = state.items[a], B = state.items[b];
    if (A.is_dir !== B.is_dir) return A.is_dir ? -1 : 1;
    let cmp;
    if (key === 'size') cmp = (A.size || 0) - (B.size || 0);
    else if (key === 'mtime') cmp = String(A.mtime || '').localeCompare(String(B.mtime || ''));
    else cmp = A.name.localeCompare(B.name, undefined, { sensitivity: 'base', numeric: true });
    return cmp * dir;
  });
  return idx;
}

/* ── Rendering ─────────────────────────────────────────────── */
function render() {
  renderBreadcrumb();
  updateViewToggle();

  const area = document.getElementById('file-area');
  const order = sortedIndices();

  let header = '';
  if (state.searchQuery !== null) {
    const n = state.items.length;
    header = `<div class="search-results__header">
      <strong>${n} result${n !== 1 ? 's' : ''}</strong> for "${escHtml(state.searchQuery)}"
      <button class="btn btn--ghost btn--sm" onclick="clearSearch()">Clear</button>
    </div>`;
  }

  if (!state.items.length) {
    area.innerHTML = header + `<div class="empty">
      <svg><use href="#i-folder"/></svg>
      <strong>${state.searchQuery !== null ? 'No files found' : 'This folder is empty'}</strong>
      ${isAdmin && state.searchQuery === null ? '<p>Drop files here or use the sidebar to upload.</p>' : ''}
    </div>`;
    updateSelectionUI();
    return;
  }

  area.innerHTML = header +
    (state.view === 'grid' ? renderGrid(order) : renderList(order));
  observeLazyVideos();
  updateSelectionUI();
}

function renderBreadcrumb() {
  const bc = document.getElementById('breadcrumb');
  if (!state.path) { bc.innerHTML = ''; return; }
  if (state.searchQuery !== null) {
    bc.innerHTML = `<span class="breadcrumb__item--current">
      <svg style="width:14px;height:14px;vertical-align:-2px"><use href="#i-search"/></svg>
      Search results</span>`;
    return;
  }
  const segs = breadcrumbSegments(state.path);
  bc.innerHTML = segs.map((seg, i) =>
    i < segs.length - 1
      ? `<button class="breadcrumb__item" data-bc="${escHtml(seg.path)}" title="${escHtml(seg.path)}">${escHtml(seg.name)}</button>
         <span class="breadcrumb__sep">/</span>`
      : `<span class="breadcrumb__item--current" title="${escHtml(seg.path)}">${escHtml(seg.name)}</span>`
  ).join('');
  bc.querySelectorAll('[data-bc]').forEach(b =>
    b.addEventListener('click', () => loadPath(b.dataset.bc)));
}

function updateViewToggle() {
  document.getElementById('view-grid-btn')?.classList.toggle('active', state.view === 'grid');
  document.getElementById('view-list-btn')?.classList.toggle('active', state.view === 'list');
}

function checkboxHtml(i) {
  return `<input type="checkbox" class="item-check" data-idx="${i}" aria-label="Select"
          ${state.selection.has(i) ? 'checked' : ''}>`;
}

function moreBtnHtml(i, cls) {
  return `<button class="icon-btn icon-btn--sm ${cls}" data-action="more" data-idx="${i}"
          aria-label="More actions"><svg><use href="#i-more"/></svg></button>`;
}

function renderGrid(order) {
  const cards = order.map(i => {
    const it = state.items[i];
    const meta = it.is_dir
      ? 'Folder'
      : [formatSize(it.size), formatDate(it.mtime)].filter(Boolean).join(' · ');
    return `<div class="fcard${state.selection.has(i) ? ' fcard--selected' : ''}"
                 data-idx="${i}" title="${escHtml(it.path)}">
      ${checkboxHtml(i).replace('item-check', 'item-check fcard__check')}
      ${moreBtnHtml(i, 'fcard__more')}
      <div class="fcard__media">${it.is_dir ? iconHtml('folder') : mediaHtml(it)}</div>
      <div class="fcard__name">${escHtml(it.name)}</div>
      <div class="fcard__meta">${meta}</div>
    </div>`;
  }).join('');
  return `<div class="file-grid">${cards}</div>`;
}

function sortArrow(key) {
  if (state.sort.key !== key) return '';
  return `<svg style="width:12px;height:12px"><use href="#i-chevron-${state.sort.dir === 1 ? 'up' : 'down'}"/></svg>`;
}

function renderList(order) {
  const head = `<div class="list-head">
    <span class="frow__check"></span>
    <span></span>
    <button data-action="sort" data-key="name">Name ${sortArrow('name')}</button>
    <button data-action="sort" data-key="size" class="lh-size">Size ${sortArrow('size')}</button>
    <button data-action="sort" data-key="mtime" class="lh-mtime">Modified ${sortArrow('mtime')}</button>
    <span></span>
  </div>`;

  const rows = order.map(i => {
    const it = state.items[i];
    const sub = state.searchQuery !== null ? `<small>${escHtml(it.path)}</small>` : '';
    return `<div class="frow${state.selection.has(i) ? ' frow--selected' : ''}" data-idx="${i}">
      <span class="frow__check">${checkboxHtml(i)}</span>
      <span class="frow__icon">${it.is_dir ? iconHtml('folder') : mediaHtml(it)}</span>
      <span class="frow__name">${escHtml(it.name)}${sub}</span>
      <span class="frow__size">${it.is_dir ? '—' : formatSize(it.size)}</span>
      <span class="frow__mtime">${formatDate(it.mtime)}</span>
      <span class="frow__more">${moreBtnHtml(i, '')}</span>
    </div>`;
  }).join('');

  return `<div class="file-list">${head}${rows}</div>`;
}

/* ── Selection ─────────────────────────────────────────────── */
function resetSelection() {
  state.selection.clear();
  state.anchorIndex = null;
}

function clearSelection() {
  resetSelection();
  updateSelectionUI();
}

function toggleSelect(i) {
  if (state.selection.has(i)) state.selection.delete(i);
  else state.selection.add(i);
  state.anchorIndex = i;
  updateSelectionUI();
}

function rangeSelect(to) {
  const order = sortedIndices();
  const a = order.indexOf(state.anchorIndex ?? to);
  const b = order.indexOf(to);
  const [lo, hi] = a < b ? [a, b] : [b, a];
  for (let k = lo; k <= hi; k++) state.selection.add(order[k]);
  updateSelectionUI();
}

function updateSelectionUI() {
  const area = document.getElementById('file-area');
  area.classList.toggle('has-selection', state.selection.size > 0);
  area.querySelectorAll('[data-idx]').forEach(el => {
    if (el.matches('.fcard, .frow')) {
      const i = Number(el.dataset.idx);
      const sel = state.selection.has(i);
      el.classList.toggle('fcard--selected', sel && el.classList.contains('fcard'));
      el.classList.toggle('frow--selected', sel && el.classList.contains('frow'));
      const cb = el.querySelector('.item-check');
      if (cb) cb.checked = sel;
    }
  });

  const bar = document.getElementById('sel-bar');
  const n = state.selection.size;
  bar.classList.toggle('sel-bar--visible', n > 0);
  if (n > 0) {
    document.getElementById('sel-count').textContent = `${n} selected`;
    const dl = document.getElementById('sel-download');
    if (dl) {
      let show = false;
      if (n === 1) {
        const it = state.items[[...state.selection][0]];
        show = !it.is_dir || zipEnabled;
      }
      dl.style.display = show ? '' : 'none';
    }
  }
}

function selectedItems() {
  return [...state.selection].map(i => state.items[i]);
}

function selectionDownload() {
  const items = selectedItems();
  if (items.length !== 1) return;
  const it = items[0];
  if (it.is_dir) downloadZip(it.path);
  else downloadFile(it.path);
}

function showMoveSelection() {
  const items = selectedItems();
  if (!items.length) return;
  showMove(items.map(i => i.path),
    items.length === 1 ? items[0].name : `${items.length} items`);
}

function showDeleteSelection() {
  const items = selectedItems();
  if (!items.length) return;
  showDelete(items.map(i => i.path), items.map(i => i.name));
}

/* ── Open / download ───────────────────────────────────────── */
function openItem(item) {
  if (item.is_dir) loadPath(item.path);
  else previewOrDownload(item.path, item.name);
}

function downloadFile(path) {
  window.location.href = '/api/download?path=' + encodeURIComponent(path);
}

function downloadZip(path) {
  window.location.href = '/api/zip?path=' + encodeURIComponent(path);
}

/* ── Context menu ──────────────────────────────────────────── */
let ctxActions = [];

function ctxClose() {
  const menu = document.getElementById('ctx-menu');
  if (menu) menu.hidden = true;
  ctxActions = [];
}

function ctxOpen(x, y, entries) {
  const menu = document.getElementById('ctx-menu');
  ctxActions = [];
  menu.innerHTML = entries.map(en => {
    if (en === 'sep') return '<div class="ctx-menu__sep"></div>';
    const k = ctxActions.push(en.fn) - 1;
    return `<button class="ctx-menu__item${en.danger ? ' ctx-menu__item--danger' : ''}" data-mi="${k}">
      <svg><use href="#i-${en.icon}"/></svg>${escHtml(en.label)}
    </button>`;
  }).join('');
  menu.hidden = false;
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, window.innerWidth - r.width - 8) + 'px';
  menu.style.top = Math.min(y, window.innerHeight - r.height - 8) + 'px';
}

function menuEntriesFor(i) {
  const multi = state.selection.size > 1 && state.selection.has(i);
  const entries = [];

  if (multi) {
    if (isAdmin) {
      entries.push({ label: `Move ${state.selection.size} items`, icon: 'move', fn: showMoveSelection });
      entries.push({ label: `Delete ${state.selection.size} items`, icon: 'trash', danger: true, fn: showDeleteSelection });
      entries.push('sep');
    }
    entries.push({ label: 'Clear selection', icon: 'x', fn: clearSelection });
    return entries;
  }

  const it = state.items[i];
  if (it.is_dir) {
    entries.push({ label: 'Open', icon: 'folder', fn: () => openItem(it) });
    if (zipEnabled) entries.push({ label: 'Download as ZIP', icon: 'archive', fn: () => downloadZip(it.path) });
  } else {
    entries.push({ label: 'Preview', icon: 'eye', fn: () => openItem(it) });
    entries.push({ label: 'Download', icon: 'download', fn: () => downloadFile(it.path) });
  }
  if (isAdmin) {
    entries.push('sep');
    entries.push({ label: 'Rename', icon: 'edit', fn: () => showRename(it.path, it.name) });
    entries.push({ label: 'Move', icon: 'move', fn: () => showMove([it.path], it.name) });
    entries.push('sep');
    entries.push({ label: 'Delete', icon: 'trash', danger: true, fn: () => showDelete([it.path], [it.name]) });
  }
  return entries;
}

document.getElementById('ctx-menu')?.addEventListener('click', e => {
  const btn = e.target.closest('[data-mi]');
  if (!btn) return;
  const fn = ctxActions[Number(btn.dataset.mi)];
  ctxClose();
  fn?.();
});

document.addEventListener('click', e => {
  if (!e.target.closest('#ctx-menu')) ctxClose();
});
window.addEventListener('scroll', ctxClose, true);
window.addEventListener('resize', ctxClose);

/* ── File-area event delegation ────────────────────────────── */
const fileArea = document.getElementById('file-area');

fileArea?.addEventListener('click', e => {
  const check = e.target.closest('.item-check');
  if (check) {
    toggleSelect(Number(check.dataset.idx));
    return;
  }
  const more = e.target.closest('[data-action="more"]');
  if (more) {
    e.stopPropagation();
    const i = Number(more.dataset.idx);
    const r = more.getBoundingClientRect();
    ctxOpen(r.left, r.bottom + 4, menuEntriesFor(i));
    return;
  }
  const sortBtn = e.target.closest('[data-action="sort"]');
  if (sortBtn) {
    setSort(sortBtn.dataset.key);
    return;
  }
  const itemEl = e.target.closest('.fcard[data-idx], .frow[data-idx]');
  if (!itemEl) return;
  const i = Number(itemEl.dataset.idx);
  if (e.ctrlKey || e.metaKey) { toggleSelect(i); return; }
  if (e.shiftKey) { rangeSelect(i); return; }
  if (state.selection.size > 0) { clearSelection(); }
  openItem(state.items[i]);
});

fileArea?.addEventListener('contextmenu', e => {
  const itemEl = e.target.closest('.fcard[data-idx], .frow[data-idx]');
  if (!itemEl) return;
  e.preventDefault();
  const i = Number(itemEl.dataset.idx);
  if (!state.selection.has(i) && state.selection.size > 0) clearSelection();
  ctxOpen(e.clientX, e.clientY, menuEntriesFor(i));
});

/* ── Rename ────────────────────────────────────────────────── */
let pendingRenameSource = null;

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
    toast('Renamed successfully.', 'success');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

document.getElementById('rename-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitRename();
});

/* ── Move (folder picker) ──────────────────────────────────── */
let pendingMovePaths = [];
let pickerPath = null;   // null => roots list

function showMove(paths, label) {
  pendingMovePaths = paths;
  document.getElementById('move-subtitle').textContent =
    `Choose a destination folder for "${label}".`;
  renderPicker(state.searchQuery === null ? state.path : null);
  showModal('modal-move');
}

async function renderPicker(path) {
  pickerPath = path;
  const pathEl = document.getElementById('move-picker-path');
  const listEl = document.getElementById('move-picker-list');
  document.getElementById('move-submit-btn').disabled = !path;

  if (!path) {
    pathEl.innerHTML = '<span class="breadcrumb__item--current">Locations</span>';
    listEl.innerHTML = ROOTS.map(r =>
      `<button class="folder-picker__item" data-pick="${escHtml(r)}">
        ${iconHtml('folder')}${escHtml(rootLabel(r))}
      </button>`).join('');
    bindPicker(listEl, pathEl);
    return;
  }

  const segs = breadcrumbSegments(path);
  pathEl.innerHTML =
    `<button class="breadcrumb__item" data-pick-root>…</button><span class="breadcrumb__sep">/</span>` +
    segs.map((seg, i) =>
      i < segs.length - 1
        ? `<button class="breadcrumb__item" data-pick="${escHtml(seg.path)}">${escHtml(seg.name)}</button>
           <span class="breadcrumb__sep">/</span>`
        : `<span class="breadcrumb__item--current">${escHtml(seg.name)}</span>`
    ).join('');

  listEl.innerHTML = '<div class="folder-picker__empty">Loading…</div>';
  try {
    const params = new URLSearchParams({ path });
    if (showHiddenEnabled()) params.set('show_hidden', 'true');
    const data = await apiJson('GET', '/api/ls?' + params);
    const moving = new Set(pendingMovePaths.map(p => normPath(p).toLowerCase()));
    const dirs = data.entries.filter(en =>
      en.is_dir && !moving.has(normPath(en.path).toLowerCase()));
    listEl.innerHTML = dirs.length
      ? dirs.map(d =>
          `<button class="folder-picker__item" data-pick="${escHtml(d.path)}">
            ${iconHtml('folder')}${escHtml(d.name)}
          </button>`).join('')
      : '<div class="folder-picker__empty">No subfolders — move here or go back.</div>';
  } catch (e) {
    listEl.innerHTML = `<div class="folder-picker__empty">${escHtml(e.message)}</div>`;
  }
  bindPicker(listEl, pathEl);
}

function bindPicker(listEl, pathEl) {
  [listEl, pathEl].forEach(el =>
    el.querySelectorAll('[data-pick], [data-pick-root]').forEach(b =>
      b.addEventListener('click', () =>
        renderPicker(b.hasAttribute('data-pick-root') ? null : b.dataset.pick))));
}

async function submitMove() {
  if (!pickerPath) return;
  try {
    const res = await apiJson('POST', '/api/move', { paths: pendingMovePaths, destination: pickerPath });
    closeModal('modal-move');
    toast(`Moved ${res.moved.length} item${res.moved.length !== 1 ? 's' : ''}.`, 'success');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

/* ── Delete ────────────────────────────────────────────────── */
let pendingDeletePaths = [];

function showDelete(paths, names) {
  pendingDeletePaths = paths;
  const shown = names.slice(0, 5).map(n => `"${n}"`).join(', ');
  const extra = names.length > 5 ? ` and ${names.length - 5} more` : '';
  document.getElementById('delete-confirm-msg').textContent =
    `Delete ${shown}${extra}? This cannot be undone.`;
  showModal('modal-delete');
}

async function submitDelete() {
  try {
    const res = await apiJson('DELETE', '/api/delete', { paths: pendingDeletePaths });
    closeModal('modal-delete');
    toast(`Deleted ${res.deleted.length} item${res.deleted.length !== 1 ? 's' : ''}.`, 'success');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

/* ── Mkdir ─────────────────────────────────────────────────── */
async function submitMkdir() {
  const name = document.getElementById('mkdir-input').value.trim();
  if (!name || !state.path) return;
  try {
    await apiJson('POST', '/api/mkdir', { path: state.path, name });
    closeModal('modal-mkdir');
    document.getElementById('mkdir-input').value = '';
    toast(`Folder "${name}" created.`, 'success');
    refresh();
  } catch (e) { toast(e.message, 'error'); }
}

document.getElementById('mkdir-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') submitMkdir();
});

function refresh() {
  if (state.searchQuery !== null) runSearch();
  else if (state.path) loadPath(state.path);
}

/* ── Upload ────────────────────────────────────────────────── */
let pendingUploadFiles = [];

function uploadFiles(files) {
  if (!state.path) { toast('Pick a folder first.', 'error'); return; }
  pendingUploadFiles = files;

  if (state.searchQuery === null) {
    const existing = new Set(
      state.items.filter(it => !it.is_dir).map(it => it.name.toLowerCase()));
    const conflicts = files.filter(f => existing.has(f.name.toLowerCase()));
    if (conflicts.length) {
      document.getElementById('conflict-msg').textContent =
        conflicts.length === 1
          ? `"${conflicts[0].name}" already exists in this folder. Keep both (auto-rename) or overwrite?`
          : `${conflicts.length} files already exist in this folder. Keep both (auto-rename) or overwrite?`;
      showModal('modal-conflict');
      return;
    }
  }
  startUpload('keep');
}

function resolveConflict(choice) {
  closeModal('modal-conflict');
  startUpload(choice);
}

function hideUploadPanel() {
  document.getElementById('upload-panel').hidden = true;
}

async function startUpload(conflict) {
  const panel = document.getElementById('upload-panel');
  const list = document.getElementById('upload-panel-list');
  const title = document.getElementById('upload-panel-title');
  list.innerHTML = '';
  panel.hidden = false;

  let done = 0, failed = 0;
  title.textContent = `Uploading 0 / ${pendingUploadFiles.length}…`;

  for (const file of pendingUploadFiles) {
    const ok = await uploadSingleFile(file, conflict, list);
    done++;
    if (!ok) failed++;
    title.textContent = `Uploading ${done} / ${pendingUploadFiles.length}…`;
  }

  title.textContent = failed
    ? `Done — ${failed} failed`
    : `Uploaded ${done} file${done !== 1 ? 's' : ''}`;
  if (!failed) setTimeout(hideUploadPanel, 2500);
  toast(failed ? `${failed} upload${failed !== 1 ? 's' : ''} failed.` : 'Upload complete.',
        failed ? 'error' : 'success');
  refresh();
}

function uploadSingleFile(file, conflict, listEl) {
  return new Promise(resolve => {
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.innerHTML = `
      <div class="upload-item__name">
        <span>${escHtml(file.name)}</span><span class="upload-item__status"></span>
      </div>
      <div class="progress-bar"><div class="progress-bar__fill" style="width:0%"></div></div>`;
    listEl.appendChild(item);
    const fill = item.querySelector('.progress-bar__fill');
    const status = item.querySelector('.upload-item__status');

    const formData = new FormData();
    formData.append('path', state.path);
    formData.append('conflict', conflict);
    formData.append('files', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.setRequestHeader('X-CSRF-Token', CSRF);

    xhr.upload.onprogress = e => {
      if (e.lengthComputable) fill.style.width = (e.loaded / e.total * 100) + '%';
    };
    xhr.onload = () => {
      const ok = xhr.status >= 200 && xhr.status < 300;
      fill.style.width = '100%';
      item.classList.add(ok ? 'upload-item--ok' : 'upload-item--err');
      status.textContent = ok ? '✓' : 'Failed';
      resolve(ok);
    };
    xhr.onerror = () => {
      item.classList.add('upload-item--err');
      status.textContent = 'Failed';
      resolve(false);
    };
    xhr.send(formData);
  });
}

/* ── Drag & drop ───────────────────────────────────────────── */
if (browserEl && isAdmin) {
  const overlay = document.getElementById('drop-overlay');
  let dragDepth = 0;

  window.addEventListener('dragenter', e => {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragDepth++;
    if (state.path && overlay) overlay.hidden = false;
  });
  window.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0 && overlay) overlay.hidden = true;
  });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => {
    e.preventDefault();
    dragDepth = 0;
    if (overlay) overlay.hidden = true;
    if (!state.path) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length) uploadFiles(files);
  });
}

/* ── Init (browser page only) ──────────────────────────────── */
if (browserEl) {
  document.querySelectorAll('.root-link').forEach(b =>
    b.addEventListener('click', () => loadPath(b.dataset.path)));

  const fileInput = document.getElementById('file-input');
  fileInput?.addEventListener('change', () => {
    if (fileInput.files.length) uploadFiles(Array.from(fileInput.files));
    fileInput.value = '';
  });

  const searchInput = document.getElementById('search-input');
  searchInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter') runSearch();
  });
  searchInput?.addEventListener('input', () => {
    document.getElementById('search-box')?.classList.toggle('has-value', !!searchInput.value);
  });

  updateViewToggle();

  // With a single configured root, jump straight into it.
  if (ROOTS.length === 1) loadPath(ROOTS[0]);
}
