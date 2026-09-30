const drivers = [
  {
    title: 'Wi-Fi driver failed',
    description: "This optimizer does not install or repair Wi-Fi drivers. Get a compatible driver from your PC or Wi-Fi adapter manufacturer's support page."
  },
  {
    title: 'Bluetooth driver failed',
    description: "This optimizer does not install or repair Bluetooth drivers. Get a compatible driver from your PC or Bluetooth adapter manufacturer's support page."
  }
];

const downloads = [
  {
    name: 'download optimizer BETA V1',
    version: 'PLATINUM / RELEASE BUILD',
    url: 'https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum-Optimizer-Homi.cmd'
  },
  {
    name: 'download latest optimizer BETA',
    version: 'PLATINUM / LATEST BETA',
    url: 'https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum-Optimizer-Homi.BETA.cmd'
  },
  {
    name: 'download original optimizer',
    version: 'PLATINUM / ORIGINAL V9.2',
    url: 'https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum+Optimizer.V9.2.original.cmd'
  }
];

function renderDriverExamples() {
  const list = document.querySelector('#driver-example-list');
  list.replaceChildren(...drivers.map((item, index) => {
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
}

function renderDownloads() {
  const list = document.querySelector('#download-list');
  list.replaceChildren(...downloads.map((item, index) => {
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
    link.href = item.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.innerHTML = `<span>${item.name}</span><span aria-hidden="true">↗</span>`;
    row.append(number, info, link);
    return row;
  }));
}

function observeScrollReveals() {
  const targets = document.querySelectorAll('.reveal-target');
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    targets.forEach((target) => target.classList.add('reveal-visible'));
    return;
  }
  targets.forEach((target, index) => target.style.setProperty('--reveal-delay', `${(index % 4) * 75}ms`));
  const revealVisible = () => {
    document.querySelectorAll('.reveal-target:not(.reveal-visible)').forEach((target) => {
      const bounds = target.getBoundingClientRect();
      if (bounds.top < window.innerHeight * 0.9 && bounds.bottom > 0) {
        target.classList.add('reveal-visible');
      }
    });
  };
  window.addEventListener('scroll', revealVisible, { passive: true });
  window.addEventListener('resize', revealVisible);
  revealVisible();
}

function enablePointerEffects() {
  const tracker = document.querySelector('#cursor-tracker');
  if (!window.matchMedia('(pointer: fine)').matches || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.addEventListener('pointermove', (event) => {
    if (event.pointerType !== 'mouse') return;
    tracker.style.setProperty('--cursor-x', `${event.clientX}px`);
    tracker.style.setProperty('--cursor-y', `${event.clientY}px`);
    tracker.classList.add('visible');
    const target = event.target instanceof Element ? event.target.closest('a, button') : null;
    tracker.classList.toggle('over-control', Boolean(target));
    const hero = document.querySelector('.hero');
    const bounds = hero.getBoundingClientRect();
    const insideHero = event.clientY >= bounds.top && event.clientY <= bounds.bottom;
    const horizontal = insideHero ? (event.clientX - (bounds.left + bounds.width / 2)) * 0.018 : 0;
    const vertical = insideHero ? (event.clientY - (bounds.top + bounds.height / 2)) * 0.018 : 0;
    hero.style.setProperty('--hero-drift-x', `${horizontal}px`);
    hero.style.setProperty('--hero-drift-y', `${vertical}px`);
    hero.style.setProperty('--hero-content-shift-x', `${horizontal * -0.12}px`);
    hero.style.setProperty('--hero-content-shift-y', `${vertical * -0.12}px`);
  });
  document.addEventListener('pointerdown', () => tracker.classList.add('pressed'));
  window.addEventListener('pointerup', () => tracker.classList.remove('pressed'));
  window.addEventListener('blur', () => tracker.classList.remove('visible', 'over-control', 'pressed'));
}

renderDriverExamples();
renderDownloads();
observeScrollReveals();
enablePointerEffects();

document.querySelector('#mobile-menu').addEventListener('click', (event) => {
  const expanded = event.currentTarget.getAttribute('aria-expanded') === 'true';
  event.currentTarget.setAttribute('aria-expanded', String(!expanded));
  document.querySelector('.navigation').classList.toggle('menu-open', !expanded);
});

document.querySelectorAll('.navigation a').forEach((link) => link.addEventListener('click', () => {
  document.querySelector('.navigation').classList.remove('menu-open');
  document.querySelector('#mobile-menu').setAttribute('aria-expanded', 'false');
}));
