document.querySelectorAll('.search-toggle').forEach(button => {
  button.addEventListener('click', () => {
    const panel = document.getElementById('search-panel');
    panel.hidden = !panel.hidden;
    document.querySelectorAll('.search-toggle').forEach(b => b.setAttribute('aria-expanded', String(!panel.hidden)));
    if (!panel.hidden) { window.scrollTo({top: 0, behavior: 'smooth'}); document.getElementById('header-search').focus(); }
  });
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.getElementById('search-panel').hidden = true;
    document.querySelectorAll('.search-toggle').forEach(b => b.setAttribute('aria-expanded', 'false'));
  }
});
document.querySelectorAll('[data-autosubmit]').forEach(select => select.addEventListener('change', () => select.form.requestSubmit()));
document.querySelectorAll('.dismiss-flash').forEach(button => button.addEventListener('click', () => button.closest('.flash').remove()));
document.querySelectorAll('[data-cover]').forEach(img => {
  const fallback = () => { img.onerror = null; img.src = '/static/cover-fallback.svg'; };
  img.addEventListener('error', fallback, {once: true});
  if (img.complete && img.naturalWidth === 0) fallback();
});
const money = cents => (cents / 100).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
document.querySelectorAll('[data-shipping]').forEach(radio => radio.addEventListener('change', () => {
  const freight = Number(radio.dataset.shipping);
  document.getElementById('shipping-total').textContent = freight ? money(freight) : 'Grátis';
  const total = document.getElementById('checkout-total');
  total.textContent = money(Number(total.dataset.subtotal) + freight);
}));
document.getElementById('checkout-form')?.addEventListener('submit', () => {
  const button = document.getElementById('confirm-order');
  button.disabled = true;
  button.textContent = 'Conferindo sua coleção…';
});
window.addEventListener('pageshow', () => {
  const button = document.getElementById('confirm-order');
  if (button) { button.disabled = false; button.textContent = 'Confirmar pedido simulado'; }
});
