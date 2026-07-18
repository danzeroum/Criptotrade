/* ============================================================
   Criptotrade — tooltips de descoberta (hover → explicação)
   Engine leve por delegação: qualquer elemento com [data-tip]
   mostra um balão explicativo ao passar o mouse. Pensado para
   quem está conhecendo a plataforma entender cada controle.
   ============================================================ */
(function () {
  if (window.__ctTooltips) return;
  window.__ctTooltips = true;

  var tip = document.createElement('div');
  tip.className = 'ct-tip';
  tip.setAttribute('role', 'tooltip');
  tip.style.opacity = '0';
  tip.style.visibility = 'hidden';
  var attached = false;
  var showTimer = null;
  var current = null;

  function ensureAttached() {
    if (!attached && document.body) { document.body.appendChild(tip); attached = true; }
  }

  function place(el) {
    ensureAttached();
    var text = el.getAttribute('data-tip');
    if (!text) return;
    tip.textContent = text;
    tip.style.visibility = 'hidden';
    tip.style.opacity = '0';
    tip.style.left = '0px';
    tip.style.top = '0px';
    // measure
    var tr = tip.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    var margin = 8, pad = 8;
    var vw = window.innerWidth, vh = window.innerHeight;
    var left = r.left + r.width / 2 - tr.width / 2;
    left = Math.max(pad, Math.min(left, vw - tr.width - pad));
    var top = r.top - tr.height - margin;       // prefer above
    var below = false;
    if (top < pad) { top = r.bottom + margin; below = true; }  // flip below
    if (top + tr.height > vh - pad) top = Math.max(pad, vh - tr.height - pad);
    tip.style.left = Math.round(left) + 'px';
    tip.style.top = Math.round(top) + 'px';
    tip.setAttribute('data-pos', below ? 'below' : 'above');
    tip.style.visibility = 'visible';
    tip.style.opacity = '1';
  }

  function hide() {
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
    current = null;
    tip.style.opacity = '0';
    tip.style.visibility = 'hidden';
  }

  document.addEventListener('pointerover', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('[data-tip]') : null;
    if (!el || el === current) return;
    if (!el.getAttribute('data-tip')) return;
    current = el;
    if (showTimer) clearTimeout(showTimer);
    showTimer = setTimeout(function () { if (current === el && el.isConnected) place(el); }, 320);
  }, true);

  document.addEventListener('pointerout', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('[data-tip]') : null;
    if (!el) return;
    var to = e.relatedTarget;
    if (to && el.contains(to)) return;
    hide();
  }, true);

  document.addEventListener('pointerdown', hide, true);
  window.addEventListener('scroll', hide, true);
  window.addEventListener('blur', hide);
})();
