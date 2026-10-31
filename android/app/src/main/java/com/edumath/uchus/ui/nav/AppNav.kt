package com.edumath.uchus.ui.nav

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.location.LocationTrackingService
import com.edumath.uchus.core.appViewModelFactory
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.MetaDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.session.StoredSession
import com.edumath.uchus.ui.about.AboutScreen
import com.edumath.uchus.ui.admin.AdminScreen
import com.edumath.uchus.ui.ai.AiScreen
import com.edumath.uchus.ui.auth.AuthViewModel
import com.edumath.uchus.ui.auth.LoginScreen
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.home.HomeScreen
import com.edumath.uchus.ui.notifications.NotificationsScreen
import com.edumath.uchus.ui.padruchnik.PadruchnikScreen
import com.edumath.uchus.ui.theme.DesignMode
import com.edumath.uchus.ui.theme.UchusTheme
import com.edumath.uchus.ui.parent.ChildDetailScreen
import com.edumath.uchus.ui.parent.ParentCreateAssignmentScreen
import com.edumath.uchus.ui.parent.ParentMapScreen
import com.edumath.uchus.ui.parent.ParentScreen
import com.edumath.uchus.ui.student.AssignmentDetailScreen
import com.edumath.uchus.ui.student.AssignmentsScreen
import com.edumath.uchus.ui.student.LibraryScreen
import com.edumath.uchus.ui.student.MapScreen
import com.edumath.uchus.ui.student.PlayScreen
import com.edumath.uchus.ui.student.ProfileScreen
import com.edumath.uchus.ui.student.QuizScreen
import com.edumath.uchus.ui.student.ReadScreen
import com.edumath.uchus.ui.student.ReaderScreen
import com.edumath.uchus.ui.student.ScheduleScreen
import com.edumath.uchus.ui.student.ShopScreen
import com.edumath.uchus.ui.student.TopicScreen
import com.edumath.uchus.ui.teacher.CreateAssignmentScreen
import com.edumath.uchus.ui.teacher.TeacherClassScreen
import com.edumath.uchus.ui.teacher.TeacherDashboardScreen
import com.edumath.uchus.ui.teacher.TeacherLibraryScreen
import com.edumath.uchus.ui.teacher.TeacherResultsScreen
import com.edumath.uchus.ui.teacher.TeacherScheduleScreen
import com.edumath.uchus.ui.teacher.TeacherStudentScreen
import com.edumath.uchus.ui.teacher.TeacherStudentsScreen
import com.edumath.uchus.ui.location.ChildLocationScreen
import com.edumath.uchus.ui.update.AppUpdateGate
import kotlinx.coroutines.launch

@Composable
fun AppNav(container: AppContainer) {
    val current by container.session.current.collectAsState()
    val loaded by container.session.loaded.collectAsState()

    LaunchedEffect(Unit) { container.session.hydrate() }

    Box(Modifier.fillMaxSize()) {
        when {
            !loaded -> LoadingBox("Проверяем сессию…")

            current == null -> {
                val vm: AuthViewModel = viewModel(factory = appViewModelFactory(container))
                LoginScreen(vm)
            }

            else -> LoggedInNav(container, current!!)
        }

        if (loaded) {
            AppUpdateGate(container)
        }
    }
}

private val homeRoutes = setOf(
    "map",
    "shop",
    "assignments",
    "library",
    "profile",
    "schedule",
    "ai",
    "about",
    "teacher_dashboard",
    "teacher_students",
    "padruchnik",
    "teacher_schedule",
    "parent",
    "parent_map",
    "location",
    "admin/0",
    "admin/1",
    "admin/2",
    "admin/3",
    "admin/4",
    "admin/5",
    "admin/6",
    "admin/7",
    "admin/8",
)

@Composable
private fun LoggedInNav(container: AppContainer, stored: StoredSession) {
    val session: SessionDto? = remember(stored.sessionJson) {
        runCatching { ApiJson.gson.fromJson(stored.sessionJson, SessionDto::class.java) }.getOrNull()
    }
    // Игровой дизайн — только у учеников 1–4 классов; у остальных строгий.
    val designMode = if (session?.theme == "playful") DesignMode.PLAYFUL else DesignMode.STRICT
    val nav = rememberNavController()
    val scope = rememberCoroutineScope()
    var meta by remember(stored.sessionJson) { mutableStateOf<MetaDto?>(null) }
    val context = LocalContext.current
    var permissionAsked by remember(stored.sessionJson) { mutableStateOf(false) }
    val isLearner = session?.learner != null || session?.user?.role == "student"
    val locationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val granted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted && isLearner) {
            LocationTrackingService.start(context)
        }
    }

    LaunchedEffect(stored.sessionJson) {
        meta = runCatching { apiCall { container.api.meta() } }.getOrNull()
        if (isLearner) {
            if (LocationTrackingService.hasPermission(context)) {
                LocationTrackingService.start(context)
            } else if (!permissionAsked) {
                permissionAsked = true
                locationPermission.launch(
                    arrayOf(
                        Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION,
                    )
                )
            }
        } else {
            // Родительский аккаунт не должен передавать свои маршруты:
            // служба могла остаться запущенной после входа ребёнка.
            LocationTrackingService.stop(context)
        }
    }

    val logout: () -> Unit = {
        scope.launch {
            runCatching { apiCall { container.api.logout() } }
            container.session.clear()
            container.cache.clear()
        }
    }

    val back: () -> Unit = { nav.popBackStack() }
    val openBook: (Int, Int) -> Unit = { id, page -> nav.navigate("book/$id/$page") }

    UchusTheme(designMode = designMode) {
    NavHost(
        navController = nav,
        startDestination = "home",
        // Плавные переходы: у младших школьников заметнее, у взрослых — тише.
        enterTransition = {
            fadeIn(tween(if (designMode == DesignMode.PLAYFUL) 220 else 160)) +
                slideInHorizontally(
                    tween(if (designMode == DesignMode.PLAYFUL) 260 else 180)
                ) { it / if (designMode == DesignMode.PLAYFUL) 8 else 20 }
        },
        exitTransition = { fadeOut(tween(120)) },
        popEnterTransition = { fadeIn(tween(160)) },
        popExitTransition = {
            fadeOut(tween(140)) +
                slideOutHorizontally(tween(160)) { it / 16 }
        },
    ) {
        composable("home") {
            HomeScreen(
                container = container,
                session = session,
                serverUrl = stored.baseUrl,
                availableRoutes = homeRoutes,
                aiEnabled = meta?.ai?.enabled == true,
                onOpen = { route -> nav.navigate(route) },
                onOpenAssignment = { id -> nav.navigate("assignment/$id") },
                onOpenNotifications = { nav.navigate("notifications") },
                onLogout = logout,
            )
        }

        composable("notifications") {
            NotificationsScreen(
                container = container,
                onBack = back,
                onOpenAssignment = { id -> nav.navigate("assignment/$id") },
            )
        }

        composable("about") {
            AboutScreen(
                serverUrl = stored.baseUrl,
                api = container.api,
                onBack = back,
            )
        }

        composable("shop") {
            ShopScreen(
                container = container,
                onBack = back,
                onRefreshSession = {
                    runCatching { apiCall { container.api.me() } }.onSuccess { fresh ->
                        container.session.updateSnapshot(ApiJson.gson.toJson(fresh))
                    }
                },
            )
        }

        composable("map") {
            MapScreen(
                container = container,
                onBack = back,
                onTopic = { slug -> nav.navigate("topic/${Uri.encode(slug)}") },
                onDaily = { generator -> nav.navigate("daily/${Uri.encode(generator)}") },
            )
        }

        composable("topic/{slug}") { entry ->
            val slug = Uri.decode(entry.arguments?.getString("slug") ?: "")
            TopicScreen(
                container = container,
                slug = slug,
                onBack = back,
                onPlay = { topic, mode ->
                    nav.navigate("play/${Uri.encode(topic)}/${Uri.encode(mode)}")
                },
                onQuiz = { nav.navigate("quiz/${Uri.encode(it)}") },
                onRead = { nav.navigate("read/${Uri.encode(it)}") },
                onBook = openBook,
                onTopic = { nav.navigate("topic/${Uri.encode(it)}") },
            )
        }

        composable(
            route = "play/{slug}/{mode}",
            arguments = listOf(
                navArgument("slug") { type = NavType.StringType },
                navArgument("mode") { type = NavType.StringType },
            ),
        ) { entry ->
            val slug = Uri.decode(entry.arguments?.getString("slug") ?: "")
            val mode = Uri.decode(entry.arguments?.getString("mode") ?: "practice")
            PlayScreen(
                container = container,
                topicSlug = slug,
                generator = null,
                mode = mode,
                onBack = back,
                playful = (session?.learner?.grade ?: 0) in 1..4,
            )
        }

        composable("daily/{generator}") { entry ->
            val generator = Uri.decode(entry.arguments?.getString("generator") ?: "")
            PlayScreen(
                container = container,
                topicSlug = null,
                generator = generator,
                mode = "daily",
                onBack = back,
                playful = (session?.learner?.grade ?: 0) in 1..4,
            )
        }

        composable("quiz/{slug}") { entry ->
            val slug = Uri.decode(entry.arguments?.getString("slug") ?: "")
            QuizScreen(
                container = container,
                slug = slug,
                onBack = back,
                playful = (session?.learner?.grade ?: 0) in 1..4,
            )
        }

        composable("read/{slug}") { entry ->
            val slug = Uri.decode(entry.arguments?.getString("slug") ?: "")
            ReadScreen(
                container = container,
                slug = slug,
                onBack = back,
                onBook = openBook,
                onQuiz = { nav.navigate("quiz/${Uri.encode(it)}") },
            )
        }

        composable("library") {
            LibraryScreen(
                container = container,
                role = session?.user?.role,
                onBack = back,
                onBook = openBook,
            )
        }

        composable("teacher_library") {
            TeacherLibraryScreen(container, back, openBook)
        }

        composable("padruchnik") {
            PadruchnikScreen(
                container = container,
                isTeacher = session?.user?.role == "teacher",
                onBack = back,
            )
        }

        composable(
            route = "book/{id}/{page}",
            arguments = listOf(
                navArgument("id") { type = NavType.IntType },
                navArgument("page") { type = NavType.IntType },
            ),
        ) { entry ->
            ReaderScreen(
                container = container,
                textbookId = entry.arguments?.getInt("id") ?: 0,
                startPage = entry.arguments?.getInt("page") ?: 1,
                onBack = back,
            )
        }

        composable("assignments") {
            AssignmentsScreen(
                container = container,
                role = session?.user?.role,
                onBack = back,
                onOpen = { nav.navigate("assignment/$it") },
                onResults = { nav.navigate("assignment_results/$it") },
                onCreate = { nav.navigate("create_assignment") },
            )
        }

        composable(
            route = "assignment/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            AssignmentDetailScreen(
                container = container,
                assignmentId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
            )
        }

        composable(
            route = "assignment_results/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            TeacherResultsScreen(
                container = container,
                assignmentId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
            )
        }

        composable("create_assignment") {
            CreateAssignmentScreen(
                container = container,
                onBack = back,
                onCreated = back,
            )
        }

        composable("profile") {
            ProfileScreen(
                container = container,
                session = session,
                serverUrl = stored.baseUrl,
                onBack = back,
                onLogout = logout,
                onAbout = { nav.navigate("about") },
                onSchedule = { nav.navigate("schedule") },
                onShop = { nav.navigate("shop") },
            )
        }

        composable("schedule") {
            ScheduleScreen(container, back)
        }

        composable("ai") {
            AiScreen(container, back)
        }

        composable("teacher_dashboard") {
            TeacherDashboardScreen(
                container = container,
                onBack = back,
                onClass = { nav.navigate("teacher_class/$it") },
                onStudent = { nav.navigate("teacher_student/$it") },
                onAssignments = { nav.navigate("assignments") },
            )
        }

        composable(
            route = "teacher_class/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            TeacherClassScreen(
                container = container,
                classId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
                onStudent = { nav.navigate("teacher_student/$it") },
            )
        }

        composable("teacher_students") {
            TeacherStudentsScreen(
                container = container,
                onBack = back,
                onStudent = { nav.navigate("teacher_student/$it") },
            )
        }

        composable(
            route = "teacher_student/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            TeacherStudentScreen(
                container = container,
                studentId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
            )
        }

        composable("teacher_schedule") {
            TeacherScheduleScreen(container, back)
        }

        composable("parent") {
            ParentScreen(
                container = container,
                onBack = back,
                onChild = { nav.navigate("parent_child/$it") },
                onAssignments = { nav.navigate("assignments") },
                onLibrary = { nav.navigate("library") },
                onCreate = { nav.navigate("parent_create_assignment") },
                onMap = { nav.navigate("parent_map") },
            )
        }

        composable("parent_map") {
            ParentMapScreen(
                container = container,
                learnerId = 0,
                onBack = back,
            )
        }

        composable(
            route = "parent_map/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            ParentMapScreen(
                container = container,
                learnerId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
            )
        }

        composable("location") {
            ChildLocationScreen(container = container, onBack = back)
        }

        composable(
            route = "parent_child/{id}",
            arguments = listOf(navArgument("id") { type = NavType.IntType }),
        ) { entry ->
            ChildDetailScreen(
                container = container,
                learnerId = entry.arguments?.getInt("id") ?: 0,
                onBack = back,
                onMap = { nav.navigate("parent_map/${entry.arguments?.getInt("id") ?: 0}") },
            )
        }

        composable("parent_create_assignment") {
            ParentCreateAssignmentScreen(
                container = container,
                onBack = back,
                onCreated = back,
            )
        }

        composable(
            route = "admin/{tab}",
            arguments = listOf(navArgument("tab") { type = NavType.IntType }),
        ) { entry ->
            AdminScreen(
                container = container,
                onBack = back,
                initialTab = entry.arguments?.getInt("tab") ?: 0,
            )
        }
    }
    }
}
