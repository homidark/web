const dialog = document.querySelector('#auth-dialog');
const authForm = document.querySelector('#auth-form');
const toast = document.querySelector('#toast');
const cursorTracker = document.querySelector('#cursor-tracker');
let authMode = 'login';
let signedInUser = null;
let siteContent = null;
let toastTimer;
let revealBound = false;

function notify(message) {
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 2800);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
    credentials: 'same-origin'
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || 'Something went wrong.');
  return payload;
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : '#';
  } catch {
    return '#';
  }
}

function renderContent(content) {
  siteContent = content;
  const root = document.documentElement;
  root.style.setProperty('--ink', content.theme.background);
  root.style.setProperty('--surface', content.theme.surface);
  root.style.setProperty('--paper', content.theme.text);
  root.style.setProperty('--lime', content.theme.accent);
  document.body.dataset.uiStyle = content.theme.style;
  document.querySelector('.process-graphic').src = `/process-flow.svg?accent=${encodeURIComponent(content.theme.accent)}`;
  document.querySelector('#hero-eyebrow').textContent = content.eyebrow;
  document.querySelector('#hero-description').textContent = content.heroText;
  const titleWords = content.title.trim().split(/\s+/);
  const title = document.querySelector('#hero-title');
  const firstLine = document.createElement('span');
  firstLine.textContent = titleWords.shift() || content.title;
  const secondLine = document.createElement('span');
  secondLine.className = 'title-second';
  secondLine.textContent = titleWords.join(' ');
  const plus = document.createElement('span');
  plus.className = 'plus-mark';
  plus.textContent = '+';
  secondLine.append(plus);
  const brandLine = document.createElement('span');
  brandLine.className = 'title-last';
  brandLine.textContent = content.brand;
  const period = document.createElement('span');
  period.className = 'title-period';
  period.textContent = '.';
  brandLine.append(period);
  title.replaceChildren(firstLine, secondLine, brandLine);
  document.querySelector('#example-title').innerHTML = `${escapeHtml(content.exampleTitle)}<span class="lime">.</span>`;
  document.querySelector('#examples-description').textContent = content.examplesDescription;
  const driverList = document.querySelector('#driver-example-list');
  driverList.replaceChildren(...content.driverExamples.map((item, index) => {
    const article = document.createElement('article');
    article.className = 'driver-example reveal-target';
    const number = document.createElement('span');
    number.className = 'driver-example-number';
    number.textContent = `0${index + 1}`;
    const copy = document.createElement('div');
    const heading = document.createElement('h4');
    heading.textContent = item.title;
    const description = document.createElement('p');
    description.textContent = item.description;
    copy.append(heading, description);
    article.append(number, copy);
    return article;
  }));
  document.querySelector('#downloads-title').innerHTML = `${escapeHtml(content.downloadsTitle).replace(/\\n/g, '<br>')}<br><span>MOVE.</span>`;
  document.querySelector('#downloads-description').textContent = content.downloadsDescription;

  const downloadList = document.querySelector('#download-list');
  downloadList.replaceChildren(...content.downloads.map((item, index) => {
    const row = document.createElement('article');
    row.className = 'download-row reveal-target';
    const number = document.createElement('span');
    number.className = 'download-number';
    number.textContent = `0${index + 1}`;
    const info = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'download-name';
    name.textContent = item.name;
    const version = document.createElement('div');
    version.className = 'download-version';
    version.textContent = item.version;
    info.append(name, version);
    const link = document.createElement('a');
    link.className = 'download-button';
    link.href = safeHttpsUrl(item.url);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.innerHTML = `<span>${escapeHtml(item.name)}</span><span aria-hidden="true">↗</span>`;
    row.append(number, info, link);
    return row;
  }));
  document.title = `${content.title} + ${content.brand}`;
  document.querySelector('#hero-title').setAttribute('aria-label', `${content.title} ${content.brand}`);
  observeScrollReveals();
}

function observeScrollReveals() {
  const targets = document.querySelectorAll('.reveal-target');
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    targets.forEach((target) => target.classList.add('reveal-visible'));
    return;
  }
  targets.forEach((target, index) => {
    if (target.dataset.revealObserved) return;
    target.dataset.revealObserved = 'true';
    target.style.setProperty('--reveal-delay', `${(index % 4) * 75}ms`);
  });
  const revealVisible = () => {
    document.querySelectorAll('.reveal-target:not(.reveal-visible)').forEach((target) => {
      const bounds = target.getBoundingClientRect();
      if (bounds.top < window.innerHeight * 0.9 && bounds.bottom > 0) {
        target.classList.add('reveal-visible');
      }
    });
  };
  if (!revealBound) {
    window.addEventListener('scroll', revealVisible, { passive: true });
    window.addEventListener('resize', revealVisible);
    revealBound = true;
  }
  revealVisible();
}

function enableWebsitePointer() {
  const pointerIsFine = window.matchMedia('(pointer: fine)').matches;
  const motionIsAllowed = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!pointerIsFine || !motionIsAllowed) return;

  document.addEventListener('pointermove', (event) => {
    if (event.pointerType !== 'mouse') return;
    cursorTracker.style.setProperty('--cursor-x', `${event.clientX}px`);
    cursorTracker.style.setProperty('--cursor-y', `${event.clientY}px`);
    cursorTracker.classList.add('visible');
    const target = event.target instanceof Element ? event.target.closest('a, button, input, select, textarea') : null;
    cursorTracker.classList.toggle('over-control', Boolean(target));
    const hero = document.querySelector('.hero');
    const bounds = hero.getBoundingClientRect();
    const insideHero = event.clientX >= bounds.left && event.clientX <= bounds.right && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
    const horizontalOffset = insideHero ? (event.clientX - (bounds.left + bounds.width / 2)) * 0.018 : 0;
    const verticalOffset = insideHero ? (event.clientY - (bounds.top + bounds.height / 2)) * 0.018 : 0;
    hero.style.setProperty('--hero-drift-x', `${horizontalOffset}px`);
    hero.style.setProperty('--hero-drift-y', `${verticalOffset}px`);
    hero.style.setProperty('--hero-content-shift-x', `${horizontalOffset * -0.12}px`);
    hero.style.setProperty('--hero-content-shift-y', `${verticalOffset * -0.12}px`);
  });
  document.addEventListener('pointerdown', () => cursorTracker.classList.add('pressed'));
  window.addEventListener('pointerup', () => cursorTracker.classList.remove('pressed'));
  window.addEventListener('pointerout', (event) => {
    if (!event.relatedTarget) cursorTracker.classList.remove('visible', 'over-control', 'pressed');
  });
  window.addEventListener('blur', () => cursorTracker.classList.remove('visible', 'over-control', 'pressed'));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function openAuth(mode = 'login') {
  setAuthMode(mode);
  dialog.showModal();
}

function setAuthMode(mode) {
  authMode = mode;
  document.querySelectorAll('.auth-tab').forEach((tab) => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-pressed', String(active));
  });
  document.querySelector('#auth-mode-label').textContent = mode === 'login' ? 'HOMI ACCOUNT / SIGN IN' : 'HOMI ACCOUNT / CREATE ACCOUNT';
  document.querySelector('#auth-title').innerHTML = mode === 'login' ? 'WELCOME<br>BACK<span class="lime">.</span>' : 'CREATE<br>ACCOUNT<span class="lime">.</span>';
  document.querySelector('#auth-submit').innerHTML = mode === 'login' ? 'SIGN IN <span aria-hidden="true">↗</span>' : 'CREATE ACCOUNT <span aria-hidden="true">↗</span>';
  document.querySelector('#auth-form [name="password"]').autocomplete = mode === 'login' ? 'current-password' : 'new-password';
  document.querySelector('#auth-error').textContent = '';
}

function openDashboard() {
  if (!signedInUser?.isOwner) {
    if (signedInUser) {
      notify('The dashboard is available to the site owner only.');
    } else {
      openAuth('login');
    }
    return;
  }
  document.querySelector('.site-shell').hidden = true;
  document.querySelector('#dashboard').hidden = false;
  document.querySelector('#dashboard-username').textContent = signedInUser.username;
  renderEditor(siteContent);
  window.scrollTo(0, 0);
}

function makeField(label, path, value, multiline = false, inputType = 'text', options = []) {
  const wrap = document.createElement('div');
  wrap.className = 'editor-field';
  const isSelect = inputType === 'select';
  const input = document.createElement(isSelect ? 'select' : multiline ? 'textarea' : 'input');
  input.className = multiline ? 'field-area' : isSelect ? 'field-input field-select' : 'field-input';
  if (isSelect) {
    options.forEach(([optionValue, optionLabel]) => {
      const option = document.createElement('option');
      option.value = optionValue;
      option.textContent = optionLabel;
      input.append(option);
    });
  } else if (!multiline) {
    input.type = inputType;
  }
  input.dataset.path = path;
  input.value = value;
  input.setAttribute('aria-label', label);
  const caption = document.createElement('label');
  caption.textContent = label;
  caption.append(input);
  wrap.append(caption);
  return wrap;
}

function addGroup(container, title, entries) {
  const section = document.createElement('section');
  section.className = 'editor-group';
  const heading = document.createElement('h2');
  heading.textContent = title;
  const grid = document.createElement('div');
  grid.className = 'editor-grid';
  entries.forEach(([label, path, value, multiline, inputType, options]) => grid.append(makeField(label, path, value, multiline, inputType, options)));
  section.append(heading, grid);
  container.append(section);
}

function renderEditor(content) {
  const fields = document.querySelector('#content-fields');
  fields.replaceChildren();
  addGroup(fields, 'Hero & page copy', [
    ['Browser title', 'title', content.title], ['Brand name', 'brand', content.brand],
    ['Hero eyebrow', 'eyebrow', content.eyebrow], ['Hero description', 'heroText', content.heroText, true],
    ['Process example heading', 'exampleTitle', content.exampleTitle], ['Process example description', 'examplesDescription', content.examplesDescription, true],
    ['Downloads heading', 'downloadsTitle', content.downloadsTitle], ['Downloads description', 'downloadsDescription', content.downloadsDescription, true]
  ]);
  addGroup(fields, 'Appearance', [
    ['UI style', 'theme.style', content.theme.style, false, 'select', [['cyber', 'Cyber'], ['minimal', 'Minimal'], ['terminal', 'Terminal']]],
    ['Accent color', 'theme.accent', content.theme.accent, false, 'color'],
    ['Page background', 'theme.background', content.theme.background, false, 'color'],
    ['Panel background', 'theme.surface', content.theme.surface, false, 'color'],
    ['Main text color', 'theme.text', content.theme.text, false, 'color']
  ]);
  content.driverExamples.forEach((item, index) => addGroup(fields, `Driver example ${String(index + 1).padStart(2, '0')}`, [
    ['Issue title', `driverExamples.${index}.title`, item.title],
    ['What this optimizer does not fix', `driverExamples.${index}.description`, item.description, true]
  ]));
  content.downloads.forEach((item, index) => addGroup(fields, `Download ${String(index + 1).padStart(2, '0')}`, [
    ['Button text', `downloads.${index}.name`, item.name], ['Version note', `downloads.${index}.version`, item.version],
    ['GitHub URL (HTTPS)', `downloads.${index}.url`, item.url]
  ]));
}

function getPath(object, path) {
  return path.split('.').reduce((current, key) => current[key], object);
}

function setPath(object, path, value) {
  const keys = path.split('.');
  const last = keys.pop();
  const target = keys.reduce((current, key) => current[key], object);
  target[last] = value;
}

document.querySelector('#dashboard-nav').addEventListener('click', openDashboard);
document.querySelector('#account-nav').addEventListener('click', () => openAuth('register'));
document.querySelectorAll('.auth-tab').forEach((tab) => tab.addEventListener('click', () => setAuthMode(tab.dataset.mode)));
document.querySelector('#back-to-site').addEventListener('click', () => {
  document.querySelector('#dashboard').hidden = true;
  document.querySelector('.site-shell').hidden = false;
  window.scrollTo(0, 0);
});
document.querySelector('#signout-button').addEventListener('click', async () => {
  try { await api('/api/logout', { method: 'POST', body: '{}' }); } catch { /* Session may already have expired. */ }
  signedInUser = null;
  document.querySelector('#dashboard').hidden = true;
  document.querySelector('.site-shell').hidden = false;
  notify('Signed out.');
});
authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.querySelector('#auth-submit');
  const error = document.querySelector('#auth-error');
  button.disabled = true;
  error.textContent = '';
  try {
    const formData = new FormData(authForm);
    const result = await api(`/api/${authMode}`, {
      method: 'POST',
      body: JSON.stringify({ username: formData.get('username'), password: formData.get('password') })
    });
    signedInUser = result.user;
    dialog.close();
    authForm.reset();
    notify(authMode === 'login' ? 'Signed in.' : 'Account created. You are signed in.');
    if (signedInUser.isOwner) openDashboard();
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    button.disabled = false;
  }
});
document.querySelector('#content-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const updated = structuredClone(siteContent);
  document.querySelectorAll('#content-fields [data-path]').forEach((input) => setPath(updated, input.dataset.path, input.value.trim()));
  const message = document.querySelector('#save-message');
  message.textContent = 'Saving...';
  try {
    const result = await api('/api/content', { method: 'PUT', body: JSON.stringify(updated) });
    renderContent(result.content);
    renderEditor(result.content);
    message.textContent = 'Saved. Public page updated.';
    notify('Site content saved.');
  } catch (requestError) {
    message.textContent = requestError.message;
  }
});

document.querySelector('#mobile-menu').addEventListener('click', (event) => {
  const expanded = event.currentTarget.getAttribute('aria-expanded') === 'true';
  event.currentTarget.setAttribute('aria-expanded', String(!expanded));
  document.querySelector('.navigation').classList.toggle('menu-open', !expanded);
});

document.querySelectorAll('.navigation a').forEach((link) => link.addEventListener('click', () => {
  document.querySelector('.navigation').classList.remove('menu-open');
  document.querySelector('#mobile-menu').setAttribute('aria-expanded', 'false');
}));

enableWebsitePointer();

(async function initialize() {
  try {
    const [contentResult, sessionResult] = await Promise.all([api('/api/content'), api('/api/me')]);
    renderContent(contentResult.content);
    signedInUser = sessionResult.user;
  } catch (error) {
    console.error(error);
    notify('Could not connect to the site server.');
  }
})();
