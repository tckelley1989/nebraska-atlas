// Header search: systems, counties and towns. The index loads on first focus.
(function () {
  var box = document.getElementById("q"), list = document.getElementById("qr"), form = box && box.form;
  if (!box) return;
  form.hidden = false;
  var root = form.getAttribute("data-root"), idx = null, hits = [], cur = -1;
  function load() {
    if (idx || document.getElementById("qidx")) return;
    var s = document.createElement("script");
    s.id = "qidx"; s.src = root + "assets/search-index.js";
    s.onload = function () { idx = window.LEDGER_SEARCH || []; run(); };
    document.head.appendChild(s);
  }
  function norm(t) { return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9 ]/g, " "); }
  function run() {
    var q = norm(box.value).trim();
    list.innerHTML = ""; hits = []; cur = -1;
    if (!idx || !q) { list.hidden = true; box.setAttribute("aria-expanded", "false"); return; }
    var words = q.split(/\s+/);
    idx.forEach(function (e) {
      var n = norm(e.n), hay = n + " " + norm(e.x);
      if (words.every(function (w) { return hay.indexOf(w) >= 0; }))
        hits.push({ e: e, s: (n.indexOf(q) === 0 ? 0 : n.indexOf(q) > 0 ? 1 : 2) + (e.k === "Town" ? 0.5 : 0) });
    });
    hits.sort(function (a, b) { return a.s - b.s || a.e.n.localeCompare(b.e.n); });
    hits = hits.slice(0, 8);
    if (!hits.length) { list.innerHTML = '<li class="none-found">No match</li>'; }
    hits.forEach(function (h, i) {
      var li = document.createElement("li");
      li.id = "qr" + i; li.setAttribute("role", "option");
      li.innerHTML = '<a href="' + root + h.e.u + '"><b></b><span></span></a>';
      li.querySelector("b").textContent = h.e.n;
      li.querySelector("span").textContent = h.e.k + (h.e.x ? " · " + h.e.x : "");
      list.appendChild(li);
    });
    list.hidden = false; box.setAttribute("aria-expanded", "true");
  }
  function mark(i) {
    var items = list.querySelectorAll("[role=option]");
    if (!items.length) return;
    cur = (i + items.length) % items.length;
    items.forEach(function (li, j) { li.setAttribute("aria-selected", j === cur ? "true" : "false"); });
    box.setAttribute("aria-activedescendant", "qr" + cur);
  }
  box.addEventListener("focus", load);
  box.addEventListener("input", function () { load(); run(); });
  box.addEventListener("keydown", function (ev) {
    if (ev.key === "ArrowDown") { mark(cur + 1); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { mark(cur - 1); ev.preventDefault(); }
    else if (ev.key === "Escape") { box.value = ""; run(); }
  });
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var h = hits[cur >= 0 ? cur : 0];
    if (h) location.href = root + h.e.u;
  });
  document.addEventListener("click", function (ev) { if (!form.contains(ev.target)) { list.hidden = true; box.setAttribute("aria-expanded", "false"); } });
})();
