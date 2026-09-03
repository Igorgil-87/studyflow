(() => {
  'use strict';

  const body = document.body;
  const sidebar = document.getElementById('appSidebar');
  const toggle = document.getElementById('mobileNavToggle');
  const closeButton = document.getElementById('mobileNavClose');
  const backdrop = document.getElementById('mobileNavBackdrop');

  if (!body || !sidebar || !toggle || !backdrop) return;

  let previouslyFocused = null;
  const desktopQuery = window.matchMedia('(min-width: 1024px)');

  const focusableSelector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function focusableElements() {
    return Array.from(sidebar.querySelectorAll(focusableSelector)).filter((element) => {
      return !element.hasAttribute('hidden') && element.offsetParent !== null;
    });
  }

  function setOpen(open, { restoreFocus = true } = {}) {
    if (desktopQuery.matches) open = false;

    body.classList.toggle('nav-open', open);
    sidebar.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    sidebar.setAttribute('aria-hidden', String(!open && !desktopQuery.matches));
    backdrop.hidden = !open;

    if (open) {
      previouslyFocused = document.activeElement;
      requestAnimationFrame(() => {
        (closeButton || focusableElements()[0] || sidebar).focus();
      });
    } else if (restoreFocus && previouslyFocused && typeof previouslyFocused.focus === 'function') {
      previouslyFocused.focus();
    }
  }

  function closeNav(options) {
    setOpen(false, options);
  }

  toggle.addEventListener('click', () => {
    setOpen(!body.classList.contains('nav-open'));
  });

  if (closeButton) closeButton.addEventListener('click', () => closeNav());
  backdrop.addEventListener('click', () => closeNav());

  sidebar.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (link && !desktopQuery.matches) closeNav({ restoreFocus: false });
  });

  document.addEventListener('keydown', (event) => {
    if (!body.classList.contains('nav-open')) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      closeNav();
      return;
    }

    if (event.key !== 'Tab') return;

    const focusable = focusableElements();
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  function syncViewport() {
    if (desktopQuery.matches) {
      body.classList.remove('nav-open');
      sidebar.classList.remove('is-open');
      sidebar.removeAttribute('aria-hidden');
      backdrop.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Abrir menu');
    } else {
      sidebar.setAttribute('aria-hidden', String(!body.classList.contains('nav-open')));
    }
  }

  if (typeof desktopQuery.addEventListener === 'function') {
    desktopQuery.addEventListener('change', syncViewport);
  } else {
    desktopQuery.addListener(syncViewport);
  }

  syncViewport();
})();
