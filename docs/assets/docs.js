'use strict';
const sections = [...document.querySelectorAll('section[data-search]')];
const search = document.getElementById('search');
const status = document.getElementById('search-status');
const links = [...document.querySelectorAll('nav a')];
search.addEventListener('input', () => {
  const words = search.value.toLocaleLowerCase('de').trim().split(/\s+/).filter(Boolean);
  let count = 0;
  sections.forEach(section => {
    const match = words.every(word => section.textContent.toLocaleLowerCase('de').includes(word));
    section.hidden = !match;
    links.find(link => link.hash === '#' + section.id).hidden = !match;
    if (match) count++;
  });
  status.textContent = words.length ? `${count} von ${sections.length} Kapiteln gefunden. Suche leeren für die vollständige Dokumentation.` : '';
});
document.getElementById('print').addEventListener('click', () => window.print());
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      links.forEach(link => {
        const active = link.hash === '#' + entry.target.id;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    });
  }, { rootMargin: '-5% 0px -70% 0px' });
  sections.forEach(section => observer.observe(section));
}
