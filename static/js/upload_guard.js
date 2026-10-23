// Проверка размера PDF до отправки — чтобы не получать 413 от сервера.
(function () {
  "use strict";

  var input = document.getElementById("file");
  if (!input) return;

  var maxMb = parseInt(input.dataset.maxMb, 10) || 60;
  var maxBytes = maxMb * 1024 * 1024;
  var form = input.form;

  function tooBig(file) {
    return file && file.size > maxBytes;
  }

  function warn(file) {
    var mb = (file.size / (1024 * 1024)).toFixed(1);
    window.alert(
      "Файл «" + file.name + "» весит " + mb + " МБ, а можно не больше " + maxMb + " МБ.\n" +
      "Сожмите PDF или выберите файл поменьше."
    );
  }

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (tooBig(file)) {
      warn(file);
      input.value = "";
    }
  });

  if (form) {
    form.addEventListener("submit", function (event) {
      var file = input.files && input.files[0];
      if (tooBig(file)) {
        event.preventDefault();
        warn(file);
      }
    });
  }
})();
