/* ============================================================================
 * OFFLINE SVG CHART SHIM  —  drop-in replacement for the projection GUI's
 * Chart.js-based mkChart(id, type, labels, datasets, opts).
 *
 * Supports exactly the call surface used by par_projection_gui.html:
 *   - type 'line'     : multi-series, optional area fill, dashed lines,
 *                       dual y-axis via dataset.yAxisID === 'y2'
 *   - type 'bar'      : grouped OR stacked (opts.scales.x.stacked &&
 *                       opts.scales.y.stacked), supports negative values
 *   - type 'doughnut' : single dataset, per-slice backgroundColor[], cutout
 *
 * Zero dependencies, zero network. Renders inline <svg>. Replaces the target
 * <canvas id> with a <div id> on first use so the rest of the page is unchanged.
 * ==========================================================================*/
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var PAL = ['#5b8df7', '#a06cf5', '#f59340', '#27c9a0', '#e85c7a',
             '#c499f7', '#e8c15c', '#6cc5f5', '#f5736c', '#7af5c0'];
  var AXIS = '#4d5370', GRID = '#1c2038', TXT = '#8f96b0';

  function el(name, attrs) {
    var e = document.createElementNS(NS, name);
    if (attrs) { for (var k in attrs) e.setAttribute(k, attrs[k]); }
    return e;
  }
  function num(v) { var f = parseFloat(v); return isFinite(f) ? f : 0; }
  function col(c, fallback) {
    if (c === undefined || c === null || c === 'transparent') return fallback || 'none';
    return c;
  }
  function fmt(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (a >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    if (a !== 0 && a < 1) return v.toFixed(2);
    return '' + Math.round(v);
  }

  // Replace a <canvas id> with a <div id> (idempotent); clear and return it.
  function host(id) {
    var node = document.getElementById(id);
    if (!node) return null;
    if (node.tagName && node.tagName.toLowerCase() === 'canvas') {
      var div = document.createElement('div');
      div.id = id;
      div.className = node.className || '';
      div.style.width = '100%';
      node.parentNode.replaceChild(div, node);
      node = div;
    }
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function svgRoot(W, H) {
    var s = el('svg', {
      viewBox: '0 0 ' + W + ' ' + H,
      width: '100%', height: 'auto',
      preserveAspectRatio: 'xMidYMid meet',
      'font-family': 'system-ui, sans-serif'
    });
    s.style.maxHeight = (H + 20) + 'px';
    return s;
  }

  function text(x, y, str, opts) {
    var a = { x: x, y: y, fill: (opts && opts.fill) || TXT,
              'font-size': (opts && opts.size) || 10,
              'text-anchor': (opts && opts.anchor) || 'start' };
    var t = el('text', a); t.textContent = str; return t;
  }

  // Shared domain helper: returns {min,max} padded, including zero baseline.
  function domain(values, includeZero) {
    var mn = Infinity, mx = -Infinity, i;
    for (i = 0; i < values.length; i++) {
      var v = values[i];
      if (v < mn) mn = v;
      if (v > mx) mx = v;
    }
    if (!isFinite(mn)) { mn = 0; mx = 1; }
    if (includeZero) { if (mn > 0) mn = 0; if (mx < 0) mx = 0; }
    if (mn === mx) { mn -= 1; mx += 1; }
    var pad = (mx - mn) * 0.08;
    return { min: mn - pad, max: mx + pad };
  }

  function legendRow(svg, datasets, W, H, colorFor) {
    var lx = 8, ly = H - 6, i;
    for (i = 0; i < datasets.length; i++) {
      var lab = datasets[i].label || ('S' + i);
      if (lx + lab.length * 6 + 16 > W - 6) { lx = 8; ly += 13; } // wrap
      svg.appendChild(el('rect', { x: lx, y: ly - 8, width: 9, height: 9,
        rx: 2, fill: colorFor(i) }));
      svg.appendChild(text(lx + 13, ly, lab, { size: 9 }));
      lx += 16 + lab.length * 6.0;
    }
    return ly; // bottom-most legend baseline
  }

  // ---- LINE (with optional dual axis + area fill) --------------------------
  function drawLine(node, labels, datasets, opts) {
    var W = 600, H = 300, padL = 44, padR = 44, padT = 14, padB = 54;
    var svg = svgRoot(W, H);
    var n = labels.length || 1;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    var left = [], right = [];
    datasets.forEach(function (d) { (d.yAxisID === 'y2' ? right : left).push(d); });

    function vals(list) { var a = []; list.forEach(function (d) {
      (d.data || []).forEach(function (v) { a.push(num(v)); }); }); return a; }
    var dL = domain(vals(left), true);
    var dR = right.length ? domain(vals(right), true) : null;

    var xAt = function (i) { return padL + (n === 1 ? plotW / 2 : (i * plotW / (n - 1))); };
    var yAtL = function (v) { return padT + plotH - (num(v) - dL.min) / (dL.max - dL.min) * plotH; };
    var yAtR = function (v) { return padT + plotH - (num(v) - dR.min) / (dR.max - dR.min) * plotH; };

    // gridlines + left axis ticks
    var t;
    for (t = 0; t <= 4; t++) {
      var gy = padT + t * plotH / 4;
      svg.appendChild(el('line', { x1: padL, y1: gy, x2: W - padR, y2: gy, stroke: GRID, 'stroke-width': 1 }));
      var lv = dL.max - t * (dL.max - dL.min) / 4;
      svg.appendChild(text(padL - 5, gy + 3, fmt(lv), { anchor: 'end', fill: AXIS, size: 9 }));
      if (dR) {
        var rv = dR.max - t * (dR.max - dR.min) / 4;
        svg.appendChild(text(W - padR + 5, gy + 3, fmt(rv), { fill: AXIS, size: 9 }));
      }
    }
    // x labels (thinned)
    var step = Math.ceil(n / 12);
    for (t = 0; t < n; t += step) {
      svg.appendChild(text(xAt(t), H - padB + 14, String(labels[t]),
        { anchor: 'middle', fill: AXIS, size: 9 }));
    }

    var colorFor = function (i) { return col(datasets[i].borderColor, PAL[i % PAL.length]); };

    datasets.forEach(function (d, di) {
      var yf = d.yAxisID === 'y2' ? yAtR : yAtL;
      var stroke = col(d.borderColor, PAL[di % PAL.length]);
      var pts = (d.data || []).map(function (v, i) { return [xAt(i), yf(v)]; });
      if (!pts.length) return;
      var path = pts.map(function (p, i) { return (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
      // area fill
      if (d.fill && col(d.backgroundColor, null) !== 'none' && d.backgroundColor) {
        var base = (d.yAxisID === 'y2' ? yAtR : yAtL)(Math.max(dL.min, 0));
        var area = path + ' L' + pts[pts.length - 1][0].toFixed(1) + ',' + base.toFixed(1) +
                   ' L' + pts[0][0].toFixed(1) + ',' + base.toFixed(1) + ' Z';
        svg.appendChild(el('path', { d: area, fill: d.backgroundColor, stroke: 'none', opacity: 0.5 }));
      }
      var attrs = { d: path, fill: 'none', stroke: stroke, 'stroke-width': 1.8,
                    'stroke-linejoin': 'round', 'stroke-linecap': 'round' };
      if (Array.isArray(d.borderDash) && d.borderDash.length) attrs['stroke-dasharray'] = d.borderDash.join(',');
      svg.appendChild(el('path', attrs));
      // points
      var pr = d.pointRadius === undefined ? 0 : num(d.pointRadius);
      if (pr > 0) pts.forEach(function (p) {
        svg.appendChild(el('circle', { cx: p[0], cy: p[1], r: Math.min(pr, 3), fill: stroke }));
      });
    });

    legendRow(svg, datasets, W, H, colorFor);
    node.appendChild(svg);
  }

  // ---- BAR (grouped or stacked, supports negatives) ------------------------
  function drawBar(node, labels, datasets, opts) {
    var W = 600, H = 300, padL = 46, padR = 14, padT = 14, padB = 54;
    var svg = svgRoot(W, H);
    var n = labels.length || 1;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var stacked = !!(opts && opts.scales && opts.scales.x && opts.scales.x.stacked);

    // domain
    var allVals = [];
    if (stacked) {
      for (var i = 0; i < n; i++) {
        var pos = 0, neg = 0;
        datasets.forEach(function (d) { var v = num(d.data[i]); if (v >= 0) pos += v; else neg += v; });
        allVals.push(pos); allVals.push(neg);
      }
    } else {
      datasets.forEach(function (d) { (d.data || []).forEach(function (v) { allVals.push(num(v)); }); });
    }
    var dom = domain(allVals, true);
    var yAt = function (v) { return padT + plotH - (v - dom.min) / (dom.max - dom.min) * plotH; };
    var zeroY = yAt(0);

    // gridlines + y ticks
    var t;
    for (t = 0; t <= 4; t++) {
      var gy = padT + t * plotH / 4;
      svg.appendChild(el('line', { x1: padL, y1: gy, x2: W - padR, y2: gy, stroke: GRID, 'stroke-width': 1 }));
      var lv = dom.max - t * (dom.max - dom.min) / 4;
      svg.appendChild(text(padL - 5, gy + 3, fmt(lv), { anchor: 'end', fill: AXIS, size: 9 }));
    }
    svg.appendChild(el('line', { x1: padL, y1: zeroY, x2: W - padR, y2: zeroY, stroke: AXIS, 'stroke-width': 1 }));

    var slot = plotW / n;
    var colorFor = function (i) { return col(datasets[i].backgroundColor, PAL[i % PAL.length]); };

    for (var ci = 0; ci < n; ci++) {
      var x0 = padL + ci * slot;
      if (stacked) {
        var accP = 0, accN = 0;
        datasets.forEach(function (d, di) {
          var v = num(d.data[ci]); if (v === 0) return;
          var bw = slot * 0.7, bx = x0 + slot * 0.15;
          var y1, y2;
          if (v >= 0) { y2 = yAt(accP); accP += v; y1 = yAt(accP); }
          else { y1 = yAt(accN); accN += v; y2 = yAt(accN); }
          svg.appendChild(el('rect', { x: bx, y: Math.min(y1, y2), width: bw,
            height: Math.abs(y2 - y1), fill: colorFor(di) }));
        });
      } else {
        var m = datasets.length, bw2 = (slot * 0.7) / m, gx = x0 + slot * 0.15;
        datasets.forEach(function (d, di) {
          var v = num(d.data[ci]);
          var y = yAt(Math.max(v, 0)), h = Math.abs(yAt(v) - zeroY);
          svg.appendChild(el('rect', { x: gx + di * bw2, y: y, width: Math.max(bw2 - 1, 1),
            height: h, fill: colorFor(di) }));
        });
      }
    }

    var step = Math.ceil(n / 12);
    for (t = 0; t < n; t += step) {
      svg.appendChild(text(padL + t * slot + slot / 2, H - padB + 14, String(labels[t]),
        { anchor: 'middle', fill: AXIS, size: 9 }));
    }
    legendRow(svg, datasets, W, H, colorFor);
    node.appendChild(svg);
  }

  // ---- DOUGHNUT ------------------------------------------------------------
  function drawDoughnut(node, labels, datasets, opts) {
    var W = 600, H = 300, svg = svgRoot(W, H);
    var d0 = datasets[0] || { data: [] };
    var data = (d0.data || []).map(num);
    var colors = Array.isArray(d0.backgroundColor) ? d0.backgroundColor : null;
    var total = data.reduce(function (a, b) { return a + Math.abs(b); }, 0) || 1;
    var cx = 150, cy = H / 2, R = 110;
    var cutout = 0.55;
    if (opts && opts.extra && opts.extra.cutout) {
      var cs = ('' + opts.extra.cutout).replace('%', ''); cutout = num(cs) / 100 || 0.55;
    }
    var r0 = R * cutout;
    var ang = -Math.PI / 2;
    data.forEach(function (v, i) {
      var frac = Math.abs(v) / total, a1 = ang, a2 = ang + frac * 2 * Math.PI; ang = a2;
      var large = (a2 - a1) > Math.PI ? 1 : 0;
      var x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
      var x2 = cx + R * Math.cos(a2), y2 = cy + R * Math.sin(a2);
      var xi2 = cx + r0 * Math.cos(a2), yi2 = cy + r0 * Math.sin(a2);
      var xi1 = cx + r0 * Math.cos(a1), yi1 = cy + r0 * Math.sin(a1);
      var dpath = 'M' + x1 + ',' + y1 +
        ' A' + R + ',' + R + ' 0 ' + large + ' 1 ' + x2 + ',' + y2 +
        ' L' + xi2 + ',' + yi2 +
        ' A' + r0 + ',' + r0 + ' 0 ' + large + ' 0 ' + xi1 + ',' + yi1 + ' Z';
      var fill = colors ? colors[i % colors.length] : PAL[i % PAL.length];
      svg.appendChild(el('path', { d: dpath, fill: fill, stroke: '#11142a', 'stroke-width': 1.5 }));
    });
    // legend (right side)
    var ly = 40;
    (labels || []).forEach(function (lab, i) {
      var fill = colors ? colors[i % colors.length] : PAL[i % PAL.length];
      svg.appendChild(el('rect', { x: 300, y: ly - 9, width: 11, height: 11, rx: 2, fill: fill }));
      var pct = ((Math.abs(data[i]) / total) * 100).toFixed(1) + '%';
      svg.appendChild(text(318, ly, (lab || ('S' + i)) + '  ' + pct, { size: 11 }));
      ly += 22;
    });
    node.appendChild(svg);
  }

  function mkChart(id, type, labels, datasets, opts) {
    try {
      var node = host(id);
      if (!node) return;
      datasets = datasets || [];
      opts = opts || {};
      if (type === 'doughnut' || type === 'pie') drawDoughnut(node, labels, datasets, opts);
      else if (type === 'bar') drawBar(node, labels, datasets, opts);
      else drawLine(node, labels, datasets, opts);
    } catch (e) {
      try { console.error('svg-chart-shim mkChart failed for ' + id, e); } catch (_) {}
    }
  }

  // Export: override the page's Chart.js-based factory.
  window.mkChart = mkChart;
  if (typeof globalThis !== 'undefined') globalThis.mkChart = mkChart;
})();
