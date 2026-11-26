/* Deeper dive place mode: ?sel=<code> marks one place in every chart and draws its own step 3.
   Every number comes from the page's embedded data, written at build. Without a selection the page is the state view. */
(function () {
  var D = JSON.parse(document.getElementById("dive-data").textContent), P = D.places, S = window.DIVE_PLACES || {}, X = window.DIVE_EXTRA || {};
  Object.keys(P).forEach(function (c) { [S[c], X[c]].forEach(function (s) { for (var k in s || {}) P[c][k] = s[k]; }); });
  var INK = "#2c2c2c", SUB = "#5e5a54", RULE = "#ddd5c8", CARD = "#fbf8f3", RUST = "#c1432e", SLATE = "#4b6777",
      SLATE_L = "#8aa0ad", SLATE_LL = "#c3cfd6", LOCAL = "#8a847b", LOCAL_L = "#bdb7ad", NEED1 = "#e6ded1", NEED2 = "#d6ccbc", NS = "http://www.w3.org/2000/svg";
  var MINUS = "−";
  function money(x) { return (x < 0 ? MINUS : "") + "$" + Math.round(Math.abs(x)).toLocaleString("en-US"); }
  function mil(x) { return "$" + (x / 1e6).toFixed(1) + "M"; }
  function pct(x, d) { d = d === undefined ? 1 : d; var s = Math.abs(x).toFixed(d) + "%"; return x > 0 ? "+" + s : x < 0 ? MINUS + s : s; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function svg(w, h, label) { var s = el("svg", { viewBox: "0 0 " + w + " " + h, role: "img", "aria-label": label, "class": "dchart" }); return s; }
  function txt(s, x, y, t, o) {
    o = o || {}; var e = el("text", { x: x, y: y, "font-size": o.fs || 12, fill: o.fill || INK, "text-anchor": o.anchor || "start", "font-weight": o.fw || 400 }, t);
    if (o.halo) { e.setAttribute("stroke", CARD); e.setAttribute("stroke-width", 4); e.setAttribute("paint-order", "stroke"); }
    s.appendChild(e); return e;
  }

  function mark(code) {
    document.querySelectorAll(".sel-lab").forEach(function (e) { e.remove(); });
    document.querySelectorAll(".dd.on, .db.on").forEach(function (e) { e.classList.remove("on"); });
    document.querySelectorAll("[data-l]").forEach(function (e) { e.style.display = e.getAttribute("data-l") === code ? "none" : ""; });
    if (!code) return;
    var p = P[code];
    document.querySelectorAll('[data-c="' + code + '"]').forEach(function (e) {
      e.classList.add("on");
      var svgEl = e.ownerSVGElement, vb = svgEl.viewBox.baseVal, bb;
      if (e.tagName === "circle") { var cx = +e.getAttribute("cx"), cy = +e.getAttribute("cy"); bb = { x: cx - 6, y: cy - 6, width: 12, height: 12 }; }
      else if (e.tagName === "rect") bb = { x: +e.getAttribute("x"), y: +e.getAttribute("y"), width: +e.getAttribute("width"), height: +e.getAttribute("height") };
      else { var m = /M([\d.\-]+) ([\d.\-]+)/.exec(e.getAttribute("d")) || [0, 0, 0]; bb = { x: +m[1], y: +m[2] - 5, width: 10, height: 10 }; }
      e.parentNode.appendChild(e);
      var label = (e.classList.contains("db") || svgEl.classList.contains("factors")) ? p.s : p.s + " " + p.v;
      var right = bb.x + bb.width + 10 + label.length * 7 < vb.width;
      var t = el("text", { "class": "sel-lab", x: right ? bb.x + bb.width + 8 : bb.x - 8, y: e.classList.contains("db") ? Math.min(bb.y + bb.height + 14, vb.height - 4) : bb.y - 4,
        "font-size": 12.5, "font-weight": 700, fill: INK, "text-anchor": right ? "start" : "end", stroke: CARD, "stroke-width": 4, "paint-order": "stroke" }, label);
      svgEl.appendChild(t);
      // drop a fixed place label the selected place's label would sit on (positions from attributes: hidden SVGs have no boxes)
      var tx = +t.getAttribute("x"), ty = +t.getAttribute("y"), w = label.length * 12.5 * 0.55, x0 = right ? tx : tx - w;
      svgEl.querySelectorAll("text[data-l]").forEach(function (o) {
        var ox = +o.getAttribute("x"), oy = +o.getAttribute("y"), ow = o.textContent.length * 12 * 0.55, a = o.getAttribute("text-anchor");
        var o0 = a === "end" ? ox - ow : ox;
        if (o0 < x0 + w && o0 + ow > x0 && oy - 12 < ty + 2 && oy + 2 > ty - 13) {
          o.style.display = "none";
          var c = o.getAttribute("data-l");
          svgEl.querySelectorAll('line[data-l="' + c + '"]').forEach(function (l) { l.style.display = "none"; });
        }
      });
    });
  }

  function bridge(f, W) {
    var phone = W < 600, L = phone ? 8 : 190, R = W - 12, top = Math.max(f.need, f.aid, f.res);
    var X = function (v) { return L + v / top * (R - L); };
    var parts = function (list, cols) { return list.map(function (t, i) { return [t[0], t[1], cols(i, t[0])]; }); };
    var needParts = f.need_parts.slice(0, 4); var rest = f.need_parts.slice(4).reduce(function (s, t) { return s + t[1]; }, 0);
    if (rest) needParts.push([(f.need_parts.length - 4) + " other parts", rest]);
    var resCol = function (i, n) { return n === "Local effort" ? LOCAL : n === "Other receipts" ? LOCAL_L : n.indexOf("Foundation") === 0 ? SLATE_L : SLATE_LL; };
    var aidCol = function (i, n) { return n === "Equalization aid" ? SLATE : n.indexOf("Foundation") === 0 ? SLATE_L : SLATE_LL; };
    var rows = [["Formula need", parts(needParts, function (i) { return i % 2 ? NEED2 : NEED1; }), 0, f.need],
                ["Formula resources", parts(f.res_parts, resCol), 0, f.res]];
    if (f.eq > 0) rows.push(["Equalization aid", [["Equalization aid", f.eq, SLATE]], f.res, f.eq]);
    rows.push(["Total TEEOSA aid", parts(f.aid_parts, aidCol), 0, f.aid]);
    var s = svg(W, 10, "Formula need, resources and aid"), y = 10, bh = 30;
    rows.forEach(function (r) {
      if (phone) { txt(s, L, y + 12, r[0] + " " + mil(r[3]), { fw: 700, fs: 13 }); y += 20; }
      else { txt(s, 0, y + bh / 2 - 2, r[0], { fw: 700, fs: 13 }); txt(s, 0, y + bh / 2 + 14, mil(r[3]), { fill: SUB }); }
      var x = X(r[2]), start = r[2], also = [];
      r[1].forEach(function (seg) {
        var w = X(start + seg[1]) - X(start);
        s.appendChild(el("rect", { x: x, y: y, width: Math.max(w, 0.5), height: bh, fill: seg[2], stroke: CARD, "stroke-width": 1.5 }));
        var t = seg[0] + " " + mil(seg[1]);
        if (t.length * 6.8 + 12 < w) txt(s, x + 6, y + bh / 2 + 4, t, { fill: (seg[2] === SLATE || seg[2] === LOCAL) ? CARD : INK });
        else also.push(t);
        x += w; start += seg[1];
      });
      y += bh + 4;
      if (also.length) {
        var line = "Also:", lines = [];
        also.forEach(function (t) { var n = line + (line === "Also:" ? " " : " · ") + t; if (n.length * 6.3 > R - L && line !== "Also:") { lines.push(line); line = t; } else line = n; });
        lines.push(line);
        lines.forEach(function (ln) { txt(s, L, y + 11, ln, { fill: SUB, fs: 11.5 }); y += 16; });
      }
      y += phone ? 26 : 18;
    });
    s.setAttribute("viewBox", "0 0 " + W + " " + y);
    return s;
  }

  function factorBars(x, W, peerMed) {
    var phone = W < 600, L = phone ? 8 : 250, R = W - 70;
    var lo = Math.min(-30, Math.floor((Math.min.apply(null, x.f) - 3) / 15) * 15), hi = Math.max(15, Math.ceil((Math.max.apply(null, x.f) + 3) / 15) * 15);
    var X = function (v) { return L + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (R - L); };
    var labels = ["× Taxable valuation, after inflation", "× Average tax rate", "× Share left after state credits", "= Taxes after credits, after inflation"];
    var s = svg(W, 10, "The three factors behind the change in taxes after credits"), y = 34, bh = 26;
    var stepT = phone && (hi - lo) / 15 > 4 ? 30 : 15;
    for (var t = lo; t <= hi; t += 15) {
      s.appendChild(el("line", { x1: X(t), x2: X(t), y1: 24, y2: 4 * (bh + (phone ? 40 : 18)) + 40, stroke: t === 0 ? INK : RULE }));
      if (t % stepT === 0 || t === 0) txt(s, X(t), 16, t === 0 ? "0%" : pct(t, 0), { fill: SUB, fs: 11.5, anchor: t === lo ? "start" : t === hi ? "end" : "middle" });
    }
    x.f.forEach(function (v, i) {
      if (i === 3) { s.appendChild(el("line", { x1: phone ? L : 0, x2: W, y1: y - 8, y2: y - 8, stroke: INK })); y += 8; }
      if (phone) { y += 14; txt(s, L, y - 6, labels[i], { fw: i === 3 ? 700 : 600, fs: 13, halo: true }); y += 4; }
      else txt(s, 0, y + bh / 2 + 4, labels[i], { fw: i === 3 ? 700 : 600, fs: 13.5 });
      var x0 = X(Math.min(0, v)), x1 = X(Math.max(0, v));
      s.appendChild(el("rect", { x: x0, y: y, width: Math.max(x1 - x0, 0.5), height: bh, fill: v < 0 ? RUST : SLATE }));
      txt(s, W - 4, y + bh / 2 + 5, pct(v), { fw: 700, fs: 13, anchor: "end" });
      y += bh + (phone ? 40 : 18);
    });
    txt(s, W - 4, y + 4, "Change since " + D.y0, { fill: SUB, fs: 11.5, anchor: "end" });
    s.setAttribute("viewBox", "0 0 " + W + " " + (y + 12));
    return s;
  }

  function placeMech(code) {
    var box = document.getElementById("place-mech"); if (!box) return;
    box.innerHTML = ""; box.hidden = !code; if (!code) return;
    var p = P[code], W = Math.round(box.parentNode.clientWidth) || 1040, h = document.createElement("div");
    if (D.chart === "formula" && p.fx) {
      var f = p.fx, line = function (l) { return l.map(function (t) { return t[0] + " " + money(t[1]); }).join(" + "); };
      h.innerHTML = "<h3 class='mh'>" + esc(p.n) + "</h3><p class='dlead'>" + esc(p.s) + "'s formula need is <b>" + mil(f.need) + "</b>. Its resources cover " + mil(f.res) +
        " of it (" + Math.round(100 * f.res / f.need) + "%)" + (f.eq > 0 ? ", so the formula pays the " + mil(f.eq) + " gap as equalization aid" : ", so it receives no equalization aid") +
        ". Its total TEEOSA aid is <b>" + mil(f.aid) + "</b>.</p>";
      box.appendChild(h); box.appendChild(bridge(f, W));
      var t = document.createElement("div");
      var found = f.eq > 0 ? "Foundation aid is paid in full (" + money(f.found_in + f.found_out) + "), but the 60% counted as a resource (" + money(f.found_in) +
        ") lowers equalization aid by the same amount. On net it adds the other 40%, " + money(f.found_out) + "."
        : "Foundation aid adds its full " + money(f.found_in + f.found_out) + ": " + esc(p.s) + " receives no equalization aid, so counting 60% of it as a resource changes nothing.";
      var moves = f.eq > 0 ? "<b>What moves " + esc(p.s) + "'s aid.</b> While a system receives equalization aid, each $1 of formula need adds $1 of aid, and each $100 of school adjusted valuation removes $1, through local effort at $1.00 per $100. Its local effort is " + money(f.le) + ": 1% of its " + money(f.sav) + " school adjusted valuation."
        : "<b>What moves " + esc(p.s) + "'s aid.</b> Its resources exceed need by " + money(f.res - f.need) + "; need would have to rise by more than that before equalization aid starts.";
      t.innerHTML = "<p>" + found + "</p><div class='whybox'><p>" + moves + "</p></div><details><summary>" + esc(p.s) + "'s formula, line by line</summary>" +
        "<p><b>Formula need " + money(f.need) + "</b> = " + esc(line(f.need_parts)) + "</p><p><b>Formula resources " + money(f.res) + "</b> = " + esc(line(f.res_parts)) + "</p>" +
        "<p><b>Equalization aid " + money(f.eq) + "</b> = need " + money(f.need) + " " + MINUS + " resources " + money(f.res) + (f.eq > 0 ? "" : ", floored at zero") + "</p>" +
        "<p><b>Total TEEOSA aid " + money(f.aid) + "</b> = " + esc(line(f.aid_parts)) + "</p><p class='quiet'>Certified total: " + money(f.cert) + ". These lines are checked against the certification for every system at every build.</p></details>";
      box.appendChild(t);
    }
    if (D.chart === "ptax" && p.px) {
      var x = p.px, d0 = D.d0, d1 = D.d1;
      h.innerHTML = "<h3 class='mh'>" + esc(p.n) + "</h3><p class='dlead'>Taxable valuation " + (x.f[0] >= 0 ? "rose " : "fell ") + Math.abs(x.f[0]).toFixed(1) + "% after inflation, the average rate " +
        (x.f[1] >= 0 ? "rose " : "fell ") + Math.abs(x.f[1]).toFixed(1) + "%, and the share left after credits " + (x.f[2] >= 0 ? "rose " : "fell ") + Math.abs(x.f[2]).toFixed(1) +
        "%. Together: <b>" + pct(x.f[3]) + "</b> after inflation, " + pct(x.nom) + " in dollars.</p>";
      box.appendChild(h); box.appendChild(factorBars(x, W));
      var prog = function (o) { return Object.keys(o).map(function (k) { return k + " " + money(o[k]); }).join(" + ") || "none"; };
      var t2 = document.createElement("div");
      t2.innerHTML = "<div class='whybox'><p><b>What moved " + esc(p.s) + ".</b> Credits went from " + mil(x.c0) + " in " + D.y0 + " to " + mil(x.c1) + " in " + D.y1 +
        ". Taxes levied rose " + (100 * (x.t1 / x.t0 - 1)).toFixed(1) + "% in dollars while taxable valuation rose " + (100 * (x.v1 / x.v0 - 1)).toFixed(1) + "%, so the average rate " + (x.f[1] < 0 ? "fell" : "rose") +
        "." + (x.school ? " School districts levy " + Math.round(x.school) + "% of its property taxes." : "") + " Rates are set by each board that levies here; credits are set by the Legislature.</p></div>" +
        "<details><summary>" + esc(p.s) + "'s arithmetic, line by line</summary>" +
        [[D.y0, x.v0, x.t0, x.c0], [D.y1, x.v1, x.t1, x.c1]].map(function (r) {
          return "<p><b>" + r[0] + "</b>: taxable valuation " + money(r[1]) + " × average rate " + (100 * r[2] / r[1]).toFixed(3) + "% = taxes levied " + money(r[2]) +
            "; credits " + money(r[3]) + " leave " + (100 * (r[2] - r[3]) / r[2]).toFixed(1) + "%, so taxes after credits are <b>" + money(r[2] - r[3]) + "</b>.</p>";
        }).join("") +
        "<p>Credits, " + D.y0 + ": " + esc(prog(x.p0)) + (x.est0 ? " (estimates, split to counties from statewide totals)" : "") + ". Credits, " + D.y1 + ": " + esc(prog(x.p1)) + ".</p></details>";
      box.appendChild(t2);
    }
  }

  function apply(code) {
    var p = code && P[code];
    if (code && !p) code = "";
    var line = document.getElementById("sel-line"), peer = document.getElementById("peer-line"), prof = document.getElementById("sel-profile");
    document.querySelectorAll(".gtable tr, .glist .gi").forEach(function (tr) { tr.classList.toggle("on", !!p && tr.getAttribute("data-g") === p.g); });
    if (!p) { line.hidden = true; peer.hidden = true; prof.hidden = true; mark(""); placeMech(""); return; }
    line.innerHTML = "<b>" + esc(p.n) + "</b>: <b class='big'>" + esc(p.v) + "</b>, " + esc(p.r) + (p.why ? ", " + esc(p.why) : "") +
      ". Median of its " + p.pn + " peers (" + esc(p.pd) + "): " + esc(p.pm) + ".";
    line.hidden = false;
    peer.innerHTML = "<b>" + esc(p.s) + "'s peers</b>: the " + p.pn + " " + D.nouns + " that share its " + (D.level === "system" ? "size band and equalization status" : "tier") +
      ". Their median is <b>" + esc(p.pm) + "</b>; " + esc(p.s) + " is " + p.pr + (p.pr % 10 === 1 && p.pr !== 11 ? "st" : p.pr % 10 === 2 && p.pr !== 12 ? "nd" : p.pr % 10 === 3 && p.pr !== 13 ? "rd" : "th") + " highest of " + p.pn + ".";
    peer.hidden = false;
    prof.href = "../../" + D.level + "/" + code + ".html"; prof.hidden = false;
    mark(code); placeMech(code);
  }

  var pick = document.getElementById("pick"), sel = new URLSearchParams(location.search).get("sel") || "";
  if (sel && P[sel]) pick.value = sel;
  pick.addEventListener("change", function () {
    var u = new URL(location.href);
    if (pick.value) u.searchParams.set("sel", pick.value); else u.searchParams.delete("sel");
    history.replaceState(null, "", u); apply(pick.value);
  });
  // Step 5 for any measure: drawn here from the shared values file with this page's y axis, by the same rules as the
  // scatters drawn at build (dive.scatter): p99 clip as triangles, fitted line, the five places furthest from it labeled.
  var V = window.DIVE_VALUES, MINUS = "\u2212";
  function niceStep(span, n) {
    var raw = span / Math.max(n, 1), mag = raw > 0 ? Math.pow(10, Math.floor(Math.log10(raw))) : 1;
    var ms = [1, 2, 2.5, 5, 10]; for (var i = 0; i < ms.length; i++) if (raw <= ms[i] * mag) return ms[i] * mag;
    return 10 * mag;
  }
  function comma(v, d) { return Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function signed(v, d, suf) { var s = comma(v, d) + (suf || ""); return +v.toFixed(d) === 0 ? s : (v > 0 ? "+" : MINUS) + s; }
  function tickLabel(v, m) {
    var f = m.format, neg = v < 0 ? MINUS : "";
    if (f === "dollars") return neg + (Math.abs(v) >= 1e6 ? "$" + comma(v / 1e6, 1) + "M" : "$" + comma(v, 0));
    if (f === "cents") return neg + "$" + Math.abs(v).toFixed(2);
    if (f === "pct" || f === "rate" || f === "pct_change") return m.scale === "diverging" || f === "pct_change" ? signed(v, 0, "%") : comma(v, 0) + "%";
    if (m.scale === "diverging") return signed(v, 0);
    return String(+v.toPrecision(4)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  function tw(s, fs) { return String(s).length * fs * 0.55; }
  function Labels(W, H) { this.b = []; this.W = W; this.H = H; }
  Labels.prototype.block = function (box) { this.b.push(box); };
  Labels.prototype.place = function (x, y, text, fs, tries) {
    var w = tw(text, fs), h = fs * 1.15;
    for (var i = 0; i < tries.length; i++) {
      var t = tries[i], x0 = x + t[0] - (t[2] === "end" ? w : 0), y0 = y + t[1] - h * 0.85, bx = [x0, y0, x0 + w, y0 + h];
      if (bx[0] < 0 || bx[2] > this.W || bx[1] < 0 || bx[3] > this.H) continue;
      if (this.b.some(function (b) { return !(bx[2] < b[0] || bx[0] > b[2] || bx[3] < b[1] || bx[1] > b[3]); })) continue;
      this.b.push(bx); return [x + t[0], y + t[1], t[2]];
    }
    return null;
  }
  function drawScatter(key, W) {
    var A = D.ax, phone = W < 600, xm = V.meta[key], ym = { short: A.short };
    var idx = {}; V.codes.forEach(function (c, i) { idx[c] = i; });
    var yv = V.v[D.key], xv = V.v[key], sc = [];
    Object.keys(P).forEach(function (c) { var i = idx[c]; if (i != null && xv[i] != null && yv[i] != null) sc.push([c, xv[i], yv[i]]); });
    if (sc.length < 3) return '<p class="note">Fewer than three ' + D.nouns + " have both measures, so there is nothing to plot.</p>";
    var xs = sc.map(function (t) { return t[1]; }), xlo = Math.min.apply(null, xs), xhi = Math.max.apply(null, xs), pad = (xhi - xlo) * 0.04 || 1;
    xlo -= pad; xhi += pad;
    var ylo = A.lo, yhi = A.hi, L = phone ? 52 : 72, R = W - 10, T = 30, Bt = phone ? 316 : 400;
    var xl = [], cur = "";
    (xm.short + ", " + xm.period).split(" ").forEach(function (w_) {
      if (cur && tw(cur + " " + w_, 11.5) > R - 4) { xl.push(cur); cur = w_; } else cur = (cur + " " + w_).trim();
    });
    if (cur) xl.push(cur);
    var H = Bt + 46 + 15 * (xl.length - 1);
    var SX = function (v) { return L + (v - xlo) / (xhi - xlo) * (R - L); };
    var SY = function (v) { return T + (yhi - Math.max(ylo, Math.min(v, yhi))) / (yhi - ylo) * (Bt - T); };
    var n = sc.length, mx = xs.reduce(function (a, b) { return a + b; }, 0) / n, my = sc.reduce(function (a, t) { return a + t[2]; }, 0) / n;
    var sxx = sc.reduce(function (a, t) { return a + (t[1] - mx) * (t[1] - mx); }, 0) || 1;
    var b = sc.reduce(function (a, t) { return a + (t[1] - mx) * (t[2] - my); }, 0) / sxx, a0 = my - b * mx;
    var o = ['<svg class="dchart scatter" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(A.short + " against " + xm.short + ", every " + D.noun) + '">'];
    var lab = new Labels(W, Bt);
    o.push('<text x="0" y="13" font-size="12" fill="' + SUB + '">' + esc(A.short) + "</text>"); lab.block([0, 0, tw(A.short, 12) + 8, 18]);
    (phone ? A.t4 : A.t6).forEach(function (t) {
      o.push('<line x1="' + L + '" x2="' + R + '" y1="' + SY(t[0]).toFixed(1) + '" y2="' + SY(t[0]).toFixed(1) + '" stroke="' + (t[0] === 0 && A.lo < 0 ? INK : RULE) + '"/>' +
        '<text x="' + (L - 6) + '" y="' + (SY(t[0]) + 4).toFixed(1) + '" font-size="11.5" fill="' + SUB + '" text-anchor="end">' + esc(t[1]) + "</text>");
    });
    if (A.floor) o.push('<path d="M' + (L - 2) + " " + (Bt + 6) + 'l4 -4l-8 -4l8 -4l-4 -4" fill="none" stroke="' + INK + '" stroke-width="1.2"/>');
    var step = niceStep(xhi - xlo, phone ? 4 : 7), t = Math.ceil(xlo / step) * step;
    for (; t <= xhi; t += step) {
      var tt = Math.round(t * 1e10) / 1e10;
      o.push('<line x1="' + SX(tt).toFixed(1) + '" x2="' + SX(tt).toFixed(1) + '" y1="' + T + '" y2="' + Bt + '" stroke="' + RULE + '"/>' +
        '<text x="' + SX(tt).toFixed(1) + '" y="' + (Bt + 17) + '" font-size="11.5" fill="' + SUB + '" text-anchor="middle">' + esc(tickLabel(tt, xm)) + "</text>");
    }
    xl.forEach(function (t_, i) { o.push('<text x="' + R + '" y="' + (Bt + 36 + 15 * i) + '" font-size="11.5" fill="' + SUB + '" text-anchor="end">' + esc(t_) + "</text>"); });
    var xa = xlo, xb = xhi;
    if (A.floor && b) { var bound = (ylo - a0) / b; if (b > 0) xa = Math.max(xlo, bound); else xb = Math.min(xhi, bound); }
    o.push('<line x1="' + SX(xa).toFixed(1) + '" y1="' + SY(a0 + b * xa).toFixed(1) + '" x2="' + SX(xb).toFixed(1) + '" y2="' + SY(a0 + b * xb).toFixed(1) + '" stroke="' + INK + '" stroke-dasharray="5 4" stroke-width="1.25"/>');
    sc.forEach(function (p) {
      var x = SX(p[1]), y = SY(p[2]);
      if (A.clip != null && p[2] > A.clip) { o.push('<path class="dd" data-c="' + p[0] + '" d="M' + (x - 5).toFixed(1) + " " + (y + 7).toFixed(1) + 'l5 -8l5 8z"/>'); lab.block([x - 6, y - 2, x + 6, y + 8]); }
      else o.push('<circle class="dd" data-c="' + p[0] + '" cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (phone ? 2.8 : 3.4) + '"/>');
    });
    var tries = [[9, -8, "start"], [-9, -8, "end"], [9, 15, "start"], [-9, 15, "end"], [-9, 28, "end"], [9, 28, "start"], [-9, 41, "end"], [9, 41, "start"]];
    sc.slice().sort(function (p, q) { return Math.abs(q[2] - (a0 + b * q[1])) - Math.abs(p[2] - (a0 + b * p[1])); }).slice(0, 5).forEach(function (p) {
      var nm = P[p[0]].s + (A.clip != null && p[2] > A.clip ? " (" + P[p[0]].v + ")" : ""), x = SX(p[1]), y = SY(p[2]);
      var at = lab.place(x, y, nm, 12, tries);
      if (!at) return;
      if (Math.abs(at[1] - y) > 16) o.push('<line data-l="' + p[0] + '" x1="' + x.toFixed(1) + '" y1="' + (y + 4).toFixed(1) + '" x2="' + at[0].toFixed(1) + '" y2="' + (at[1] - 10).toFixed(1) + '" stroke="' + SUB + '" stroke-width="0.8"/>');
      o.push('<text data-l="' + p[0] + '" stroke="' + CARD + '" stroke-width="4" paint-order="stroke" x="' + at[0].toFixed(1) + '" y="' + at[1].toFixed(1) + '" font-size="12" fill="' + INK + '" text-anchor="' + at[2] + '">' + esc(nm) + "</text>");
    });
    return o.join("") + "</svg>";
  }
  var vs = document.getElementById("vs"), jsKey = null;
  function showScatter(v) {
    if (v.indexOf("k:") === 0) {
      jsKey = v.slice(2);
      var r = (D.rels || {})[jsKey] || {}, box = document.getElementById("sc-js");
      document.getElementById("sc-js-lead").textContent = r.few
        ? r.name + ": too few " + D.nouns + " to test, so read any pattern as untested."
        : r.name + ": " + r.word + " (rank correlation " + r.rho + ")" + (r.holds ? ", stronger than chance." : ", which could be chance.");
      box.innerHTML = '<div class="w-desk">' + drawScatter(jsKey, 1040) + '</div><div class="w-phone">' + drawScatter(jsKey, 350) + "</div>";
      v = "js";
    }
    document.querySelectorAll(".sc").forEach(function (d) { d.hidden = d.getAttribute("data-i") !== v; });
    mark(pick.value);
  }
  if (vs) vs.addEventListener("change", function () { if (vs.value) showScatter(vs.value); });
  // Step 4 rows plot their measure in step 5.
  document.querySelectorAll(".plotlink").forEach(function (a) {
    a.addEventListener("click", function () {
      var k = a.getAttribute("data-x"), opt = vs && (vs.querySelector('option[data-k="' + k + '"]') || vs.querySelector('option[value="k:' + k + '"]'));
      if (opt) { vs.value = opt.value; showScatter(opt.value); }
    });
  });
  // ?vs=<measure> opens step 5 on that measure (links from the map pages)
  var wantVs = new URLSearchParams(location.search).get("vs");
  if (wantVs && vs) {
    var ov = vs.querySelector('option[data-k="' + wantVs + '"]') || vs.querySelector('option[value="k:' + wantVs + '"]');
    if (ov) { vs.value = ov.value; showScatter(ov.value); }
  }
  apply(sel);
})();
