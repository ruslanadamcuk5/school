/* Карта детей: последние точки и трек за день (Leaflet + OpenStreetMap). */
(function () {
  "use strict";

  var root = window.PARENT_MAP;
  if (!root) return;

  var learnerSelect = document.getElementById("geo-learner");
  var dateInput = document.getElementById("geo-date");
  var refreshBtn = document.getElementById("geo-refresh");
  var requestBtn = document.getElementById("geo-request");
  var flashBox = document.getElementById("geo-flash");
  var overviewBox = document.getElementById("geo-overview");
  var summaryBox = document.getElementById("geo-summary");
  var timeline = document.getElementById("geo-timeline");
  var mapBox = document.getElementById("geo-map");
  if (!learnerSelect || !mapBox) return;

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

  function localIso(date) {
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  }

  function tzOffset() {
    return -new Date().getTimezoneOffset();
  }

  if (!dateInput.value) dateInput.value = localIso(new Date());
  dateInput.max = localIso(new Date());

  var map = null;
  var trackLayer = null;
  var overviewLayer = null;
  var trackBounds = null;

  if (window.L) {
    map = L.map(mapBox, { zoomControl: true }).setView([53.9023, 27.5619], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
    }).addTo(map);
    trackLayer = L.layerGroup().addTo(map);
    overviewLayer = L.layerGroup().addTo(map);
  } else {
    mapBox.innerHTML = '<div class="geo-empty">Карта не загрузилась. Проверьте соединение и обновите страницу.</div>';
  }

  function setFlash(text, isError) {
    if (!flashBox) return;
    flashBox.textContent = text || "";
    flashBox.style.color = isError ? "#ef4444" : "";
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function addText(parent, tag, text, className) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = text == null ? "" : String(text);
    parent.appendChild(el);
    return el;
  }

  function formatDistance(meters) {
    if (!meters) return "0 м";
    if (meters < 1000) return Math.round(meters) + " м";
    return (meters / 1000).toFixed(meters < 10000 ? 1 : 0) + " км";
  }

  function formatDuration(minutes) {
    if (!minutes) return "0 мин";
    if (minutes < 60) return minutes + " мин";
    return Math.floor(minutes / 60) + " ч " + (minutes % 60) + " мин";
  }

  function timeOfIso(value) {
    if (!value) return "";
    var d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }

  function dateTimeOfIso(value) {
    if (!value) return "";
    var d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  function buildUrl(base, params) {
    var url = new URL(base, window.location.origin);
    Object.keys(params).forEach(function (key) {
      if (params[key] !== undefined && params[key] !== null && params[key] !== "") {
        url.searchParams.set(key, params[key]);
      }
    });
    return url.toString();
  }

  function drawTrack(data) {
    if (!map) return;
    trackLayer.clearLayers();
    trackBounds = null;
    var points = data.points || [];
    if (!points.length) return;

    var latlngs = points.map(function (p) { return [p.lat, p.lon]; });
    trackBounds = L.latLngBounds(latlngs);
    L.polyline(latlngs, {
      color: "#6366f1", weight: 5, opacity: 0.82, lineJoin: "round", lineCap: "round"
    }).addTo(trackLayer);

    var labelStep = Math.max(1, Math.ceil(points.length / 12));
    points.forEach(function (p, index) {
      var isEdge = index === 0 || index === points.length - 1;
      var marker = L.circleMarker([p.lat, p.lon], {
        radius: isEdge ? 8 : 5,
        color: "#ffffff",
        weight: 2,
        fillColor: isEdge ? "#4338ca" : "#6366f1",
        fillOpacity: 1
      }).addTo(trackLayer);
      var parts = [p.time || timeOfIso(p.recorded_at)];
      if (p.accuracy != null) parts.push("±" + Math.round(p.accuracy) + " м");
      if (p.speed) parts.push((p.speed * 3.6).toFixed(1) + " км/ч");
      marker.bindPopup(parts.join(" · "));
      if (index % labelStep === 0 || isEdge) {
        marker.bindTooltip(p.time || timeOfIso(p.recorded_at), {
          permanent: true,
          direction: "top",
          offset: [0, -8],
          className: "geo-time-label"
        });
      }
    });

    map.fitBounds(trackBounds, { padding: [28, 28], maxZoom: 17 });
  }

  function renderSummary(data) {
    clear(summaryBox);
    clear(timeline);
    var summary = data.summary || {};
    if (!data.points || !data.points.length) {
      var reason = data.sharing && !data.sharing.enabled
        ? "Передача геолокации у ребёнка выключена."
        : "За этот день точек нет.";
      addText(summaryBox, "p", reason, "muted");
      if (data.sharing && data.sharing.last_point_at) {
        addText(summaryBox, "p", "Последняя точка: " + dateTimeOfIso(data.sharing.last_point_at), "small muted");
      }
      return;
    }

    addText(summaryBox, "p",
      formatDistance(summary.distance_m) + " · " + formatDuration(summary.duration_min) +
      " · точек: " + summary.points, "");
    var details = [];
    if (summary.first_at) details.push("с " + timeOfIso(summary.first_at));
    if (summary.last_at) details.push("до " + timeOfIso(summary.last_at));
    if (summary.accuracy != null) details.push("точность ±" + Math.round(summary.accuracy) + " м");
    if (summary.max_speed) details.push("макс. " + (summary.max_speed * 3.6).toFixed(1) + " км/ч");
    addText(summaryBox, "p", details.join(" · "), "small muted");

    var fragment = document.createDocumentFragment();
    data.points.forEach(function (p) {
      var li = document.createElement("li");
      addText(li, "time", p.time || timeOfIso(p.recorded_at));
      var body = addText(li, "span", "");
      var text = p.lat.toFixed(5) + ", " + p.lon.toFixed(5);
      if (p.accuracy != null) text += " · ±" + Math.round(p.accuracy) + " м";
      if (p.battery != null) text += " · 🔋" + p.battery + "%";
      if (p.source) text += " · " + p.source;
      body.textContent = text;
      fragment.appendChild(li);
    });
    timeline.appendChild(fragment);
    if (data.summary && data.summary.last_at) {
      setFlash("Трек обновлён: последняя точка в " + timeOfIso(data.summary.last_at) + ".", false);
    }
  }

  function renderOverview(data) {
    if (!overviewBox || !map) return;
    clear(overviewBox);
    overviewLayer.clearLayers();
    var children = data.children || [];
    if (!children.length) {
      addText(overviewBox, "p", "Нет профилей детей.", "muted small");
      return;
    }
    children.forEach(function (child) {
      var info = child.learner || {};
      var sharing = child.sharing || {};
      var last = child.last_point;
      var row = document.createElement("button");
      row.type = "button";
      row.className = "geo-child" + (String(info.id) === String(learnerSelect.value) ? " is-selected" : "");
      row.addEventListener("click", function () {
        learnerSelect.value = String(info.id);
        loadTrack();
      });

      var dot = document.createElement("span");
      dot.className = "geo-dot" + (last ? (child.stale ? " geo-dot--stale" : " geo-dot--live") : "");
      dot.style.margin = "0";
      row.appendChild(dot);
      addText(row, "span", info.avatar || "👦", "");
      var body = document.createElement("span");
      body.className = "geo-child__body";
      addText(body, "span", (info.name || "Ребёнок") + " · " + (info.grade || "") + " класс", "geo-child__title");
      var meta;
      if (!sharing.enabled) {
        meta = "передача выключена";
      } else if (last) {
        meta = (child.stale ? "давно: " : "был(а) ") + dateTimeOfIso(last.recorded_at);
        if (last.battery != null) meta += " · 🔋" + last.battery + "%";
      } else {
        meta = "точек пока нет";
      }
      addText(body, "span", meta, "geo-child__meta");
      row.appendChild(body);
      overviewBox.appendChild(row);

      if (last) {
        var color = child.stale ? "#94a3b8" : "#16a34a";
        var marker = L.circleMarker([last.lat, last.lon], {
          radius: 10, color: "#ffffff", weight: 3, fillColor: color, fillOpacity: 1
        }).addTo(overviewLayer);
        marker.bindTooltip((info.avatar || "") + " " + (info.name || ""), {
          permanent: true, direction: "top", offset: [0, -10], className: "geo-time-label"
        });
        marker.bindPopup(
          "<b>" + (info.name || "Ребёнок") + "</b><br>" +
          dateTimeOfIso(last.recorded_at) + "<br>" +
          "±" + Math.round(last.accuracy || 0) + " м"
        );
        marker.on("click", function () {
          learnerSelect.value = String(info.id);
          loadTrack();
        });
      }
    });
  }

  async function loadTrack() {
    if (!learnerSelect.value) return;
    setFlash("Загружаем трек…", false);
    try {
      var url = buildUrl(root.dataUrl, {
        learner_id: learnerSelect.value,
        date: dateInput.value,
        tz: tzOffset()
      });
      var response = await fetch(url, { headers: { "Accept": "application/json" }, credentials: "same-origin" });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok || !data.ok) throw new Error(data.message || "Не удалось загрузить трек");
      renderSummary(data);
      drawTrack(data);
      if (map && trackBounds) map.fitBounds(trackBounds, { padding: [28, 28], maxZoom: 17 });
      var next = new URL(window.location.href);
      next.searchParams.set("learner_id", learnerSelect.value);
      next.searchParams.set("date", dateInput.value);
      window.history.replaceState({}, "", next.toString());
    } catch (error) {
      setFlash(error.message || "Ошибка загрузки", true);
      if (summaryBox) {
        clear(summaryBox);
        addText(summaryBox, "p", error.message || "Ошибка загрузки", "muted");
      }
    }
  }

  async function loadOverview() {
    if (!overviewBox) return;
    try {
      var url = buildUrl(root.overviewUrl, { tz: tzOffset() });
      var response = await fetch(url, { headers: { "Accept": "application/json" }, credentials: "same-origin" });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok || !data.ok) throw new Error(data.message || "Не удалось загрузить точки детей");
      renderOverview(data);
    } catch (error) {
      clear(overviewBox);
      addText(overviewBox, "p", error.message || "Ошибка загрузки", "muted small");
    }
  }

  async function requestLocation() {
    if (!learnerSelect.value) return;
    setFlash("Отправляем просьбу…", false);
    try {
      var response = await fetch(root.requestBase + learnerSelect.value, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": "application/json", "X-CSRFToken": csrfToken }
      });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok || !data.ok) throw new Error(data.message || "Не удалось отправить просьбу");
      setFlash(data.message || "Просьба отправлена", false);
      loadOverview();
    } catch (error) {
      setFlash(error.message || "Ошибка отправки", true);
    }
  }

  refreshBtn.addEventListener("click", loadTrack);
  learnerSelect.addEventListener("change", loadTrack);
  dateInput.addEventListener("change", loadTrack);
  requestBtn.addEventListener("click", requestLocation);

  var initialDate = new URL(window.location.href).searchParams.get("date");
  if (initialDate) dateInput.value = initialDate;
  loadOverview();
  loadTrack();
  setInterval(loadOverview, 60000);
})();
