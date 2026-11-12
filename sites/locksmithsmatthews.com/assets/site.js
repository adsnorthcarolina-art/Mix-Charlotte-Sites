/* Mix Charlotte Sites – shared behaviour: menu, back-to-top, tracking events, lead form */
(function () {
  window.dataLayer = window.dataLayer || [];
  function track(name, extra) {
    var ev = { event: name };
    for (var k in extra || {}) ev[k] = extra[k];
    window.dataLayer.push(ev);
    if (typeof window.gtag === 'function') window.gtag('event', name, extra || {});
  }

  var burger = document.querySelector('.burger');
  var nav = document.querySelector('.nav');
  if (burger && nav) {
    burger.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var top = document.querySelector('.totop');
  if (top) {
    window.addEventListener('scroll', function () {
      top.classList.toggle('show', window.scrollY > 500);
    });
    top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (href.indexOf('tel:') === 0) track('phone_call', { link_url: href, page: location.pathname });
    else if (href.indexOf('sms:') === 0) track('sms_click', { link_url: href, page: location.pathname });
    else if (href.indexOf('wa.me') > -1) track('whatsapp_click', { link_url: href, page: location.pathname });
  });

  var form = document.querySelector('form.lead-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var status = form.querySelector('.form-status');
      var btn = form.querySelector('button[type=submit]');
      if (form.querySelector('[name=botcheck]').checked) return;
      btn.disabled = true;
      status.textContent = 'Sending...';
      fetch(form.action, {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
        body: new FormData(form)
      }).then(function (r) { return r.json(); }).then(function (res) {
        if (res.success) {
          track('lead_form_submit', { page: location.pathname });
          form.reset();
          status.textContent = 'Thank you. We received your request and will call you back shortly.';
        } else {
          status.textContent = 'Something went wrong. Please call us instead.';
        }
      }).catch(function () {
        status.textContent = 'Something went wrong. Please call us instead.';
      }).then(function () { btn.disabled = false; });
    });
  }
})();
