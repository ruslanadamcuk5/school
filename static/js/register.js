/* Форма регистрации: переключение роли и загрузка городов/школ/классов. */
(function () {
  "use strict";

  const form = document.getElementById("register-form");
  if (!form) return;

  const blocks = form.querySelectorAll(".role-block");
  const roleInputs = form.querySelectorAll('input[name="role"]');

  function currentRole() {
    const checked = form.querySelector('input[name="role"]:checked');
    return checked ? checked.value : "student";
  }

  function syncRole() {
    const role = currentRole();
    blocks.forEach((block) => {
      const active = block.getAttribute("data-role") === role;
      block.style.display = active ? "" : "none";
      block.querySelectorAll("select, input").forEach((el) => {
        el.disabled = !active;
      });
    });
  }

  roleInputs.forEach((input) => input.addEventListener("change", syncRole));
  syncRole();

  async function fetchJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return response.json();
  }

  async function loadCities(select) {
    const data = await fetchJSON("/api/org/cities");
    if (!data) return;
    select.innerHTML = '<option value="">— выбери город —</option>';
    data.cities.forEach((city) => {
      const option = document.createElement("option");
      option.value = city.id;
      option.textContent = city.name;
      select.appendChild(option);
    });
  }

  async function loadSchools(select, cityId) {
    const data = await fetchJSON("/api/org/schools?city_id=" + encodeURIComponent(cityId));
    select.innerHTML = '<option value="">— выбери школу —</option>';
    if (!data) return;
    data.schools.forEach((school) => {
      const option = document.createElement("option");
      option.value = school.id;
      option.textContent = school.name + " (" + school.city_name + ")";
      select.appendChild(option);
    });
  }

  async function loadClasses(target, schoolId, mode) {
    const data = await fetchJSON("/api/org/classes?school_id=" + encodeURIComponent(schoolId));
    if (!data) return;
    if (mode === "checkbox") {
      target.innerHTML = "";
      if (!data.classes.length) {
        target.innerHTML = '<span class="muted small">В этой школе пока нет классов — обратитесь к администратору.</span>';
        return;
      }
      data.classes.forEach((klass) => {
        const label = document.createElement("label");
        label.className = "check-item";
        label.innerHTML =
          '<input type="checkbox" name="class_ids" value="' + klass.id + '">' +
          "<span><b>" + klass.title + "</b> · " + klass.students_count + " уч." +
          (klass.teacher_name ? " · ведёт: " + klass.teacher_name : " · учитель не назначен") +
          "</span>";
        target.appendChild(label);
      });
      return;
    }
    target.innerHTML = '<option value="">— выбери класс —</option>';
    data.classes.forEach((klass) => {
      const option = document.createElement("option");
      option.value = klass.id;
      option.textContent = klass.title + " (" + klass.students_count + " уч.)";
      option.dataset.teacher = klass.teacher_name || "";
      target.appendChild(option);
    });
  }

  document.querySelectorAll("[data-load]").forEach((select) => {
    if (select.id === "student_city" || select.id === "teacher_city") {
      loadCities(select);
    }
    select.addEventListener("change", async function () {
      const kind = select.getAttribute("data-load");
      const target = document.getElementById(select.getAttribute("data-target"));
      if (!target) return;
      if (kind === "schools") {
        if (!select.value) {
          target.innerHTML = '<option value="">— выбери школу —</option>';
          return;
        }
        await loadSchools(target, select.value);
      } else if (kind === "classes") {
        const mode = target.id === "teacher_classes" ? "checkbox" : "select";
        if (!select.value) {
          target.innerHTML = mode === "checkbox"
            ? '<span class="muted small">Сначала выберите школу.</span>'
            : '<option value="">— выбери класс —</option>';
          return;
        }
        await loadClasses(target, select.value, mode);
      }
    });
  });

  const studentClass = document.getElementById("student_class");
  const teacherHint = document.getElementById("teacher-hint");
  if (studentClass && teacherHint) {
    studentClass.addEventListener("change", function () {
      const option = studentClass.selectedOptions[0];
      const teacher = option ? option.dataset.teacher : "";
      teacherHint.textContent = teacher
        ? "Ваш учитель: " + teacher + " — подставится автоматически."
        : "Учитель класса подставится автоматически.";
    });
  }
})();
