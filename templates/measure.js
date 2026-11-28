/* Measure page: one measure across every place, in three tabs (Map, Table, Relationships).
   Geometry comes from the shared geo file; this page sends only its own bin classes and table values. */
(function () {
  var M = JSON.parse(document.getElementById("measure-data").textContent), G = window.LEDGER_GEO, NS = "http://www.w3.org/2000/svg";
  var root = M.root, svg = document.getElementById("map"), sel = new URLSearchParams(location.search).get("sel") || "";

  // Old links: schools.html?ind=<key> now lives at schools/<key>.html.
  var want = new URLSearchParams(location.search).get("ind");
  if (M.front && want && want !== M.key) {
    var go = root + M.sect + "/" + encodeURIComponent(want) + ".html" + (location.hash || "");
    return location.replace(go);
  }

  // Map
  svg.setAttribute("viewBox", G.vb);
  var els = {};
  G.ids.forEach(function (id, i) {
    var a = document.createElementNS(NS, "a"), p = document.createElementNS(NS, "path"), t = document.createElementNS(NS, "title");
    a.setAttribute("href", root + G.href + id + ".html");
    p.setAttribute("d", G.d[i]); p.setAttribute("class", M.cls[i]); p.setAttribute("id", "p" + id);
    t.textContent = G.n[i] + (M.tab[i] ? ": " + M.tab[i][1] : "");
    p.appendChild(t); a.appendChild(p); svg.appendChild(a); els[id] = p;
  });
  function outline(code) {
    svg.querySelectorAll("path.sel").forEach(function (p) { p.classList.remove("sel"); });
    var p = els[code];
    if (p) { p.classList.add("sel"); svg.appendChild(p.parentNode); }
  }

  // Tabs. The hash names the open tab; the old step anchors (#s3, #s4, #s5) open Relationships at that step.
  var tabs = [].slice.call(document.querySelectorAll(".mtabs [role=tab]")), panels = { map: "t-map", table: "t-table", relationships: "t-rel" };
  function show(t, push) {
    if (!document.getElementById(panels[t])) t = "map";
    tabs.forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-t") === t ? "true" : "false"); });
    Object.keys(panels).forEach(function (k) { var el = document.getElementById(panels[k]); if (el) el.hidden = k !== t; });
    if (t === "table") draw();
    if (push) try { history.replaceState(null, "", location.pathname + location.search + (t === "map" ? "" : "#" + t)); } catch (e) {}
  }
  function fromHash() {
    var h = location.hash.slice(1);
    if (/^s[345]$/.test(h)) { show("relationships"); var a = document.getElementById(h); if (a) setTimeout(function () { a.scrollIntoView(); }, 0); }
    else if (/^s[12]$/.test(h)) { show("map"); var b = document.getElementById(h); if (b) setTimeout(function () { b.scrollIntoView(); }, 0); }
    else if (panels[h]) show(h);
    else if (h === "" || h === "map") show("map");
  }
  tabs.forEach(function (b, i) {
    b.addEventListener("click", function () { show(b.getAttribute("data-t"), true); });
    b.addEventListener("keydown", function (e) {
      var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
      if (j === null) return;
      var n = tabs[(j + tabs.length) % tabs.length]; n.focus(); n.click();
    });
  });
  document.querySelectorAll(".golink").forEach(function (b) {
    b.addEventListener("click", function () { show(b.getAttribute("data-t"), true); document.querySelector(".mtabs").scrollIntoView(); });
  });
  window.addEventListener("hashchange", fromHash);

  // Table
  var tb = document.getElementById("tb"), tf = document.getElementById("tf"), sortBy = "val", dir = -1;
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function draw() {
    var rows = [], q = (tf.value || "").toLowerCase();
    G.ids.forEach(function (id, i) { rows.push({ i: i, id: id, name: G.n[i], x: M.tab[i] }); });
    var vals = rows.filter(function (r) { return r.x && r.x[0] !== null; });
    vals.forEach(function (r) { r.rank = 1 + vals.filter(function (o) { return o.x[0] > r.x[0]; }).length; });
    rows.sort(function (a, b) {
      if (!a.x !== !b.x) return a.x ? -1 : 1;  // blanks always last
      if (sortBy === "name") return dir * a.name.localeCompare(b.name);
      var av = a.x && a.x[0], bv = b.x && b.x[0];
      if (av === null || bv === null || av === undefined) return a.x && b.x ? a.x[1].localeCompare(b.x[1]) || a.name.localeCompare(b.name) : 0;
      return sortBy === "rank" ? -dir * (bv - av) || a.name.localeCompare(b.name) : dir * (av - bv) || a.name.localeCompare(b.name);
    });
    var shown = rows.filter(function (r) { return !q || r.name.toLowerCase().indexOf(q) >= 0; });
    tb.innerHTML = shown.map(function (r) {
      return "<tr" + (r.id === sel ? " class='on'" : "") + "><td class='num'>" + (r.rank ? r.rank : "") + "</td><td><a href='" + root + G.href + r.id + ".html'>" + esc(r.name) +
        "</a></td><td class='num'>" + (r.x ? "<b class='" + r.x[2] + "'>" + esc(r.x[1]) + "</b>" : "<span class='quiet'>Not available</span>") + "</td></tr>";
    }).join("");
    document.querySelectorAll(".maptable th").forEach(function (th) {
      var s = th.querySelector("button").getAttribute("data-s");
      th.setAttribute("aria-sort", s === sortBy ? (dir > 0 ? "ascending" : "descending") : "none");
    });
    document.getElementById("tcount").textContent = (q ? shown.length + " of " : "") + rows.length + " " + M.nouns + "; " + vals.length + " with a value. Click a column to sort.";
  }
  document.querySelectorAll(".maptable th button").forEach(function (b) {
    b.addEventListener("click", function () {
      var s = b.getAttribute("data-s");
      if (s === sortBy) dir = -dir; else { sortBy = s; dir = s === "name" || s === "rank" ? 1 : -1; }
      draw();
    });
  });
  tf.addEventListener("input", draw);

  // Switching measures keeps the place you follow and the tab you are on.
  function carry(href) {
    var u = new URL(href, location.href);
    if (sel) u.searchParams.set("sel", sel); else u.searchParams.delete("sel");
    var t = location.hash.slice(1);
    if (!u.hash && (t === "table" || t === "relationships")) u.hash = t;
    return u.href;
  }
  var msel = document.getElementById("msel");
  msel.addEventListener("change", function () { location.href = carry(root + M.sect + "/" + msel.value + ".html"); });
  document.querySelectorAll(".mlink:not(.all), .mlist a").forEach(function (a) {
    a.addEventListener("click", function (e) { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); location.href = carry(a.getAttribute("href")); });
  });
  document.addEventListener("ledger:sel", function (e) { sel = e.detail || ""; outline(sel); if (!document.getElementById("t-table").hidden) draw(); });
  outline(sel);

  // Downloads: a standalone picture of the map, with its title, legend, period and source drawn in.
  function mk(tag, at, txt) { var e = document.createElementNS(NS, tag); for (var k in at) e.setAttribute(k, at[k]); if (txt != null) e.textContent = txt; return e; }
  function wrap(text, max) {
    var words = String(text).split(" "), lines = [], line = "";
    words.forEach(function (w) { if ((line + " " + w).trim().length > max) { lines.push(line.trim()); line = w; } else line += " " + w; });
    if (line.trim()) lines.push(line.trim());
    return lines;
  }
  function picture() {
    var cs = getComputedStyle(document.body), font = cs.fontFamily, ink = cs.color, card = getComputedStyle(svg).backgroundColor;
    var sub = getComputedStyle(document.querySelector(".quiet")).color, vb = svg.viewBox.baseVal, W = vb.width, P = 24;
    var tl = wrap(M.title, 70), top = P + tl.length * 30 + 6;
    var items = [].slice.call(document.querySelectorAll("#t-map .legend > div")).map(function (d) {
      var sw = d.querySelector(".sw"), sp = d.querySelectorAll("span");
      return { na: sw.classList.contains("na"), color: getComputedStyle(sw).backgroundColor, label: sp[1].textContent, n: sp[2] ? sp[2].textContent : "" };
    });
    var cols = 3, rowH = 26, legTop = top + vb.height + 18, legH = Math.ceil(items.length / cols) * rowH;
    var foot = wrap(M.foot, 130), H = legTop + legH + 12 + foot.length * 18 + P;
    var out = mk("svg", { xmlns: NS, width: W + 2 * P, height: H, viewBox: "0 0 " + (W + 2 * P) + " " + H, "font-family": font });
    var defs = mk("defs", {}), pat = mk("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
    pat.appendChild(mk("rect", { width: 6, height: 6, fill: card })); pat.appendChild(mk("rect", { width: 2, height: 6, fill: sub, "fill-opacity": 0.45 }));
    defs.appendChild(pat); out.appendChild(defs);
    out.appendChild(mk("rect", { width: W + 2 * P, height: H, fill: card }));
    tl.forEach(function (l, i) { out.appendChild(mk("text", { x: P, y: P + 22 + i * 30, "font-size": 24, "font-weight": 800, fill: ink }, l)); });
    var g = mk("g", { transform: "translate(" + P + "," + top + ")" });
    svg.querySelectorAll("path").forEach(function (p) {
      var pc = getComputedStyle(p), na = p.classList.contains("na"), on = p.classList.contains("sel");
      var q = mk("path", { d: p.getAttribute("d"), fill: na ? "url(#hatch)" : pc.fill, stroke: on ? ink : card, "stroke-width": on ? 2 : 0.6 });
      q.appendChild(mk("title", {}, p.querySelector("title") ? p.querySelector("title").textContent : ""));
      g.appendChild(q);
    });
    out.appendChild(g);
    var colW = W / cols;
    items.forEach(function (it, i) {
      var x = P + (i % cols) * colW, y = legTop + Math.floor(i / cols) * rowH;
      out.appendChild(mk("rect", { x: x, y: y, width: 22, height: 16, fill: it.na ? "url(#hatch)" : it.color, stroke: sub, "stroke-opacity": 0.5 }));
      var lt = mk("text", { x: x + 30, y: y + 13, "font-size": 15, fill: ink }, it.label);
      if (it.n) lt.appendChild(mk("tspan", { fill: sub, dx: 8 }, it.n + " " + (it.n === "1" ? M.noun : M.nouns)));
      out.appendChild(lt);
    });
    foot.forEach(function (l, i) { out.appendChild(mk("text", { x: P, y: legTop + legH + 12 + 13 + i * 18, "font-size": 13, fill: sub }, l)); });
    return { svg: out, w: W + 2 * P, h: H };
  }
  function save(blob, name) {
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  document.querySelectorAll(".dlbtn").forEach(function (b) {
    b.addEventListener("click", function () {
      var pic = picture(), txt = new XMLSerializer().serializeToString(pic.svg), name = M.level + "-" + M.key;
      if (b.getAttribute("data-f") === "svg") return save(new Blob([txt], { type: "image/svg+xml" }), name + ".svg");
      var img = new Image(), scale = 2;
      img.onload = function () {
        var c = document.createElement("canvas"); c.width = pic.w * scale; c.height = pic.h * scale;
        var x = c.getContext("2d"); x.scale(scale, scale); x.drawImage(img, 0, 0);
        c.toBlob(function (bl) { save(bl, name + ".png"); }, "image/png");
      };
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(txt);
    });
  });

  fromHash();
})();
