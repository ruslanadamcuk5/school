import { Suspense, lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Spinner } from "./components/ui";
import { useSession } from "./lib/hooks";
import Shell from "./components/Shell";
import Landing from "./pages/Landing";
import { LoginPage, RegisterPage } from "./pages/Auth";

/** Ленивая загрузка страниц: первый экран остаётся лёгким. */
const page = (loader, name) =>
  lazy(() => loader().then((module) => ({ default: module[name] })));

const StudentDashboard = page(() => import("./pages/Student"), "default");
const LearnPage = page(() => import("./pages/Learn"), "LearnPage");
const TopicPage = page(() => import("./pages/Learn"), "TopicPage");
const PracticePage = page(() => import("./pages/Practice"), "PracticePage");
const PracticeResult = page(() => import("./pages/Practice"), "PracticeResult");
const AssignmentsPage = page(() => import("./pages/Assignments"), "AssignmentsPage");
const AssignmentPage = page(() => import("./pages/Assignments"), "AssignmentPage");
const LibraryPage = page(() => import("./pages/Library"), "LibraryPage");
const BookPage = page(() => import("./pages/Library"), "BookPage");
const ShopPage = page(() => import("./pages/Shop"), "default");
const PetPage = page(() => import("./pages/Pet"), "default");
const SchedulePage = page(() => import("./pages/Schedule"), "default");
const NotificationsPage = page(() => import("./pages/Notifications"), "default");
const ProfilePage = page(() => import("./pages/Profile"), "default");
const ParentChild = page(() => import("./pages/Parent"), "ParentChild");
const ParentDashboard = page(() => import("./pages/Parent"), "ParentDashboard");
const ParentHelp = page(() => import("./pages/Parent"), "ParentHelp");
const ParentLibrary = page(() => import("./pages/Parent"), "ParentLibrary");
const ParentMap = page(() => import("./pages/Parent"), "ParentMap");
const ParentAssignments = page(() => import("./pages/ParentAssignments"), "ParentAssignmentsPage");
const TeacherAssignments = page(() => import("./pages/Teacher"), "TeacherAssignments");
const TeacherClass = page(() => import("./pages/Teacher"), "TeacherClass");
const TeacherClasses = page(() => import("./pages/Teacher"), "TeacherClasses");
const TeacherDashboard = page(() => import("./pages/Teacher"), "TeacherDashboard");
const TeacherLibrary = page(() => import("./pages/Teacher"), "TeacherLibrary");
const TeacherSchedule = page(() => import("./pages/Teacher"), "TeacherSchedule");
const TeacherStudent = page(() => import("./pages/Teacher"), "TeacherStudent");
const TeacherStudents = page(() => import("./pages/Teacher"), "TeacherStudents");
const AdminAI = page(() => import("./pages/Admin"), "AdminAI");
const AdminAudit = page(() => import("./pages/Admin"), "AdminAudit");
const AdminCourses = page(() => import("./pages/Admin"), "AdminCourses");
const AdminDashboard = page(() => import("./pages/Admin"), "AdminDashboard");
const AdminMap = page(() => import("./pages/Admin"), "AdminMap");
const AdminOrgs = page(() => import("./pages/Admin"), "AdminOrgs");
const AdminPadruchnik = page(() => import("./pages/Admin"), "AdminPadruchnik");
const AdminShop = page(() => import("./pages/Admin"), "AdminShop");
const AdminTextbookDetail = page(() => import("./pages/Admin"), "AdminTextbookDetail");
const AdminTextbooks = page(() => import("./pages/Admin"), "AdminTextbooks");
const AdminTopics = page(() => import("./pages/Admin"), "AdminTopics");
const AdminUserDetail = page(() => import("./pages/Admin"), "AdminUserDetail");
const AdminUsers = page(() => import("./pages/Admin"), "AdminUsers");
const AdminYouTube = page(() => import("./pages/Admin"), "AdminYouTube");

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner label="Открываем кабинет…" />
    </div>
  );
}

function RequireAuth() {
  const { session, ready } = useSession();
  const location = useLocation();
  if (!ready) return <FullScreenLoader />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Shell />;
}

function RequireRole({ roles, children }) {
  const { session } = useSession();
  const role = session?.user?.role;
  if (!roles.includes(role)) {
    const home = {
      student: "/app",
      parent: "/app/parent",
      teacher: "/app/teacher",
      admin: "/app/admin",
    }[role] || "/app";
    return <Navigate to={home} replace />;
  }
  return children;
}

/**
 * Школьная библиотека — раздел ученика. У учителя, родителя и администратора
 * есть собственные библиотеки, поэтому прямой адрес ведёт в подходящий раздел,
 * а не в тупик с ошибкой 403.
 */
function LibraryEntry() {
  const { session } = useSession();
  const target = {
    teacher: "/app/teacher/library",
    parent: "/app/parent/library",
    admin: "/app/admin",
  }[session?.user?.role];
  if (target) return <Navigate to={target} replace />;
  return <LibraryPage />;
}

export default function App() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route path="/app" element={<RequireAuth />}>
        <Route index element={<StudentDashboard />} />

        <Route
          path="learn"
          element={
            <RequireRole roles={["student"]}>
              <LearnPage />
            </RequireRole>
          }
        />
        <Route
          path="learn/:slug"
          element={
            <RequireRole roles={["student"]}>
              <TopicPage />
            </RequireRole>
          }
        />
        <Route
          path="play/:roundId"
          element={
            <RequireRole roles={["student"]}>
              <PracticePage />
            </RequireRole>
          }
        />
        <Route
          path="play/:roundId/result"
          element={
            <RequireRole roles={["student"]}>
              <PracticeResult />
            </RequireRole>
          }
        />

        <Route
          path="assignments"
          element={
            <RequireRole roles={["student"]}>
              <AssignmentsPage />
            </RequireRole>
          }
        />
        <Route path="assignments/:id" element={<AssignmentPage />} />

        <Route path="library" element={<LibraryEntry />} />
        <Route path="library/:id" element={<BookPage />} />

        <Route
          path="shop"
          element={
            <RequireRole roles={["student"]}>
              <ShopPage />
            </RequireRole>
          }
        />
        <Route
          path="pet"
          element={
            <RequireRole roles={["student"]}>
              <PetPage />
            </RequireRole>
          }
        />

        <Route path="schedule" element={<SchedulePage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="profile" element={<ProfilePage />} />

        <Route
          path="parent"
          element={
            <RequireRole roles={["parent"]}>
              <ParentDashboard />
            </RequireRole>
          }
        />
        <Route
          path="parent/children/:learnerId"
          element={
            <RequireRole roles={["parent"]}>
              <ParentChild />
            </RequireRole>
          }
        />
        <Route
          path="parent/map"
          element={
            <RequireRole roles={["parent"]}>
              <ParentMap />
            </RequireRole>
          }
        />
        <Route
          path="parent/help"
          element={
            <RequireRole roles={["parent"]}>
              <ParentHelp />
            </RequireRole>
          }
        />
        <Route
          path="parent/library"
          element={
            <RequireRole roles={["parent"]}>
              <ParentLibrary />
            </RequireRole>
          }
        />
        <Route
          path="parent/assignments"
          element={
            <RequireRole roles={["parent"]}>
              <ParentAssignments />
            </RequireRole>
          }
        />

        <Route
          path="teacher"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherDashboard />
            </RequireRole>
          }
        />
        <Route
          path="teacher/classes"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherClasses />
            </RequireRole>
          }
        />
        <Route
          path="teacher/classes/:classId"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherClass />
            </RequireRole>
          }
        />
        <Route
          path="teacher/students"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherStudents />
            </RequireRole>
          }
        />
        <Route
          path="teacher/students/:studentId"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherStudent />
            </RequireRole>
          }
        />
        <Route
          path="teacher/assignments"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherAssignments />
            </RequireRole>
          }
        />
        <Route
          path="teacher/schedule"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherSchedule />
            </RequireRole>
          }
        />
        <Route
          path="teacher/library"
          element={
            <RequireRole roles={["teacher", "admin"]}>
              <TeacherLibrary />
            </RequireRole>
          }
        />

        <Route
          path="admin"
          element={
            <RequireRole roles={["admin"]}>
              <AdminDashboard />
            </RequireRole>
          }
        />
        <Route
          path="admin/users"
          element={
            <RequireRole roles={["admin"]}>
              <AdminUsers />
            </RequireRole>
          }
        />
        <Route
          path="admin/users/:id"
          element={
            <RequireRole roles={["admin"]}>
              <AdminUserDetail />
            </RequireRole>
          }
        />
        <Route
          path="admin/topics"
          element={
            <RequireRole roles={["admin"]}>
              <AdminTopics />
            </RequireRole>
          }
        />
        <Route
          path="admin/courses"
          element={
            <RequireRole roles={["admin"]}>
              <AdminCourses />
            </RequireRole>
          }
        />
        <Route
          path="admin/textbooks"
          element={
            <RequireRole roles={["admin"]}>
              <AdminTextbooks />
            </RequireRole>
          }
        />
        <Route
          path="admin/textbooks/:id"
          element={
            <RequireRole roles={["admin"]}>
              <AdminTextbookDetail />
            </RequireRole>
          }
        />
        <Route
          path="admin/padruchnik"
          element={
            <RequireRole roles={["admin"]}>
              <AdminPadruchnik />
            </RequireRole>
          }
        />
        <Route
          path="admin/map"
          element={
            <RequireRole roles={["admin"]}>
              <AdminMap />
            </RequireRole>
          }
        />
        <Route
          path="admin/orgs"
          element={
            <RequireRole roles={["admin"]}>
              <AdminOrgs />
            </RequireRole>
          }
        />
        <Route
          path="admin/shop"
          element={
            <RequireRole roles={["admin"]}>
              <AdminShop />
            </RequireRole>
          }
        />
        <Route
          path="admin/youtube"
          element={
            <RequireRole roles={["admin"]}>
              <AdminYouTube />
            </RequireRole>
          }
        />
        <Route
          path="admin/ai"
          element={
            <RequireRole roles={["admin"]}>
              <AdminAI />
            </RequireRole>
          }
        />
        <Route
          path="admin/audit"
          element={
            <RequireRole roles={["admin"]}>
              <AdminAudit />
            </RequireRole>
          }
        />
      </Route>

      <Route
        path="*"
        element={
          <div className="relative z-10 flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
            <p className="font-display text-7xl font-semibold grad-text">404</p>
            <div>
              <h1 className="font-display text-2xl font-semibold text-white">Страница не найдена</h1>
              <p className="mt-2 text-sm text-mist-500">
                Возможно, ссылка устарела или страница была перемещена.
              </p>
            </div>
            <a href="/" className="btn btn-primary">На главную</a>
          </div>
        }
      />
      </Routes>
    </Suspense>
  );
}
