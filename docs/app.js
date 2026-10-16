(() => {
  'use strict';
  const repo = 'shamendra654321-byte/quiet-pages';
  const github = `https://github.com/${repo}`;
  let playing = null;
  let currentButton = null;
  function resetAudio() {
    if (playing) { playing.pause(); playing.currentTime = 0; }
    if (currentButton) { currentButton.setAttribute('aria-pressed', 'false'); currentButton.querySelector('.play-symbol').textContent = '▶'; }
    playing = null; currentButton = null;
  }
  document.querySelectorAll('[data-voice]').forEach(button => {
    button.addEventListener('click', async () => {
      const same = currentButton === button;
      resetAudio();
      if (same) return;
      const sound = new Audio(`audio/${button.dataset.voice}.wav`);
      playing = sound; currentButton = button;
      button.setAttribute('aria-pressed', 'true');
      button.querySelector('.play-symbol').textContent = '■';
      sound.addEventListener('ended', () => { if (playing === sound) resetAudio(); });
      try { await sound.play(); }
      catch { if (playing === sound) { resetAudio(); document.getElementById('audio-status').textContent = 'The sample could not play. Please try again or preview this voice in the app.'; } }
    });
  });
  const dialog = document.getElementById('follow-dialog');
  document.getElementById('follow-open').addEventListener('click', () => dialog.showModal());
  document.getElementById('follow-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if(event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close(); } });
  document.getElementById('share-button').addEventListener('click', async event => {
    const button = event.currentTarget;
    try { await navigator.clipboard.writeText(location.origin + location.pathname); button.textContent = 'Link copied ✓'; document.getElementById('share-status').textContent = 'Page link copied.'; setTimeout(() => { button.textContent = 'Copy page link ↗'; }, 3000); }
    catch { document.getElementById('share-status').textContent = 'Copy the address from your browser to share this page.'; button.textContent = 'Copy the browser address'; }
  });
  const status = document.getElementById('release-status');
  const create = (tag, className, text) => { const el = document.createElement(tag); if(className) el.className = className; if(text) el.textContent = text; return el; };
  const validReleaseURL = url => typeof url === 'string' && url.startsWith(github + '/releases/');
  async function loadReleases() {
    try {
      const response = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=12`, {signal: AbortSignal.timeout(8000), headers: {'Accept': 'application/vnd.github+json'}});
      if (!response.ok) throw new Error('Release feed unavailable');
      const data = await response.json();
      if (!Array.isArray(data)) throw new Error('Invalid release feed');
      const releases = data.filter(r => !r.draft && validReleaseURL(r.html_url) && Array.isArray(r.assets) && r.assets.some(a => a.name === 'QuietPages-Windows-x64.zip' && validReleaseURL(a.browser_download_url))).sort((a,b) => new Date(b.published_at) - new Date(a.published_at));
      if (!releases.length) throw new Error('No downloadable releases');
      const latest = releases[0];
      const portable = latest.assets.find(a => a.name === 'QuietPages-Windows-x64.zip' && validReleaseURL(a.browser_download_url));
      const asset = latest.assets.find(a => a.name === 'QuietPages-Setup-Windows-x64.exe' && validReleaseURL(a.browser_download_url)) || portable;
      document.getElementById('portable-link').href = portable.browser_download_url;
      document.querySelectorAll('.download-link').forEach(link => { link.href = asset.browser_download_url; });
      document.getElementById('version-label').textContent = `${latest.name || latest.tag_name} · ${Math.round(asset.size / 1048576)} MB · Windows 64-bit`;
      const list = document.getElementById('release-list');
      const fragment = document.createDocumentFragment();
      releases.slice(0, 4).forEach((release, i) => {
        const article = create('article', 'release');
        const meta = create('div', 'release-meta');
        meta.append(create('span', 'pill', i === 0 ? 'LATEST RELEASE' : 'PREVIOUS RELEASE'));
        const date = new Date(release.published_at);
        const time = create('time', '', Number.isNaN(date.valueOf()) ? '' : date.toLocaleDateString('en-AU', {day:'numeric',month:'long',year:'numeric'}));
        if (!Number.isNaN(date.valueOf())) time.dateTime = date.toISOString();
        meta.append(time);
        const body = create('div');
        body.append(create('h3', '', release.name || release.tag_name));
        const notes = (release.body || 'A new Quiet Pages release is available. Open the full release notes for details.').replace(/^#{1,6}\s+/gm, '').replace(/\*\*/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        body.append(create('p', '', notes.length > 1000 ? notes.slice(0, 1000) + '…' : notes));
        const link = create('a', 'text-link', 'Read the release notes ↗'); link.href = release.html_url; body.append(link);
        article.append(meta, body); fragment.append(article);
      });
      list.replaceChildren(fragment);
      status.textContent = 'Latest announcements from our GitHub releases.';
    } catch {
      status.textContent = 'Showing the saved launch announcement. Visit GitHub for the newest releases.';
      // Keep a usable latest-release destination if GitHub rate-limits this browser.
      document.querySelectorAll('.download-link').forEach(link => { link.href = github + '/releases'; });
      document.getElementById('version-label').textContent = 'Choose the newest Windows installer or ZIP on GitHub · Windows 64-bit';
    }
  }
  loadReleases();
})();
