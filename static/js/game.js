/* Игровой экран: ответы, подсказки, обратная связь. */
(function () {
  "use strict";

  const root = document.querySelector("[data-game]");
  if (!root) return;

  const answerType = root.getAttribute("data-answer-type") || "number";
  const topic = root.getAttribute("data-topic") || "";
  const mode = root.getAttribute("data-mode") || "practice";
  const nextUrl = root.getAttribute("data-next-url") || "";

  const form = document.getElementById("answer-form");
  const input = document.getElementById("answer-input");
  const choicesBox = document.getElementById("choices");
  const feedback = document.getElementById("feedback");
  const feedbackText = document.getElementById("feedback-text");
  const feedbackAnswer = document.getElementById("feedback-answer");
  const hintBox = document.getElementById("hint-box");
  const hintText = document.getElementById("hint-text");
  const card = document.getElementById("task-card");
  const progressFill = document.getElementById("progress-fill");
  const progressLabel = document.getElementById("progress-label");
  const coinsEl = document.getElementById("coin-count");
  const comboEl = document.getElementById("combo-count");
  const hintBtn = document.getElementById("hint-btn");
  const switchBtn = document.getElementById("switch-method-btn");
  const methodLabel = document.getElementById("method-label");

  let busy = false;

  function setBusy(value) {
    busy = value;
    if (form) form.querySelectorAll("button, input").forEach((el) => (el.disabled = value));
    if (choicesBox) choicesBox.querySelectorAll("button").forEach((el) => (el.disabled = value));
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.App.csrf() },
      body: JSON.stringify(body || {}),
    });
    if (!response.ok) {
      let detail = {};
      try { detail = await response.json(); } catch (e) { /* ignore */ }
      throw new Error(detail.error || "Ошибка " + response.status);
    }
    return response.json();
  }

  function showFeedback(ok, data) {
    if (!feedback) return;
    feedback.className = "feedback is-visible " + (ok ? "feedback--ok" : "feedback--err");
    const parts = [];
    if (ok) {
      parts.push("<b>Правильно! 🎉</b>");
      if (data.xp) parts.push(" +" + data.xp + " XP, +" + data.coins + " 💰");
      if (data.solution) parts.push("<br><span>" + data.solution + "</span>");
    } else {
      parts.push("<b>Пока не то.</b>");
      if (data.retry) parts.push("<br>Попробуй ещё раз — не спеши!");
      else parts.push("<br>Правильный ответ: <b>" + data.correct_answer + "</b>");
      if (data.solution) parts.push("<br><span>" + data.solution + "</span>");
    }
    if (data.badges && data.badges.length) {
      parts.push("<br><b>Новый значок: " + data.badges.map((b) => b.icon + " " + b.name).join(", ") + "</b>");
    }
    feedback.innerHTML = parts.join(" ");
    if (feedbackAnswer) feedbackAnswer.textContent = data.correct_answer || "";
  }

  function showHint(text) {
    if (!hintBox || !text) return;
    hintText.innerHTML = text;
    hintBox.classList.add("is-visible");
  }

  function updateProgress(data) {
    if (coinsEl) coinsEl.textContent = parseInt(coinsEl.textContent || "0", 10) + (data.coins || 0);
    if (comboEl) comboEl.textContent = data.combo || 0;
  }

  function showCombo(value) {
    if (!value || value < 2) return;
    const el = document.createElement("div");
    el.className = "combo-badge";
    el.textContent = "Комбо ×" + value + " 🔥";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1000);
  }

  async function submitAnswer(value) {
    if (busy) return;
    if (value === "" || value === null) {
      if (input) input.focus();
      return;
    }
    setBusy(true);
    try {
      const data = await post("/api/answer", { answer: value });
      showFeedback(data.correct, data);
      updateProgress(data);
      if (data.hint) showHint("💡 " + data.hint);

      if (data.correct) {
        window.App.sound.correct();
        window.App.confetti(60);
        if (card) card.classList.add("task-card--right");
        showCombo(data.combo);
        if (data.badges && data.badges.length) window.App.sound.levelUp();
        setTimeout(() => {
          if (data.done) {
            window.location.href = "/play/" + topic + "/result";
          } else {
            window.location.reload();
          }
        }, data.done ? 1600 : 1500);
      } else {
        window.App.sound.wrong();
        if (card) card.classList.add("task-card--wrong");
        if (!data.retry && card) card.classList.add("task-card--wrong");
        if (!data.retry) {
          setTimeout(() => {
            if (data.done) window.location.href = "/play/" + topic + "/result";
            else window.location.reload();
          }, 3200);
        } else {
          setBusy(false);
          if (input) {
            input.value = "";
            input.classList.remove("is-wrong");
            input.focus();
          }
          choicesBox && choicesBox.querySelectorAll(".choice").forEach((b) => b.classList.remove("is-wrong"));
        }
      }
    } catch (err) {
      setBusy(false);
      window.App.toast("Что-то пошло не так. Попробуй ещё раз.");
      if (input) input.focus();
    }
  }

  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const value = input ? input.value.trim() : "";
      submitAnswer(value);
    });
  }

  if (choicesBox) {
    choicesBox.querySelectorAll(".choice").forEach((btn) => {
      btn.addEventListener("click", function () {
        if (busy) return;
        choicesBox.querySelectorAll(".choice").forEach((b) => b.classList.remove("is-correct", "is-wrong"));
        btn.classList.add("is-correct");
        submitAnswer(btn.getAttribute("data-value"));
      });
    });
  }

  if (hintBtn) {
    hintBtn.addEventListener("click", async function () {
      if (busy) return;
      try {
        const data = await post("/api/hint", {});
        if (data.hint) {
          showHint("💡 " + data.hint);
          window.App.sound.click();
          hintBtn.textContent = "Ещё подсказка (" + (data.left || 0) + ")";
          if (!data.left) hintBtn.disabled = true;
        }
      } catch (e) {
        window.App.toast("Подсказки закончились — попробуй сам!");
      }
    });
  }

  if (switchBtn) {
    switchBtn.addEventListener("click", async function () {
      try {
        const data = await post("/api/switch-method", {});
        if (methodLabel && data.name) {
          methodLabel.textContent = "Способ: " + data.name;
          window.App.toast("Объясняем по-другому: " + data.name);
        }
        window.App.sound.click();
      } catch (e) {
        window.App.toast("Не удалось сменить способ объяснения");
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && input && document.activeElement === input) {
      event.preventDefault();
      submitAnswer(input.value.trim());
    }
  });

  const keypad = document.getElementById("keypad");
  if (keypad && input) {
    keypad.querySelectorAll(".keypad__key").forEach((key) => {
      key.addEventListener("click", function () {
        const value = key.getAttribute("data-key");
        if (value === "clear") input.value = "";
        else if (value === "back") input.value = input.value.slice(0, -1);
        else input.value += value;
        window.App.sound.click();
        input.focus();
      });
    });
  }

  if (input) input.focus();
})();
