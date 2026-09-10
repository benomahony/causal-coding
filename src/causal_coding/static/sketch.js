(function () {
  "use strict";

  var transform = {scale: 1, x: 0, y: 0};
  var graphKey = null;
  var activeSvg = null;
  var pointer = null;
  var pointers = new Map();
  var pinch = null;
  var suppressClick = false;
  var fitScale = 1;
  var restoreGraphFocus = false;

  function panel() { return document.getElementById("graph-panel"); }
  function svg() { return document.querySelector(".causal-svg"); }
  function params(overrides) {
    var current = panel();
    return Object.assign({
      view: current.dataset.view, target: current.dataset.target,
      focus: current.dataset.focus || "", sources: current.dataset.sources
    }, overrides || {});
  }

  function sourceSelection() {
    return Array.from(document.querySelectorAll("#sources-form input:checked"))
      .map(function (input) { return input.value; }).join(",") || "none";
  }

  window.workbench = {params: params, sourceSelection: sourceSelection};

  function applyTransform() {
    var current = svg();
    if (!current) return;
    current.querySelector("#viewport").setAttribute("transform",
      "translate(" + transform.x + "," + transform.y + ") scale(" + transform.scale + ")");
    var output = document.getElementById("zoom-level");
    if (output) output.value = Math.round(transform.scale * 100) + "%";
  }

  function fit() {
    var current = svg();
    if (!current) return;
    var bounds = current.querySelector("#viewport").getBBox();
    var frame = current.getBoundingClientRect();
    if (!bounds.width || !frame.width || !frame.height) return;
    fitScale = Math.min((frame.width - 48) / bounds.width, (frame.height - 48) / bounds.height, 1.25);
    transform = {
      scale: fitScale,
      x: frame.width / 2 - (bounds.x + bounds.width / 2) * fitScale,
      y: frame.height / 2 - (bounds.y + bounds.height / 2) * fitScale
    };
    applyTransform();
  }

  function zoom(factor, clientX, clientY) {
    var current = svg();
    if (!current) return;
    var frame = current.getBoundingClientRect();
    var anchorX = clientX === undefined ? frame.width / 2 : clientX - frame.left;
    var anchorY = clientY === undefined ? frame.height / 2 : clientY - frame.top;
    var scale = Math.min(3, Math.max(Math.min(fitScale, 0.08), transform.scale * factor));
    var relative = scale / transform.scale;
    transform.x = anchorX - (anchorX - transform.x) * relative;
    transform.y = anchorY - (anchorY - transform.y) * relative;
    transform.scale = scale;
    applyTransform();
  }

  function setup() {
    var current = svg();
    if (!current) return;
    var state = params();
    var nextKey = state.view + "|" + (state.view === "neighborhood" ? state.focus : "") + "|" + state.target;
    if (current !== activeSvg) {
      current.removeAttribute("viewBox");
      activeSvg = current;
      pointers.clear();
      pointer = null;
      pinch = null;
    }
    if (nextKey !== graphKey) {
      graphKey = nextKey;
      fit();
    } else {
      applyTransform();
    }
    document.querySelectorAll("[data-view-choice]").forEach(function (button) {
      var selected = button.dataset.viewChoice === state.view;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    if (restoreGraphFocus) {
      var selectedNode = current.querySelector(".node.focused");
      if (selectedNode) selectedNode.focus({preventScroll: true});
      restoreGraphFocus = false;
    }
  }

  function closeSearch() {
    document.getElementById("search-results").hidden = true;
    document.getElementById("variable-search").setAttribute("aria-expanded", "false");
  }

  function explore(variable) {
    closeSearch();
    var query = new URLSearchParams(params({view: "neighborhood", focus: variable}));
    if (typeof htmx !== "undefined") {
      htmx.ajax("GET", "/focus/" + encodeURIComponent(variable) + "?" + query,
        {target: "#graph-panel", swap: "outerHTML"});
    } else {
      window.location.href = "/?" + query;
    }
  }

  function search() {
    var input = document.getElementById("variable-search");
    var term = input.value.trim().toLowerCase().replaceAll("_", " ");
    var count = 0;
    document.querySelectorAll("[data-search-id]").forEach(function (button) {
      var matches = button.dataset.label.toLowerCase().includes(term);
      button.hidden = !matches || count >= 10;
      if (matches) count++;
    });
    document.getElementById("no-results").hidden = count > 0;
    document.getElementById("search-results").hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function editable(target) { return target.closest("input,textarea,select,[contenteditable=true]"); }

  document.addEventListener("click", function (event) {
    if (suppressClick && event.target.closest(".causal-svg")) {
      suppressClick = false;
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    var target = event.target.closest("[data-explore],[data-search-id]");
    if (target) {
      explore(target.dataset.explore || target.dataset.searchId);
      return;
    }
    var zoomButton = event.target.closest("[data-zoom]");
    if (zoomButton) zoom(zoomButton.dataset.zoom === "in" ? 1.25 : 0.8);
    if (event.target.closest("[data-reset-view]")) fit();
    if (event.target.closest("[data-dismiss-error]")) document.getElementById("request-error").hidden = true;
    var selectButton = event.target.closest("[data-sources-select]");
    if (selectButton) document.querySelectorAll("#sources-form input").forEach(function (input) {
      input.checked = selectButton.dataset.sourcesSelect === "all";
    });
    if (!event.target.closest(".search")) closeSearch();
  }, true);

  document.addEventListener("input", function (event) {
    if (event.target.id === "variable-search") search();
  });
  document.addEventListener("focusin", function (event) {
    if (event.target.id === "variable-search") search();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { closeSearch(); return; }
    if (event.key === "/" && !editable(event.target)) {
      event.preventDefault();
      document.getElementById("variable-search").focus();
      return;
    }
    if (event.target.closest(".search") && ["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) {
      var results = Array.from(document.querySelectorAll("[data-search-id]:not([hidden])"));
      var index = results.indexOf(document.activeElement);
      if (event.key === "Enter" && event.target.id === "variable-search" && results.length) {
        event.preventDefault(); explore(results[0].dataset.searchId);
      } else if (event.key !== "Enter") {
        event.preventDefault();
        var next = event.key === "ArrowDown" ? index + 1 : index - 1;
        if (next < 0) document.getElementById("variable-search").focus();
        else if (results.length) results[Math.min(next, results.length - 1)].focus();
      }
      return;
    }
    if (editable(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "0") { event.preventDefault(); fit(); }
    if (event.target.closest("#graph-panel")) {
      if (["+", "=", "-"].includes(event.key)) {
        event.preventDefault(); zoom(event.key === "-" ? 0.8 : 1.25);
      }
      if (["Enter", " "].includes(event.key) && event.target.matches(".node,.edge-hit")) {
        event.preventDefault();
        restoreGraphFocus = event.target.matches(".node");
        event.target.dispatchEvent(new MouseEvent("click", {bubbles: true}));
      }
    }
  });

  document.addEventListener("wheel", function (event) {
    if (!event.target.closest(".causal-svg")) return;
    event.preventDefault();
    zoom(Math.exp(-event.deltaY * 0.0015), event.clientX, event.clientY);
  }, {passive: false});

  document.addEventListener("pointerdown", function (event) {
    var current = event.target.closest(".causal-svg");
    if (!current || event.button !== 0) return;
    suppressClick = false;
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pointers.size === 2) {
      var points = Array.from(pointers.values());
      pinch = {distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y)};
      pointer = null;
      current.setPointerCapture(event.pointerId);
      return;
    }
    if (event.target.closest(".node,.edge-hit")) return;
    current.setPointerCapture(event.pointerId);
    pointer = {id: event.pointerId, x: event.clientX, y: event.clientY, initialX: transform.x, initialY: transform.y, moved: false};
    current.classList.add("panning");
  });

  document.addEventListener("pointermove", function (event) {
    if (pointers.has(event.pointerId)) pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pinch && pointers.size === 2) {
      var points = Array.from(pointers.values());
      var distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      if (pinch.distance > 0) zoom(distance / pinch.distance, (points[0].x + points[1].x) / 2, (points[0].y + points[1].y) / 2);
      pinch.distance = distance;
      suppressClick = true;
      return;
    }
    if (!pointer || pointer.id !== event.pointerId) return;
    var deltaX = event.clientX - pointer.x;
    var deltaY = event.clientY - pointer.y;
    if (Math.hypot(deltaX, deltaY) > 4) pointer.moved = true;
    transform.x = pointer.initialX + deltaX;
    transform.y = pointer.initialY + deltaY;
    applyTransform();
  });

  function finishPointer(event) {
    pointers.delete(event.pointerId);
    if (pointer && pointer.id === event.pointerId) {
      suppressClick = pointer.moved;
      pointer = null;
    }
    if (pointers.size < 2) pinch = null;
    if (svg()) svg().classList.remove("panning");
  }
  document.addEventListener("pointerup", finishPointer);
  document.addEventListener("pointercancel", finishPointer);
  document.addEventListener("dblclick", function (event) {
    if (event.target.closest(".causal-svg") && !event.target.closest(".node,.edge-hit")) fit();
  });
  ["htmx:responseError", "htmx:sendError", "htmx:timeout"].forEach(function (name) {
    document.addEventListener(name, function () { document.getElementById("request-error").hidden = false; });
  });
  document.addEventListener("htmx:afterSettle", function (event) {
    setup();
    var target = event.detail.target;
    if (window.matchMedia("(max-width: 760px)").matches && target && ["graph-panel", "inspector"].includes(target.id)) {
      var destination = document.getElementById(target.id);
      destination.scrollIntoView({block: "start", behavior: "instant"});
    }
  });
  document.addEventListener("htmx:historyRestore", function () { graphKey = null; setup(); });
  window.addEventListener("resize", fit);
  setup();
})();
