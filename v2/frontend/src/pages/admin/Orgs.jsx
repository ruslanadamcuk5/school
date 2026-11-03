import { useMemo, useState } from "react";
import {
  Building2,
  Check,
  GraduationCap,
  Layers,
  MapPin,
  Pencil,
  Plus,
  School,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  Modal,
  PageHeader,
  Progress,
  Select,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { plural } from "../../lib/format";
import { MiniStat } from "./shared";

const TABS = [
  { key: "cities", label: "Города", icon: MapPin },
  { key: "schools", label: "Школы", icon: School },
  { key: "classes", label: "Классы", icon: GraduationCap },
  { key: "subjects", label: "Предметы", icon: Layers },
];

export function AdminOrgs() {
  const { data, loading, error, refresh } = useApi("/admin/orgs");
  const { data: usersData } = useApi("/admin/users?role=student", { ttl: 120_000 });
  const [tab, setTab] = useState("classes");
  const [cityOpen, setCityOpen] = useState(false);
  const [schoolOpen, setSchoolOpen] = useState(false);
  const [classOpen, setClassOpen] = useState(false);
  const [editClass, setEditClass] = useState(null);
  const [addStudentClass, setAddStudentClass] = useState(null);
  const [cityForm, setCityForm] = useState({ name: "", region: "" });
  const [schoolForm, setSchoolForm] = useState({ city_id: "", name: "", address: "", director: "" });
  const [classForm, setClassForm] = useState({ school_id: "", grade: 1, letter: "", teacher_id: "", year: "2025/2026", title: "" });
  const [classEditForm, setClassEditForm] = useState(null);
  const [studentId, setStudentId] = useState("");
  const { pending, run } = useAction();

  const cities = data?.cities || [];
  const schools = data?.schools || [];
  const classes = data?.classes || [];
  const subjects = data?.subjects || [];
  const teachers = data?.teachers || [];
  const students = usersData?.users || [];

  const studentsTotal = useMemo(
    () => classes.reduce((sum, klass) => sum + Number(klass.students_count || 0), 0),
    [classes],
  );

  const afterChange = async (message) => {
    invalidate("/admin");
    await refresh();
    toast(message, "success");
  };

  const openSchool = () => {
    setSchoolForm({ city_id: cities[0] ? String(cities[0].id) : "", name: "", address: "", director: "" });
    setSchoolOpen(true);
  };

  const openClass = () => {
    setClassForm({
      school_id: schools[0] ? String(schools[0].id) : "",
      grade: 1,
      letter: "",
      teacher_id: teachers[0] ? String(teachers[0].id) : "",
      year: "2025/2026",
      title: "",
    });
    setClassOpen(true);
  };

  const submitCity = async () => {
    if (!cityForm.name.trim()) {
      toast("Введите название города", "info");
      return;
    }
    try {
      await run(() => api.post("/admin/cities", cityForm));
      setCityOpen(false);
      setCityForm({ name: "", region: "" });
      await afterChange("Город добавлен");
    } catch (err) {
      toast(err.message || "Не удалось добавить город", "error");
    }
  };

  const submitSchool = async () => {
    if (!schoolForm.city_id || !schoolForm.name.trim()) {
      toast("Нужны город и название школы", "info");
      return;
    }
    try {
      await run(() => api.post("/admin/schools", { ...schoolForm, city_id: Number(schoolForm.city_id) }));
      setSchoolOpen(false);
      await afterChange("Школа добавлена");
    } catch (err) {
      toast(err.message || "Не удалось добавить школу", "error");
    }
  };

  const submitClass = async () => {
    if (!classForm.school_id) {
      toast("Выберите школу", "info");
      return;
    }
    try {
      await run(() => api.post("/admin/classes", {
        ...classForm,
        school_id: Number(classForm.school_id),
        grade: Number(classForm.grade),
        teacher_id: classForm.teacher_id || null,
      }));
      setClassOpen(false);
      await afterChange("Класс создан");
    } catch (err) {
      toast(err.message || "Не удалось создать класс", "error");
    }
  };

  const openClassEdit = (klass) => {
    setEditClass(klass);
    setClassEditForm({
      grade: klass.grade || 1,
      letter: klass.letter || "",
      teacher_id: klass.teacher_id ? String(klass.teacher_id) : "",
      year: klass.year || "2025/2026",
      title: klass.title || "",
    });
  };

  const submitClassEdit = async () => {
    if (!editClass || !classEditForm) return;
    try {
      await run(() => api.patch(`/admin/classes/${editClass.id}`, {
        ...classEditForm,
        grade: Number(classEditForm.grade),
        teacher_id: classEditForm.teacher_id || null,
      }));
      setEditClass(null);
      setClassEditForm(null);
      await afterChange("Класс обновлён");
    } catch (err) {
      toast(err.message || "Не удалось сохранить класс", "error");
    }
  };

  const removeSchool = async (school) => {
    if (!window.confirm(`Удалить школу «${school.name}»? Классы и связи могут быть затронуты.`)) return;
    try {
      await run(() => api.del(`/admin/schools/${school.id}`));
      await afterChange("Школа удалена");
    } catch (err) {
      toast(err.message || "Не удалось удалить школу", "error");
    }
  };

  const removeClass = async (klass) => {
    if (!window.confirm(`Удалить класс ${klass.title}?`)) return;
    try {
      await run(() => api.del(`/admin/classes/${klass.id}`));
      await afterChange("Класс удалён");
    } catch (err) {
      toast(err.message || "Не удалось удалить класс", "error");
    }
  };

  const openAddStudent = (klass) => {
    setAddStudentClass(klass);
    setStudentId("");
  };

  const submitAddStudent = async () => {
    if (!addStudentClass || !studentId) {
      toast("Выберите ученика", "info");
      return;
    }
    try {
      await run(() => api.post(`/admin/classes/${addStudentClass.id}/students`, { student_id: Number(studentId) }));
      setAddStudentClass(null);
      setStudentId("");
      await afterChange("Ученик зачислен в класс");
    } catch (err) {
      toast(err.message || "Не удалось зачислить ученика", "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Организация"
        subtitle="Структура школы: города, школы, классы и предметы. Классы связывают учеников и учителей."
        actions={
          <>
            {tab === "cities" && <Button icon={Plus} onClick={() => { setCityForm({ name: "", region: "" }); setCityOpen(true); }}>Город</Button>}
            {tab === "schools" && <Button icon={Plus} onClick={openSchool}>Школа</Button>}
            {tab === "classes" && <Button icon={Plus} onClick={openClass}>Класс</Button>}
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={MapPin} label="Городов" value={cities.length} tone="iris" />
        <StatCard icon={School} label="Школ" value={schools.length} tone="cyan" />
        <StatCard icon={GraduationCap} label="Классов" value={classes.length} tone="gold" />
        <StatCard icon={Users} label="Учеников в классах" value={studentsTotal} tone="green" />
      </div>

      <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${
              tab === key ? "bg-white/10 text-white" : "text-mist-500 hover:text-white"
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {loading && !data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-36" />)}
        </div>
      ) : (
        <>
          {tab === "cities" && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cities.map((city) => (
                <Card key={city.id} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-iris-400/20 bg-iris-500/10 text-iris-200">
                      <MapPin size={19} />
                    </span>
                    <Badge tone="iris">{schools.filter((school) => Number(school.city_id) === Number(city.id)).length} школ</Badge>
                  </div>
                  <h3 className="mt-4 font-display text-base font-semibold text-white">{city.name}</h3>
                  <p className="mt-1 text-[11px] text-mist-500">{city.region || "регион не указан"}</p>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <MiniStat label="Школы" value={schools.filter((school) => Number(school.city_id) === Number(city.id)).length} />
                    <MiniStat label="Классы" value={classes.filter((klass) => Number(klass.city_id) === Number(city.id)).length} />
                  </div>
                </Card>
              ))}
              {cities.length === 0 && <Card className="sm:col-span-2 lg:col-span-3"><EmptyState icon="🏙" title="Городов нет" text="Добавьте первый город, затем школу." /></Card>}
            </div>
          )}

          {tab === "schools" && (
            <div className="grid gap-3 sm:grid-cols-2">
              {schools.map((school) => (
                <Card key={school.id} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-500/10 text-cyan-200">
                      <School size={19} />
                    </span>
                    <div className="flex items-center gap-1.5">
                      <Badge tone="cyan">{school.classes_count || 0} классов</Badge>
                      <IconButton icon={Trash2} label="Удалить школу" className="text-rose-300" onClick={() => removeSchool(school)} />
                    </div>
                  </div>
                  <h3 className="mt-4 font-display text-base font-semibold text-white">{school.name}</h3>
                  <p className="mt-1 text-[11px] text-mist-500">{school.city_name} · {school.address || "адрес не указан"}</p>
                  <p className="mt-0.5 text-[10px] text-mist-600">Директор: {school.director || "—"}</p>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <MiniStat label="Классы" value={school.classes_count || 0} />
                    <MiniStat label="Ученики" value={school.students_count || 0} />
                  </div>
                </Card>
              ))}
              {schools.length === 0 && <Card className="sm:col-span-2"><EmptyState icon="🏫" title="Школ нет" text="Добавьте школу и привяжите её к городу." action={<Button icon={Plus} onClick={openSchool}>Добавить школу</Button>} /></Card>}
            </div>
          )}

          {tab === "classes" && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {classes.map((klass) => {
                const capacity = Math.max(Number(klass.students_count || 0), 1);
                const fill = Math.min(100, Math.round((Number(klass.students_count || 0) / Math.max(capacity, 25)) * 100));
                return (
                  <Card key={klass.id} className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 font-display text-base font-semibold text-white">
                        {klass.grade}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <Badge tone="iris">{klass.title}</Badge>
                        <IconButton icon={Pencil} label="Изменить класс" onClick={() => openClassEdit(klass)} />
                        <IconButton icon={Trash2} label="Удалить класс" className="text-rose-300" onClick={() => removeClass(klass)} />
                      </div>
                    </div>
                    <h3 className="mt-4 font-display text-base font-semibold text-white">{klass.school_name}</h3>
                    <p className="mt-1 text-[11px] text-mist-500">
                      {klass.city_name} · {klass.year || "—"}
                    </p>
                    <p className="mt-0.5 text-[10px] text-mist-600">
                      Учитель: {klass.teacher_first ? `${klass.teacher_first} ${klass.teacher_last || ""}` : "не назначен"}
                    </p>
                    <div className="mt-4">
                      <div className="mb-1.5 flex items-center justify-between text-[10px] font-bold text-mist-500">
                        <span>Учеников</span>
                        <span>{klass.students_count || 0}</span>
                      </div>
                      <Progress value={fill} />
                    </div>
                    <Button size="sm" variant="ghost" icon={UserPlus} className="mt-4 w-full" onClick={() => openAddStudent(klass)}>
                      Добавить ученика
                    </Button>
                  </Card>
                );
              })}
              {classes.length === 0 && <Card className="sm:col-span-2 lg:col-span-3"><EmptyState icon="🎓" title="Классов нет" text="Создайте класс и назначьте учителя." action={<Button icon={Plus} onClick={openClass}>Создать класс</Button>} /></Card>}
            </div>
          )}

          {tab === "subjects" && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {subjects.map((subject) => (
                <Card key={subject.id} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">{subject.icon || "📘"}</span>
                    <Badge tone={subject.is_active ? "green" : "rose"}>{subject.is_active ? "активен" : "скрыт"}</Badge>
                  </div>
                  <h3 className="mt-4 font-display text-base font-semibold text-white">{subject.name}</h3>
                  <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-mist-500">{subject.description}</p>
                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <MiniStat label="Темы" value={subject.topics_count || 0} />
                    <MiniStat label="Курсы" value={subject.courses_count || 0} />
                    <MiniStat label="Книги" value={subject.textbooks_count || 0} />
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      <Modal
        open={cityOpen}
        onClose={() => setCityOpen(false)}
        title="Новый город"
        footer={<><Button variant="ghost" onClick={() => setCityOpen(false)}>Отмена</Button><Button icon={Check} loading={pending} onClick={submitCity}>Добавить</Button></>}
      >
        <div className="space-y-4">
          <Field label="Название"><Input value={cityForm.name} onChange={(event) => setCityForm((current) => ({ ...current, name: event.target.value }))} placeholder="Минск" autoFocus /></Field>
          <Field label="Регион"><Input value={cityForm.region} onChange={(event) => setCityForm((current) => ({ ...current, region: event.target.value }))} placeholder="Минская область" /></Field>
        </div>
      </Modal>

      <Modal
        open={schoolOpen}
        onClose={() => setSchoolOpen(false)}
        title="Новая школа"
        footer={<><Button variant="ghost" onClick={() => setSchoolOpen(false)}>Отмена</Button><Button icon={Check} loading={pending} onClick={submitSchool}>Добавить</Button></>}
      >
        <div className="space-y-4">
          <Field label="Город">
            <Select value={schoolForm.city_id} onChange={(event) => setSchoolForm((current) => ({ ...current, city_id: event.target.value }))}>
              <option value="">Выберите город</option>
              {cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
            </Select>
          </Field>
          <Field label="Название"><Input value={schoolForm.name} onChange={(event) => setSchoolForm((current) => ({ ...current, name: event.target.value }))} placeholder="Гимназия №1" /></Field>
          <Field label="Адрес"><Input value={schoolForm.address} onChange={(event) => setSchoolForm((current) => ({ ...current, address: event.target.value }))} /></Field>
          <Field label="Директор"><Input value={schoolForm.director} onChange={(event) => setSchoolForm((current) => ({ ...current, director: event.target.value }))} /></Field>
        </div>
      </Modal>

      <Modal
        open={classOpen}
        onClose={() => setClassOpen(false)}
        title="Новый класс"
        size="lg"
        footer={<><Button variant="ghost" onClick={() => setClassOpen(false)}>Отмена</Button><Button icon={Check} loading={pending} onClick={submitClass}>Создать</Button></>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Школа" className="sm:col-span-2">
            <Select value={classForm.school_id} onChange={(event) => setClassForm((current) => ({ ...current, school_id: event.target.value }))}>
              <option value="">Выберите школу</option>
              {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
            </Select>
          </Field>
          <Field label="Класс">
            <Select value={classForm.grade} onChange={(event) => setClassForm((current) => ({ ...current, grade: event.target.value }))}>
              {Array.from({ length: 11 }).map((_, index) => <option key={index + 1} value={index + 1}>{index + 1} класс</option>)}
            </Select>
          </Field>
          <Field label="Литера"><Input value={classForm.letter} onChange={(event) => setClassForm((current) => ({ ...current, letter: event.target.value }))} placeholder="А" maxLength={3} /></Field>
          <Field label="Учитель">
            <Select value={classForm.teacher_id} onChange={(event) => setClassForm((current) => ({ ...current, teacher_id: event.target.value }))}>
              <option value="">Не назначен</option>
              {teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.first_name} {teacher.last_name}</option>)}
            </Select>
          </Field>
          <Field label="Учебный год"><Input value={classForm.year} onChange={(event) => setClassForm((current) => ({ ...current, year: event.target.value }))} /></Field>
          <Field label="Название" hint="Необязательно — соберём автоматически." className="sm:col-span-2">
            <Input value={classForm.title} onChange={(event) => setClassForm((current) => ({ ...current, title: event.target.value }))} placeholder={`${classForm.grade} «${classForm.letter || "А"}»`} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={Boolean(editClass && classEditForm)}
        onClose={() => { setEditClass(null); setClassEditForm(null); }}
        title={editClass ? `Класс ${editClass.title}` : "Класс"}
        footer={<><Button variant="ghost" onClick={() => { setEditClass(null); setClassEditForm(null); }}>Отмена</Button><Button icon={Check} loading={pending} onClick={submitClassEdit}>Сохранить</Button></>}
      >
        {classEditForm && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Класс">
              <Select value={classEditForm.grade} onChange={(event) => setClassEditForm((current) => ({ ...current, grade: event.target.value }))}>
                {Array.from({ length: 11 }).map((_, index) => <option key={index + 1} value={index + 1}>{index + 1} класс</option>)}
              </Select>
            </Field>
            <Field label="Литера"><Input value={classEditForm.letter} onChange={(event) => setClassEditForm((current) => ({ ...current, letter: event.target.value }))} maxLength={3} /></Field>
            <Field label="Учитель">
              <Select value={classEditForm.teacher_id} onChange={(event) => setClassEditForm((current) => ({ ...current, teacher_id: event.target.value }))}>
                <option value="">Не назначен</option>
                {teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.first_name} {teacher.last_name}</option>)}
              </Select>
            </Field>
            <Field label="Год"><Input value={classEditForm.year} onChange={(event) => setClassEditForm((current) => ({ ...current, year: event.target.value }))} /></Field>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(addStudentClass)}
        onClose={() => setAddStudentClass(null)}
        title="Зачислить ученика"
        description={addStudentClass ? `${addStudentClass.school_name} · ${addStudentClass.title}` : ""}
        footer={<><Button variant="ghost" onClick={() => setAddStudentClass(null)}>Отмена</Button><Button icon={UserPlus} loading={pending} onClick={submitAddStudent}>Зачислить</Button></>}
      >
        <Field label="Ученик" hint="Показаны все активные ученики школы.">
          <Select value={studentId} onChange={(event) => setStudentId(event.target.value)}>
            <option value="">Выберите ученика</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.first_name} {student.last_name} · @{student.login}
              </option>
            ))}
          </Select>
        </Field>
      </Modal>
    </div>
  );
}
