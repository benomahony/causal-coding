(function () {
  "use strict";

  var DASH = { mixed: [8, 7], hypothesis: [1, 7] };

  function palette() {
    var cs = getComputedStyle(document.documentElement);
    var get = function (name, fallback) {
      var v = cs.getPropertyValue(name).trim();
      return v || fallback;
    };
    return {
      ink: get("--ink", "#000000"),
      paper: get("--surface", "#ffffff"),
      accent: get("--accent", "#003d4f"),
      accent2: get("--accent2", "#f2617a"),
      accent2Dark: get("--tw-flamingo-dark", "#d8455d"),
      supported: get("--supported", "#6b9e78"),
      supportedDark: get("--tw-jade-dark", "#4e7e5c"),
      mixed: get("--mixed", "#cc850a"),
      mixedDark: get("--tw-turmeric-dark", "#a66a05"),
      mechanism: get("--mechanism", "#47a1ad"),
      mechanismDark: get("--tw-sapphire-dark", "#2e7e89"),
      hypothesis: get("--hypothesis", "#8a8a8a"),
      amethyst: get("--tw-amethyst", "#634f7d"),
    };
  }

  function stageColor(pal, slug) {
    return (
      {
        inputs: pal.accent,
        system: pal.mixed,
        agent: pal.mechanism,
        flow: pal.amethyst,
        delivery: pal.ink,
        product: pal.supported,
        commercial: pal.accent2,
      }[slug] || pal.ink
    );
  }

  function edgeColor(pal, statusClasses, focused) {
    if (statusClasses.contains("literature_supported")) return focused ? pal.supportedDark : pal.supported;
    if (statusClasses.contains("mixed")) return focused ? pal.mixedDark : pal.mixed;
    if (statusClasses.contains("mechanistic")) return focused ? pal.mechanismDark : pal.mechanism;
    return pal.hypothesis;
  }

  function seed(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
    return (Math.abs(h) % 2147483646) + 1;
  }

  var lastAnchor = null; // {x, y} in viewport coordinates, from the click that opened the inspector

  document.addEventListener(
    "click",
    function (evt) {
      if (evt.target.closest(".node, .edge-hit")) {
        lastAnchor = { x: evt.clientX, y: evt.clientY };
      } else if (evt.target.closest(".inspector-close, .segmented button")) {
        lastAnchor = null;
      }
    },
    true
  );

  function positionInspector() {
    var inspector = document.getElementById("inspector");
    var overlay = document.getElementById("leader-overlay");
    var leader = document.getElementById("inspector-leader");
    if (!inspector) return;

    var isHint = !!inspector.querySelector(":scope > .hint");
    if (isHint || !lastAnchor) {
      inspector.classList.remove("anchored");
      inspector.style.left = "";
      inspector.style.top = "";
      if (overlay) overlay.classList.remove("visible");
      return;
    }

    var margin = 16;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var cardW = inspector.offsetWidth || 360;
    var cardH = inspector.offsetHeight || 280;

    var placeRight = lastAnchor.x + margin + cardW < vw - margin;
    var left = placeRight
      ? Math.min(lastAnchor.x + margin, vw - cardW - margin)
      : Math.max(lastAnchor.x - margin - cardW, margin);
    var top = Math.min(Math.max(lastAnchor.y - cardH / 2, margin), Math.max(vh - cardH - margin, margin));

    inspector.classList.add("anchored");
    inspector.style.left = left + "px";
    inspector.style.top = top + "px";

    if (overlay && leader) {
      var cardEdgeX = placeRight ? left : left + cardW;
      var cardEdgeY = Math.min(Math.max(lastAnchor.y, top + 18), top + cardH - 18);
      var midX = (lastAnchor.x + cardEdgeX) / 2;
      var d =
        "M " +
        lastAnchor.x.toFixed(1) +
        " " +
        lastAnchor.y.toFixed(1) +
        " Q " +
        midX.toFixed(1) +
        " " +
        lastAnchor.y.toFixed(1) +
        " " +
        cardEdgeX.toFixed(1) +
        " " +
        cardEdgeY.toFixed(1);
      leader.setAttribute("d", d);
      overlay.classList.add("visible");
    }
  }

  function sketchify() {
    if (typeof rough === "undefined") return;
    var svg = document.querySelector("#graph-panel svg.causal-svg");
    if (!svg) return;

    var pal = palette();
    var rc = rough.svg(svg);

    svg.querySelectorAll(".edge").forEach(function (g) {
      var old = g.querySelector(".sketch-edge");
      if (old) old.remove();
      var line = g.querySelector(".edge-line");
      if (!line) return;
      line.style.opacity = "";
      var id = g.getAttribute("data-id") || line.getAttribute("d");
      var isFocusedEdge = g.classList.contains("focused");
      var options = {
        seed: seed("edge-" + id),
        roughness: 1.5,
        bowing: 1.3,
        stroke: edgeColor(pal, line.classList, isFocusedEdge),
        strokeWidth: isFocusedEdge ? 3.4 : 2,
        fill: "none",
      };
      var dashKey = line.classList.contains("mixed")
        ? "mixed"
        : line.classList.contains("hypothesis")
          ? "hypothesis"
          : null;
      if (dashKey) options.strokeLineDash = DASH[dashKey];
      var drawn = rc.path(line.getAttribute("d"), options);
      drawn.setAttribute("class", "sketch-edge");
      drawn.setAttribute("marker-end", "url(#arrow)");
      drawn.style.pointerEvents = "none";
      g.insertBefore(drawn, line);
    });

    svg.querySelectorAll(".node").forEach(function (g) {
      var old = g.querySelector(".sketch-node");
      if (old) old.remove();
      var rect = g.querySelector("rect");
      if (!rect) return;
      var id = g.getAttribute("data-id") || "";
      var stageSlug = g.getAttribute("data-stage") || "";
      var isTarget = g.classList.contains("target");
      var isFocused = g.classList.contains("focused");
      var stroke = isFocused ? pal.accent2Dark : isTarget ? pal.accent : stageColor(pal, stageSlug);
      var drawn = rc.rectangle(
        0,
        0,
        parseFloat(rect.getAttribute("width")),
        parseFloat(rect.getAttribute("height")),
        {
          seed: seed("node-" + id),
          roughness: 1.7,
          bowing: 1.6,
          stroke: stroke,
          strokeWidth: isFocused ? 3 : 1.8,
          fill: isTarget ? pal.accent : pal.paper,
          fillStyle: isTarget ? "solid" : "hachure",
          hachureGap: 5,
          fillWeight: 1,
        }
      );
      drawn.setAttribute("class", "sketch-node");
      drawn.style.pointerEvents = "none";
      g.insertBefore(drawn, rect);
    });

    document.body.classList.add("sketch-ready");
  }

  // ---- Pan, zoom and node dragging -----------------------------------------
  // The transform persists across htmx swaps (it lives here, not on the DOM),
  // so clicking a node to trace its pathway doesn't reset your view.
  var view = { scale: 1, tx: 0, ty: 0 };
  var hasView = false;
  var nodePositions = {}; // id -> {x, y} (top-left, content space)
  var MIN_SCALE = 0.25;
  var MAX_SCALE = 3;

  function currentSvg() {
    return document.querySelector("#graph-panel svg.causal-svg");
  }

  function viewportGroup(svg) {
    return svg && svg.querySelector("#viewport");
  }

  function computeFit(svg) {
    var content = viewportGroup(svg);
    if (!content) return { scale: 1, tx: 0, ty: 0 };
    var bbox = content.getBBox();
    var rect = svg.getBoundingClientRect();
    if (!bbox.width || !bbox.height || !rect.width || !rect.height) return { scale: 1, tx: 0, ty: 0 };
    var pad = 48;
    var scale = Math.min((rect.width - pad * 2) / bbox.width, (rect.height - pad * 2) / bbox.height);
    scale = Math.min(Math.max(scale, MIN_SCALE), 1.3);
    var tx = rect.width / 2 - (bbox.x + bbox.width / 2) * scale;
    var ty = rect.height / 2 - (bbox.y + bbox.height / 2) * scale;
    return { scale: scale, tx: tx, ty: ty };
  }

  function applyTransform(svg) {
    var content = viewportGroup(svg);
    if (!content) return;
    content.setAttribute("transform", "translate(" + view.tx + "," + view.ty + ") scale(" + view.scale + ")");
  }

  function zoomBy(svg, factor, anchorX, anchorY) {
    var rect = svg.getBoundingClientRect();
    var mx = anchorX === undefined ? rect.width / 2 : anchorX - rect.left;
    var my = anchorY === undefined ? rect.height / 2 : anchorY - rect.top;
    var newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale * factor));
    var cx = (mx - view.tx) / view.scale;
    var cy = (my - view.ty) / view.scale;
    view.scale = newScale;
    view.tx = mx - cx * newScale;
    view.ty = my - cy * newScale;
    applyTransform(svg);
  }

  function readNodePositions(svg) {
    nodePositions = {};
    svg.querySelectorAll(".node").forEach(function (g) {
      var m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(g.getAttribute("transform") || "");
      if (m) nodePositions[g.getAttribute("data-id")] = { x: parseFloat(m[1]), y: parseFloat(m[2]) };
    });
  }

  function clipToBox(cx, cy, halfW, halfH, tx, ty) {
    var dx = tx - cx;
    var dy = ty - cy;
    if (dx === 0 && dy === 0) return [cx, cy];
    var candidates = [];
    if (dx !== 0) candidates.push(halfW / Math.abs(dx));
    if (dy !== 0) candidates.push(halfH / Math.abs(dy));
    var t = Math.min.apply(null, candidates);
    return [cx + dx * t, cy + dy * t];
  }

  function edgeD(causeId, effectId) {
    var a = nodePositions[causeId];
    var b = nodePositions[effectId];
    if (!a || !b) return null;
    var acx = a.x + 90,
      acy = a.y + 25;
    var bcx = b.x + 90,
      bcy = b.y + 25;
    var p1 = clipToBox(acx, acy, 90, 25, bcx, bcy);
    var p2 = clipToBox(bcx, bcy, 90, 25, acx, acy);
    return "M " + p1[0].toFixed(1) + " " + p1[1].toFixed(1) + " L " + p2[0].toFixed(1) + " " + p2[1].toFixed(1);
  }

  function updateEdgesFor(svg, nodeId) {
    svg.querySelectorAll('.edge[data-cause="' + nodeId + '"], .edge[data-effect="' + nodeId + '"]').forEach(
      function (g) {
        var d = edgeD(g.getAttribute("data-cause"), g.getAttribute("data-effect"));
        if (!d) return;
        var line = g.querySelector(".edge-line");
        var hit = g.querySelector(".edge-hit");
        var sketch = g.querySelector(".sketch-edge");
        if (line) line.setAttribute("d", d);
        if (hit) hit.setAttribute("d", d);
        if (sketch) sketch.style.opacity = "0";
        if (line) line.style.opacity = "1";
      }
    );
  }

  var panState = null;
  var dragState = null;
  var suppressNextClick = false;

  // All interaction listeners are delegated onto document/window exactly once
  // and resolve the *current* svg dynamically - the svg itself is replaced on
  // every htmx swap, so anything bound directly to it would leak on each swap.
  function wireDelegatedInteractionsOnce() {
    if (window.__causalGraphWired) return;
    window.__causalGraphWired = true;

    document.addEventListener(
      "wheel",
      function (evt) {
        var svg = evt.target.closest && evt.target.closest("svg.causal-svg");
        if (!svg) return;
        evt.preventDefault();
        var factor = Math.exp(-evt.deltaY * 0.0015);
        zoomBy(svg, factor, evt.clientX, evt.clientY);
      },
      { passive: false }
    );

    document.addEventListener("dblclick", function (evt) {
      var svg = evt.target.closest && evt.target.closest("svg.causal-svg");
      if (!svg || evt.target.closest(".node, .edge-hit")) return;
      view = computeFit(svg);
      applyTransform(svg);
    });

    document.addEventListener("mousedown", function (evt) {
      var svg = evt.target.closest && evt.target.closest("svg.causal-svg");
      if (!svg) return;
      var nodeEl = evt.target.closest(".node");
      if (nodeEl) {
        var pos = nodePositions[nodeEl.getAttribute("data-id")] || { x: 0, y: 0 };
        dragState = {
          id: nodeEl.getAttribute("data-id"),
          x0: pos.x,
          y0: pos.y,
          startX: evt.clientX,
          startY: evt.clientY,
          moved: false,
        };
        evt.preventDefault();
        return;
      }
      panState = { startX: evt.clientX, startY: evt.clientY, tx0: view.tx, ty0: view.ty, moved: false };
      svg.classList.add("panning");
    });

    window.addEventListener("mousemove", function (evt) {
      var svg = currentSvg();
      if (!svg) return;
      if (dragState) {
        var el = svg.querySelector('.node[data-id="' + dragState.id + '"]');
        if (!el) {
          dragState = null;
          return;
        }
        var dx = (evt.clientX - dragState.startX) / view.scale;
        var dy = (evt.clientY - dragState.startY) / view.scale;
        if (Math.abs(evt.clientX - dragState.startX) > 3 || Math.abs(evt.clientY - dragState.startY) > 3) {
          dragState.moved = true;
        }
        var nx = dragState.x0 + dx;
        var ny = dragState.y0 + dy;
        el.setAttribute("transform", "translate(" + nx + "," + ny + ")");
        nodePositions[dragState.id] = { x: nx, y: ny };
        updateEdgesFor(svg, dragState.id);
      } else if (panState) {
        if (Math.abs(evt.clientX - panState.startX) > 3 || Math.abs(evt.clientY - panState.startY) > 3) {
          panState.moved = true;
        }
        view.tx = panState.tx0 + (evt.clientX - panState.startX);
        view.ty = panState.ty0 + (evt.clientY - panState.startY);
        applyTransform(svg);
      }
    });

    window.addEventListener("mouseup", function () {
      var svg = currentSvg();
      if (dragState) {
        if (dragState.moved) {
          suppressNextClick = true;
          sketchify();
        }
        dragState = null;
      }
      if (panState) {
        if (panState.moved) suppressNextClick = true;
        panState = null;
        if (svg) svg.classList.remove("panning");
      }
    });

    document.addEventListener(
      "click",
      function (evt) {
        if (suppressNextClick) {
          evt.stopImmediatePropagation();
          evt.preventDefault();
          suppressNextClick = false;
          return;
        }
        var zoomBtn = evt.target.closest("[data-zoom]");
        if (zoomBtn) {
          var svg = currentSvg();
          if (!svg) return;
          var action = zoomBtn.getAttribute("data-zoom");
          if (action === "in") zoomBy(svg, 1.25);
          else if (action === "out") zoomBy(svg, 0.8);
          else {
            view = computeFit(svg);
            applyTransform(svg);
          }
        }
      },
      true
    );
  }

  function setupGraph() {
    var svg = currentSvg();
    if (!svg) return;
    if (!hasView) {
      view = computeFit(svg);
      hasView = true;
    }
    applyTransform(svg);
    readNodePositions(svg);
    wireDelegatedInteractionsOnce();
  }

  function onSettle() {
    sketchify();
    setupGraph();
    positionInspector();
  }

  sketchify();
  setupGraph();
  positionInspector();
  document.body.addEventListener("htmx:afterSettle", onSettle);
  window.addEventListener("resize", function () {
    positionInspector();
  });
})();
