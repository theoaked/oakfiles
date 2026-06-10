// Video the browser plays natively vs. formats the server transcodes to MP4
// on the fly (via /api/stream). Both open in the video player.
const NATIVE_VIDEO = ['mp4','webm','ogg','mov','m4v'];
const TRANSCODE_VIDEO = ['avi','mkv','wmv','flv','mpg','mpeg','m2ts','mts',
                         'ts','3gp','vob','divx','asf','rm','rmvb','ogv'];

const PREVIEW_TYPES = {
  image: ['jpg','jpeg','png','gif','webp','svg','bmp'],
  video: [...NATIVE_VIDEO, ...TRANSCODE_VIDEO],
  audio: ['mp3','wav','flac','oga'],
  pdf:   ['pdf'],
  text:  ['txt','md','json','xml','csv','yaml','yml','py','js','ts','html','css',
           'java','c','cpp','cs','go','rb','rs','sh','bat','ini','toml','sql'],
};

function fileExtOf(filename) {
  return filename.split('.').pop().toLowerCase();
}

function getPreviewType(filename) {
  const ext = fileExtOf(filename);
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

  // inline=1 serves the file with `Content-Disposition: inline` so browsers
  // (notably iOS Safari) render it in place instead of forcing a download.
  const url = '/api/download?path=' + encodeURIComponent(path) + '&inline=1';

  if (type === 'image') {
    const img = document.createElement('img');
    img.src = url;
    img.alt = name;
    img.onerror = () => { content.innerHTML = '<span class="preview-error">Could not load image.</span>'; };
    content.innerHTML = '';
    content.appendChild(img);

  } else if (type === 'video') {
    const needsTranscode = TRANSCODE_VIDEO.includes(fileExtOf(name));
    const video = document.createElement('video');
    // Browser-incompatible formats are transcoded to MP4 server-side; native
    // ones stream directly with Range support so seeking works.
    video.src = needsTranscode
      ? '/api/stream?path=' + encodeURIComponent(path)
      : url;
    video.controls = true;
    video.autoplay = false;
    video.playsInline = true;
    video.setAttribute('playsinline', '');
    video.setAttribute('webkit-playsinline', '');
    video.preload = needsTranscode ? 'auto' : 'metadata';
    video.onerror = () => {
      const msg = needsTranscode
        ? 'Could not transcode this video. Is ffmpeg installed on the server? Use the Download link above.'
        : 'Could not play this video. Use the Download link above.';
      content.innerHTML = '<span class="preview-error">' + msg + '</span>';
    };
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
