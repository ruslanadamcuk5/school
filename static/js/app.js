/* Общие утилиты: озвучка, звуки, конфетти, виджеты. */
(function (global) {
  "use strict";

  const App = {};

  /* --------------------------------------------------------------- CSRF */
  App.csrf = function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  };

  /* ------------------------------------------------------------ озвучка */
  let voice = null;
  function pickVoice() {
    if (!("speechSynthesis" in global)) return null;
    const voices = global.speechSynthesis.getVoices() || [];
    voice =
      voices.find((v) => /ru[-_]BY/i.test(v.lang)) ||
      voices.find((v) => /^ru/i.test(v.lang)) ||
      voices.find((v) => /belarus/i.test(v.name)) ||
      null;
    return voice;
  }
  if ("speechSynthesis" in global) {
    pickVoice();
    global.speechSynthesis.onvoiceschanged = pickVoice;
  }

  App.speak = function (text, button) {
    if (!text) return;
    if (!("speechSynthesis" in global)) {
      App.toast("Браузер не умеет читать вслух. Попробуй Chrome или Edge.");
      return;
    }
    try {
      global.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(String(text).replace(/\s+/g, " ").trim());
      utter.lang = "ru-BE";
      utter.rate = 0.92;
      utter.pitch = 1.08;
      if (!voice) pickVoice();
      if (voice) utter.voice = voice;
      if (button) {
        button.classList.add("is-speaking");
        utter.onend = utter.onerror = () => button.classList.remove("is-speaking");
      }
      global.speechSynthesis.speak(utter);
    } catch (e) {
      /* тихо игнорируем */
    }
  };

  App.stopSpeak = function () {
    if ("speechSynthesis" in global) global.speechSynthesis.cancel();
  };

  /* ------------------------------------------------------------- звуки */
  const Audio = global.AudioContext || global.webkitAudioContext;
  let ctx = null;
  function audio() {
    if (!Audio) return null;
    if (!ctx) ctx = new Audio();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone(freq, start, dur, type, gain) {
    const c = audio();
    if (!c) return;
    const osc = c.createOscillator();
    const vol = c.createGain();
    osc.type = type || "sine";
    osc.frequency.setValueAtTime(freq, c.currentTime + start);
    vol.gain.setValueAtTime(0.0001, c.currentTime + start);
    vol.gain.exponentialRampToValueAtTime(gain || 0.18, c.currentTime + start + 0.02);
    vol.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + start + dur);
    osc.connect(vol).connect(c.destination);
    osc.start(c.currentTime + start);
    osc.stop(c.currentTime + start + dur + 0.05);
  }

  const Sound = {
    correct() { tone(660, 0, 0.12, "sine", 0.16); tone(880, 0.11, 0.16, "sine", 0.16); },
    wrong() { tone(240, 0, 0.18, "triangle", 0.14); tone(180, 0.16, 0.22, "triangle", 0.12); },
    coin() { tone(1180, 0, 0.08, "square", 0.09); tone(1560, 0.07, 0.12, "square", 0.08); },
    levelUp() {
      [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.1, 0.2, "triangle", 0.15));
    },
    click() { tone(520, 0, 0.05, "sine", 0.07); },
  };
  App.sound = Sound;

  /* ---------------------------------------------------------- конфетти */
  App.confetti = function (count) {
    if (global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = document.createElement("canvas");
    canvas.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:95";
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const colors = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#06b6d4", "#8b5cf6"];
    const pieces = [];
    for (let i = 0; i < (count || 70); i++) {
      pieces.push({
        x: Math.random() * canvas.width,
        y: -20 - Math.random() * canvas.height * 0.5,
        w: 6 + Math.random() * 8,
        h: 8 + Math.random() * 10,
        color: colors[Math.floor(Math.random() * colors.length)],
        vy: 2 + Math.random() * 3,
        vr: (Math.random() - 0.5) * 0.2,
        rot: Math.random() * Math.PI,
      });
    }
    let frames = 0;
    function tick() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach((p) => {
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      });
      frames++;
      if (frames < 220) requestAnimationFrame(tick);
      else canvas.remove();
    }
    requestAnimationFrame(tick);
  };

  /* ------------------------------------------------------------- тосты */
  App.toast = function (message, ms) {
    const box = document.querySelector(".flash-stack");
    if (!box) return;
    const el = document.createElement("div");
    el.className = "flash flash--info";
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.remove(), ms || 3200);
  };

  /* ----------------------------------------------------------- виджеты */
  App.renderWidgets = function (root) {
    const scope = root || document;
    scope.querySelectorAll("[data-widget]").forEach((el) => {
      let spec = null;
      try {
        spec = JSON.parse(el.getAttribute("data-widget"));
      } catch (e) {
        return;
      }
      const html = global.Widgets ? global.Widgets.render(spec) : "";
      if (html) el.innerHTML = html;
    });
  };

  /* ------------------------------------------------------------- инициализация */
  document.addEventListener("DOMContentLoaded", function () {
    App.renderWidgets(document);

    document.querySelectorAll("[data-speak-target]").forEach((btn) => {
      btn.addEventListener("click", function () {
        const target = document.getElementById(btn.getAttribute("data-speak-target"));
        const text = target ? target.getAttribute("data-speak") || target.textContent : btn.getAttribute("data-speak");
        App.speak(text, btn);
      });
    });

    document.querySelectorAll("[data-speak]").forEach((el) => {
      if (el.id && el.tagName !== "BUTTON") {
        el.setAttribute("data-speak-text", el.getAttribute("data-speak"));
      }
    });

    const auto = document.querySelector("[data-autospeak]");
    if (auto) {
      setTimeout(() => App.speak(auto.getAttribute("data-autospeak")), 450);
    }
  });

  global.App = App;
})(window);
