/* Передача геолокации из браузера: только после явного согласия ребёнка. */
(function () {
  "use strict";

  var cfg = window.CHILD_LOCATION;
  if (!cfg) return;

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
  var stateEl = document.getElementById("loc-state");
  var stateText = document.getElementById("loc-state-text");
  var startBtn = document.getElementById("loc-start");
  var stopBtn = document.getElementById("loc-stop");
  var clearBtn = document.getElementById("loc-clear");
  var flashBox = document.getElementById("loc-flash");
  var sentEl = document.getElementById("loc-sent");
  var lastEl = document.getElementById("loc-last");
  var accuracyEl = document.getElementById("loc-accuracy");

  var enabled = false;
  var watchId = null;
  var flushTimer = null;
  var pending = [];
  var sending = false;
  var sentCount = 0;
  var batteryLevel = null;

  function setFlash(text, isError) {
    flashBox.textContent = text || "";
    flashBox.style.color = isError ? "#ef4444" : "";
  }

  function setState(on) {
    enabled = on;
    stateEl.className = "geo-state geo-state--" + (on ? "on" : "off");
    stateText.textContent = on ? "Включена" : "Выключена";
    startBtn.disabled = on;
    stopBtn.disabled = !on;
  }

  function timeLabel(value) {
    if (!value) return "—";
    var d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  async function api(url, options) {
    options = options || {};
    options.credentials = "same-origin";
    options.headers = Object.assign(
      { "Accept": "application/json", "X-CSRFToken": csrfToken },
      options.headers || {}
    );
    var response = await fetch(url, options);
    var data = await response.json().catch(function () { return {}; });
    if (!response.ok || data.ok === false) {
      throw new Error(data.message || "Ошибка сервера");
    }
    return data;
  }

  function currentPosition() {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) {
        reject(new Error("Браузер не поддерживает геолокацию"));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 5000
      });
    });
  }

  function positionError(error) {
    if (!error) return "Не удалось определить местоположение";
    if (error.code === 1) return "Доступ к геолокации запрещён. Разрешите его в настройках браузера.";
    if (error.code === 2) return "Местоположение недоступно. Проверьте GPS и интернет.";
    if (error.code === 3) return "Не удалось определить местоположение вовремя.";
    return error.message || "Ошибка геолокации";
  }

  function queuePoint(position) {
    var coords = position.coords || {};
    pending.push({
      lat: coords.latitude,
      lon: coords.longitude,
      accuracy: coords.accuracy,
      altitude: coords.altitude,
      speed: coords.speed,
      source: "web",
      recorded_at: new Date(position.timestamp || Date.now()).toISOString()
    });
    if (pending.length > 250) pending = pending.slice(-250);
    if (coords.accuracy != null) accuracyEl.textContent = "±" + Math.round(coords.accuracy) + " м";
    if (pending.length >= 3) flush();
  }

  async function flush() {
    if (sending || !pending.length) return;
    if (!navigator.onLine) {
      setFlash("Нет интернета — точки сохранены и отправятся позже.", true);
      return;
    }
    sending = true;
    var batch = pending.slice(0, 100);
    try {
      var data = await api(cfg.pointsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ points: batch, battery: batteryLevel })
      });
      pending = pending.slice(batch.length);
      sentCount += Number(data.saved || 0);
      sentEl.textContent = String(sentCount);
      if (data.last_point_at) lastEl.textContent = timeLabel(data.last_point_at);
      setFlash(
        data.saved
          ? "Отправлено точек: " + data.saved + ". Родитель видит твою позицию."
          : "Точки уже были отправлены ранее.",
        false
      );
      if (pending.length) setTimeout(flush, 1500);
    } catch (error) {
      setFlash(error.message || "Не удалось отправить точки", true);
    } finally {
      sending = false;
    }
  }

  function startWatch() {
    if (watchId != null) return;
    if (!navigator.geolocation) {
      setFlash("Браузер не поддерживает геолокацию", true);
      return;
    }
    watchId = navigator.geolocation.watchPosition(
      function (position) {
        queuePoint(position);
        setState(true);
      },
      function (error) {
        setFlash(positionError(error), true);
        setState(false);
        stopWatch();
      },
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 30000 }
    );
    flushTimer = setInterval(flush, 20000);
  }

  function stopWatch() {
    if (watchId != null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchId);
    }
    watchId = null;
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = null;
  }

  async function enable() {
    if (enabled) return;
    setFlash("Запрашиваем доступ к геолокации…", false);
    try {
      var position = await currentPosition();
      var data = await api(cfg.setStatusUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true })
      });
      setState(Boolean(data.enabled));
      queuePoint(position);
      startWatch();
      await flush();
      setFlash("Передача включена. Точки будут обновляться автоматически.", false);
    } catch (error) {
      setFlash(positionError(error), true);
      setState(false);
    }
  }

  async function disable() {
    if (!enabled) return;
    await flush();
    stopWatch();
    try {
      await api(cfg.setStatusUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: false })
      });
      setState(false);
      pending = [];
      setFlash("Передача остановлена. Родитель больше не видит новые точки.", false);
    } catch (error) {
      setFlash(error.message || "Не удалось остановить передачу", true);
    }
  }

  async function clearHistory() {
    if (!window.confirm("Удалить всю историю геолокации? Родитель не сможет посмотреть старые точки.")) return;
    try {
      var data = await api(cfg.historyUrl, { method: "DELETE" });
      sentCount = 0;
      sentEl.textContent = "0";
      lastEl.textContent = "—";
      setFlash(data.message || "История удалена", false);
    } catch (error) {
      setFlash(error.message || "Не удалось удалить историю", true);
    }
  }

  async function loadStatus() {
    try {
      var data = await api(cfg.statusUrl, { method: "GET" });
      setState(Boolean(data.enabled));
      if (data.last_point) {
        lastEl.textContent = timeLabel(data.last_point.recorded_at);
        if (data.last_point.accuracy != null) {
          accuracyEl.textContent = "±" + Math.round(data.last_point.accuracy) + " м";
        }
      }
      if (data.enabled) {
        setFlash("Передача уже включена — продолжаем делиться позицией.", false);
        startWatch();
      }
    } catch (error) {
      setFlash(error.message || "Не удалось получить статус", true);
      setState(false);
    }
  }

  if (navigator.getBattery) {
    navigator.getBattery().then(function (battery) {
      batteryLevel = Math.round(battery.level * 100);
      battery.addEventListener("levelchange", function () {
        batteryLevel = Math.round(battery.level * 100);
      });
    }).catch(function () {});
  }

  startBtn.addEventListener("click", enable);
  stopBtn.addEventListener("click", disable);
  clearBtn.addEventListener("click", clearHistory);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("beforeunload", function () {
    if (!pending.length || !window.fetch) return;
    try {
      fetch(cfg.pointsUrl, {
        method: "POST",
        keepalive: true,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ points: pending, battery: batteryLevel })
      });
    } catch (error) { /* ignore */ }
  });

  stopBtn.disabled = true;
  loadStatus();
})();
