const PREVIEW_TYPES = {
  image: ['jpg','jpeg','png','gif','webp','svg','bmp'],
  video: ['mp4','webm','ogg'],
  audio: ['mp3','wav','flac','oga'],
  pdf:   ['pdf'],
  text:  ['txt','md','json','xml','csv','yaml','yml','py','js','ts','html','css',
           'java','c','cpp','cs','go','rb','rs','sh','bat','ini','toml','sql'],
};

function getPreviewType(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  for (const [type, exts] of Object.entries(PREVIEW_TYPES)) {
    if (exts.includes(ext)) return type;
  }
  return null;
}

function previewOrDownload(path, name) {
  const type = getPreviewType(name);
  if (!type) {
    window.location.href = '/api/download?path=' + encodeURIComponent(path);
    return;
  }
  openPreview(path, name, type);
}

function openPreview(path, name, type) {
  const modal = document.getElementById('modal-preview');
  const content = document.getElementById('preview-content');
  const link = document.getElementById('preview-download-link');
  const fname = document.getElementById('preview-filename');

  fname.textContent = name;
  link.href = '/api/download?path=' + encodeURIComponent(path);
  link.download = name;
  content.innerHTML = '<span class="preview-loading">Loading…</span>';

  modal.hidden = false;

  const url = '/api/download?path=' + encodeURIComponent(path);

  if (type === 'image') {
    const img = document.createElement('img');
    img.src = url;
    img.alt = name;
    img.onerror = () => { content.innerHTML = '<span class="preview-error">Could not load image.</span>'; };
    content.innerHTML = '';
    content.appendChild(img);

  } else if (type === 'video') {
    const video = document.createElement('video');
    video.src = url;
    video.controls = true;
    video.autoplay = false;
    content.innerHTML = '';
    content.appendChild(video);

  } else if (type === 'audio') {
    const audio = document.createElement('audio');
    audio.src = url;
    audio.controls = true;
    content.innerHTML = '';
    content.appendChild(audio);

  } else if (type === 'pdf') {
    const embed = document.createElement('embed');
    embed.src = url;
    embed.type = 'application/pdf';
    content.innerHTML = '';
    content.appendChild(embed);

  } else if (type === 'text') {
    fetch(url)
      .then(r => r.text())
      .then(text => {
        const pre = document.createElement('pre');
        pre.textContent = text;
        content.innerHTML = '';
        content.appendChild(pre);
      })
      .catch(() => {
        content.innerHTML = '<span class="preview-error">Could not load file.</span>';
      });
  }
}
