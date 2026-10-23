/* Всплывающий ИИ-помощник по приложению.
   Подключается на страницах только когда ИИ настроен (см. base.html). */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;
  // На странице помощника виджет не нужен — там своя форма.
  if (document.body && document.body.dataset.aiInline) return;

  var askUrl = script.getAttribute("data-ask-url");
  var pageUrl = script.getAttribute("data-page-url");
  if (!askUrl || !document.body) return;

  function csrf() {
    if (window.App && typeof window.App.csrf === "function") return window.App.csrf();
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  var button = document.createElement("button");
  button.type = "button";
  button.className = "ai-fab";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-label", "Помощник по приложению");
  button.innerHTML =
    '<span aria-hidden="true">🤖</span><span class="ai-fab__label">Помощник</span>';

  var panel = document.createElement("section");
  panel.className = "ai-panel";
  panel.setAttribute("hidden", "");
  panel.setAttribute("aria-label", "Помощник");
  panel.innerHTML =
    '<header class="ai-panel__head">' +
      "<span>🤖 Помощник</span>" +
      '<span class="ai-panel__actions">' +
        (pageUrl
          ? '<a href="' + pageUrl + '" title="Открыть отдельной страницей">↗</a>'
          : "") +
        '<button type="button" class="ai-panel__close" aria-label="Закрыть">✕</button>' +
      "</span>" +
    "</header>" +
    '<div class="ai-thread">' +
      '<div class="ai-msg ai-msg--bot">Здравствуйте! Подскажу, как пользоваться ' +
      "приложением. Спросите, например: «Как пройти тест по теме?»</div>" +
    "</div>" +
    '<form class="ai-form">' +
      '<textarea rows="2" maxlength="2000" placeholder="Ваш вопрос…" required></textarea>' +
      '<button type="submit" class="btn btn--small">Отправить</button>' +
    "</form>";

  document.body.appendChild(button);
  document.body.appendChild(panel);

  var thread = panel.querySelector(".ai-thread");
  var form = panel.querySelector(".ai-form");
  var textarea = form.querySelector("textarea");
  var submit = form.querySelector("button[type=submit]");

  function open() {
    panel.removeAttribute("hidden");
    button.setAttribute("aria-expanded", "true");
    if (textarea) textarea.focus();
  }

  function close() {
    panel.setAttribute("hidden", "");
    button.setAttribute("aria-expanded", "false");
  }

  button.addEventListener("click", function () {
    if (panel.hasAttribute("hidden")) open();
    else close();
  });
  panel.querySelector(".ai-panel__close").addEventListener("click", close);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !panel.hasAttribute("hidden")) close();
  });

  function add(role, content, asText) {
    var el = document.createElement("div");
    el.className = "ai-msg ai-msg--" + role;
    if (asText) el.textContent = content;
    else el.innerHTML = content;
    thread.appendChild(el);
    thread.scrollTop = thread.scrollHeight;
    return el;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var question = (textarea.value || "").trim();
    if (!question) return;
    add("user", question, true);
    textarea.value = "";
    submit.disabled = true;

    var pending = add("bot", "Думаю…");
    pending.classList.add("ai-msg--pending");

    fetch(askUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrf()
      },
      body: JSON.stringify({
        question: question,
        page: location.pathname + location.search
      })
    })
      .then(function (response) {
        return response.json().catch(function () {
          return { ok: false, error: "Ошибка ответа сервера." };
        });
      })
      .then(function (data) {
        pending.classList.remove("ai-msg--pending");
        if (data && data.ok) {
          pending.classList.add("ai-msg--rich");
          pending.innerHTML = data.html || data.answer || "";
        } else {
          pending.classList.add("ai-msg--error");
          pending.textContent = (data && data.error) || "Не удалось получить ответ.";
        }
        thread.scrollTop = thread.scrollHeight;
      })
      .catch(function () {
        pending.classList.remove("ai-msg--pending");
        pending.classList.add("ai-msg--error");
        pending.textContent = "Нет связи с сервисом ИИ.";
      })
      .then(function () {
        submit.disabled = false;
        if (textarea) textarea.focus();
      });
  });
})();
