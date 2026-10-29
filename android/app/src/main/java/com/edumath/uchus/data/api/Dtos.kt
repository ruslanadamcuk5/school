package com.edumath.uchus.data.api

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName

// ------------------------------------------------------------------ общие

data class ApiErrorDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("error") val error: String? = null,
    @SerializedName("message") val message: String? = null,
)

data class SimpleOkDto(
    @SerializedName("ok") val ok: Boolean = false,
)

data class IdDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("id") val id: Int = 0,
    @SerializedName("slug") val slug: String? = null,
)

data class HealthDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("status") val status: String? = null,
    @SerializedName("db") val db: Boolean = false,
    @SerializedName("api") val api: Int = 0,
    @SerializedName("time") val time: String? = null,
)

data class AppVersionDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("version_code") val versionCode: Int = 0,
    @SerializedName("version_name") val versionName: String? = null,
    @SerializedName("download_url") val downloadUrl: String? = null,
    @SerializedName("size") val size: Long = 0,
    @SerializedName("sha256") val sha256: String? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("published_at") val publishedAt: String? = null,
)

// ------------------------------------------------------------------ люди

data class UserDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("login") val login: String? = null,
    @SerializedName("role") val role: String? = null,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("avatar") val avatar: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("city_id") val cityId: Int? = null,
    @SerializedName("school_id") val schoolId: Int? = null,
    @SerializedName(
        value = "is_active",
        alternate = ["is_Active", "isActive"],
    ) val isActive: Boolean = true,
    @SerializedName("city_name") val cityName: String? = null,
    @SerializedName("school_name") val schoolName: String? = null,
    @SerializedName("child_code") val childCode: String? = null,
) {
    val displayName: String
        get() = listOfNotNull(firstName, lastName).filter { it.isNotBlank() }
            .joinToString(" ").ifBlank { login ?: "Пользователь" }
}

data class LearnerDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("name") val name: String? = null,
    @SerializedName("avatar") val avatar: String? = null,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("streak_days") val streakDays: Int = 0,
    @SerializedName("has_pin") val hasPin: Boolean = false,
) {
    val displayName: String get() = name ?: "Ученик"
    val emoji: String get() = avatar ?: "🦊"
}

data class SessionDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("token") val token: String? = null,
    @SerializedName("user") val user: UserDto? = null,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("theme") val theme: String? = null,
)

data class LearnersDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("learners") val learners: List<LearnerDto> = emptyList(),
)

data class LoginRequest(
    @SerializedName("login") val login: String,
    @SerializedName("password") val password: String,
)

// ---------------------------------------------------------- вход через Google

data class GoogleLoginRequest(
    @SerializedName("id_token") val idToken: String,
    @SerializedName("nonce") val nonce: String,
)

/**
 * Ответ сервера на вход по Google ID token.
 *
 * Либо сразу сессия (``token`` + пользователь), либо просьба завершить
 * регистрацию: ``needsSignup`` и подписанный ``signupToken``.
 */
data class GoogleLoginResponse(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("token") val token: String? = null,
    @SerializedName("user") val user: UserDto? = null,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("theme") val theme: String? = null,
    @SerializedName("needs_signup") val needsSignup: Boolean = false,
    @SerializedName("signup_token") val signupToken: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("picture") val picture: String? = null,
    @SerializedName("suggested_login") val suggestedLogin: String? = null,
) {
    fun toSession(): SessionDto = SessionDto(
        ok = ok,
        token = token,
        user = user,
        learner = learner,
        theme = theme,
    )
}

data class GoogleFinishRequest(
    @SerializedName("signup_token") val signupToken: String,
    @SerializedName("role") val role: String,
    @SerializedName("login") val login: String,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("avatar") val avatar: String? = null,
    @SerializedName("child_code") val childCode: String? = null,
)

/** Обмен одноразового кода из браузера на токен (PKCE). */
data class GoogleExchangeRequest(
    @SerializedName("code") val code: String,
    @SerializedName("verifier") val verifier: String,
)

data class LearnerLoginRequest(
    @SerializedName("pin") val pin: String? = null,
)

data class CreateLearnerRequest(
    @SerializedName("name") val name: String,
    @SerializedName("avatar") val avatar: String,
    @SerializedName("grade") val grade: Int,
    @SerializedName("pin") val pin: String?,
)

// ------------------------------------------------------------------ метаданные

data class AppInfoDto(
    @SerializedName("name") val name: String? = null,
    @SerializedName("version") val version: String? = null,
)

data class AiStatusDto(
    @SerializedName("enabled") val enabled: Boolean = false,
    @SerializedName("provider") val provider: String? = null,
    @SerializedName("provider_name") val providerName: String? = null,
    @SerializedName("model") val model: String? = null,
)

data class SubjectDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("slug") val slug: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("color") val color: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("topics_count") val topicsCount: Int = 0,
)

data class MetaDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("app") val app: AppInfoDto? = null,
    @SerializedName("grades") val grades: List<Int> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
    @SerializedName("ai") val ai: AiStatusDto? = null,
)

data class AiStatusResponseDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("ai") val ai: AiStatusDto? = null,
)

data class TopicCatalogDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("topics") val topics: List<AdminTopicDto> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
)

// ------------------------------------------------------------------ карта тем

data class StatsDto(
    @SerializedName("level") val level: Int = 1,
    @SerializedName("level_title") val levelTitle: String? = null,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("total_attempts") val totalAttempts: Int = 0,
    @SerializedName("total_correct") val totalCorrect: Int = 0,
    @SerializedName("accuracy") val accuracy: Int = 0,
    @SerializedName("streak_days") val streakDays: Int = 0,
)

data class BookLinkDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("pages") val pages: Int = 0,
    @SerializedName("page") val page: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
)

data class TopicCardDto(
    @SerializedName("slug") val slug: String = "",
    @SerializedName("title") val title: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("part") val part: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("min_level") val minLevel: Int = 0,
    @SerializedName("page_start") val pageStart: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("source") val source: String? = null,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("correct") val correct: Int = 0,
    @SerializedName("accuracy") val accuracy: Int = 0,
    @SerializedName("boss_cleared") val bossCleared: Boolean = false,
    @SerializedName("methods_total") val methodsTotal: Int = 0,
    @SerializedName("methods_mastered") val methodsMastered: Int = 0,
    @SerializedName("read") val read: Boolean = false,
    @SerializedName("books_count") val booksCount: Int = 0,
    @SerializedName("books") val books: List<BookLinkDto> = emptyList(),
) {
    val displayTitle: String get() = title ?: slug
    val emoji: String get() = icon ?: "⭐"
}

data class DailyItemDto(
    @SerializedName("generator") val generator: String = "",
    @SerializedName("topic") val topic: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("label") val label: String? = null,
    @SerializedName("done") val done: Boolean = false,
    @SerializedName("correct") val correct: Boolean? = null,
)

data class MapDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("subject") val subject: SubjectDto? = null,
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
    @SerializedName("topics") val topics: List<TopicCardDto> = emptyList(),
    @SerializedName("daily") val daily: List<DailyItemDto> = emptyList(),
    @SerializedName("daily_done") val dailyDone: Boolean = false,
    @SerializedName("stats") val stats: StatsDto? = null,
)

// ------------------------------------------------------------------ тема

data class MethodStepDto(
    @SerializedName("title") val title: String? = null,
    @SerializedName("text") val text: String? = null,
)

data class MethodDto(
    @SerializedName("slug") val slug: String = "",
    @SerializedName("name") val name: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("explanation") val explanation: String? = null,
    @SerializedName("steps") val steps: List<MethodStepDto> = emptyList(),
    @SerializedName("mastered") val mastered: Boolean = false,
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("correct") val correct: Int = 0,
)

data class TopicDetailDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("methods") val methods: List<MethodDto> = emptyList(),
    @SerializedName("books") val books: List<BookLinkDto> = emptyList(),
    @SerializedName("previous") val previous: TopicCardDto? = null,
    @SerializedName("next") val next: TopicCardDto? = null,
    @SerializedName("can_play") val canPlay: Boolean = false,
    @SerializedName("can_quiz") val canQuiz: Boolean = false,
    @SerializedName("can_read") val canRead: Boolean = false,
)

data class PageTextDto(
    @SerializedName("page") val page: Int = 0,
    @SerializedName("text") val text: String = "",
)

data class TopicTextDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("pages") val pages: List<PageTextDto> = emptyList(),
)

// ------------------------------------------------------------------ тест по теме

data class QuizQuestionDto(
    @SerializedName("index") val index: Int = 0,
    @SerializedName("question") val question: String = "",
    @SerializedName("choices") val choices: List<String> = emptyList(),
    @SerializedName("answer_type") val answerType: String? = null,
)

data class QuizStartDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("quiz_id") val quizId: Int = 0,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("questions") val questions: List<QuizQuestionDto> = emptyList(),
)

data class QuizSubmitRequest(
    @SerializedName("quiz_id") val quizId: Int,
    @SerializedName("answers") val answers: List<String>,
)

data class StepResultDto(
    @SerializedName("index") val index: Int = 0,
    @SerializedName("question") val question: String = "",
    @SerializedName("given") val given: String = "",
    @SerializedName("expected") val expected: String = "",
    @SerializedName("answer") val answer: String? = null,
    @SerializedName("correct") val correct: Boolean = false,
    @SerializedName("solution") val solution: String? = null,
    @SerializedName("task_type") val taskType: String? = null,
    @SerializedName("ai_comment") val aiComment: String? = null,
)

data class QuizResultDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("correct") val correct: Int = 0,
    @SerializedName("total") val total: Int = 0,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("results") val results: List<StepResultDto> = emptyList(),
    @SerializedName("badges") val badges: List<BadgeDto> = emptyList(),
)

// ------------------------------------------------------------------ игра

data class MethodRefDto(
    @SerializedName("slug") val slug: String? = null,
    @SerializedName("name") val name: String? = null,
)

data class TaskDto(
    @SerializedName("question") val question: String = "",
    @SerializedName("answer_type") val answerType: String? = null,
    @SerializedName("choices") val choices: List<String> = emptyList(),
    @SerializedName("widget") val widget: JsonElement? = null,
    @SerializedName("difficulty") val difficulty: Int = 1,
    @SerializedName("generator") val generator: String? = null,
    @SerializedName("index") val index: Int = 0,
    @SerializedName("total") val total: Int = 0,
    @SerializedName("method") val method: MethodRefDto? = null,
    @SerializedName("methods") val methods: List<MethodRefDto> = emptyList(),
    @SerializedName("hints_left") val hintsLeft: Int = 0,
    @SerializedName("can_switch_method") val canSwitchMethod: Boolean = false,
)

data class RoundStateDto(
    @SerializedName("correct") val correct: Int = 0,
    @SerializedName("answered") val answered: Int = 0,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("combo") val combo: Int = 0,
    @SerializedName("max_combo") val maxCombo: Int = 0,
    @SerializedName("index") val index: Int = 0,
    @SerializedName("total") val total: Int = 0,
    @SerializedName("mode") val mode: String? = null,
)

data class PlayStartRequest(
    @SerializedName("topic_slug") val topicSlug: String,
    @SerializedName("mode") val mode: String? = null,
    @SerializedName("method") val method: String? = null,
)

data class PlayStartDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("round_id") val roundId: Int = 0,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("task") val task: TaskDto? = null,
    @SerializedName("state") val state: RoundStateDto? = null,
    @SerializedName("done") val done: Boolean = false,
)

data class PlayRoundDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("round_id") val roundId: Int = 0,
    @SerializedName("done") val done: Boolean = false,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("task") val task: TaskDto? = null,
    @SerializedName("state") val state: RoundStateDto? = null,
)

data class AnswerRequest(
    @SerializedName("answer") val answer: String,
)

data class BadgeDto(
    @SerializedName("key") val key: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("description") val description: String? = null,
)

data class AnswerDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("correct") val correct: Boolean = false,
    @SerializedName("retry") val retry: Boolean = false,
    @SerializedName("correct_answer") val correctAnswer: String? = null,
    @SerializedName("solution") val solution: String? = null,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("combo") val combo: Int = 0,
    @SerializedName("hints_used") val hintsUsed: Int = 0,
    @SerializedName("hint") val hint: String? = null,
    @SerializedName("method_switched") val methodSwitched: Boolean = false,
    @SerializedName("method") val method: String? = null,
    @SerializedName("done") val done: Boolean = false,
    @SerializedName("badges") val badges: List<BadgeDto> = emptyList(),
    @SerializedName("state") val state: RoundStateDto? = null,
)

data class HintDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("hint") val hint: String? = null,
    @SerializedName("left") val left: Int = 0,
)

data class SwitchMethodDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("method") val method: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("explanation") val explanation: String? = null,
)

data class ResultItemDto(
    @SerializedName("question") val question: String = "",
    @SerializedName("correct") val correct: Boolean = false,
    @SerializedName("given") val given: String? = null,
    @SerializedName("answer") val answer: String? = null,
    @SerializedName("solution") val solution: String? = null,
)

data class PlayResultDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("correct") val correct: Int = 0,
    @SerializedName("total") val total: Int = 0,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("max_combo") val maxCombo: Int = 0,
    @SerializedName("mode") val mode: String? = null,
    @SerializedName("items") val items: List<ResultItemDto> = emptyList(),
    @SerializedName("badges") val badges: List<BadgeDto> = emptyList(),
)

data class DailyDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("tasks") val tasks: List<DailyItemDto> = emptyList(),
    @SerializedName("done") val done: Boolean = false,
)

data class DailyStartRequest(
    @SerializedName("generator") val generator: String? = null,
)

// ------------------------------------------------------------------ работы

data class ResultSummaryDto(
    @SerializedName("score") val score: Int = 0,
    @SerializedName("max_score") val maxScore: Int = 0,
    @SerializedName("percent") val percent: Int = 0,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("completed_at") val completedAt: String? = null,
    @SerializedName("duration_sec") val durationSec: Int = 0,
    @SerializedName("submission_type") val submissionType: String? = null,
    @SerializedName("ai_status") val aiStatus: String? = null,
    @SerializedName("ai_feedback") val aiFeedback: String? = null,
    @SerializedName("ai_model") val aiModel: String? = null,
    @SerializedName("ai_score") val aiScore: Int? = null,
    @SerializedName("photos") val photos: List<String> = emptyList(),
)

data class AssignmentDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("task_type") val taskType: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("course_id") val courseId: Int? = null,
    @SerializedName("subject_id") val subjectId: Int? = null,
    @SerializedName("class_id") val classId: Int? = null,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("author_role") val authorRole: String? = null,
    @SerializedName("author_label") val authorLabel: String? = null,
    @SerializedName("author_name") val authorName: String? = null,
    @SerializedName("student_id") val studentId: Int? = null,
    @SerializedName("topic_slugs") val topicSlugs: String? = null,
    @SerializedName("questions_count") val questionsCount: Int = 0,
    @SerializedName("allow_photo") val allowPhoto: Boolean = true,
    @SerializedName("allow_text") val allowText: Boolean = true,
    @SerializedName("time_limit") val timeLimit: Int = 0,
    @SerializedName("due_date") val dueDate: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("published_at") val publishedAt: String? = null,
    @SerializedName("result") val result: ResultSummaryDto? = null,
    @SerializedName("results") val results: List<ChildResultDto> = emptyList(),
    @SerializedName("overdue") val overdue: Boolean = false,
    @SerializedName("missed") val missed: Boolean = false,
) {
    val displayTitle: String get() = title ?: "Работа"
    val authorDisplay: String
        get() {
            val label = authorLabel ?: when (authorRole) {
                "parent" -> "родителя"
                "admin" -> "администратора"
                else -> "учителя"
            }
            val name = authorName?.takeIf { it.isNotBlank() }
            return if (name != null) "от $label $name" else "от $label"
        }
    val isPending: Boolean get() = status == "опубликована" && result == null
}

data class QuestionDto(
    @SerializedName("index") val index: Int = 0,
    @SerializedName("question") val question: String = "",
    @SerializedName("answer_type") val answerType: String? = null,
    @SerializedName("task_type") val taskType: String? = null,
    @SerializedName("choices") val choices: List<String> = emptyList(),
    @SerializedName("points") val points: Int = 1,
    @SerializedName("audio_text") val audioText: String? = null,
    @SerializedName("content_text") val contentText: String? = null,
    @SerializedName("topic_slug") val topicSlug: String? = null,
)

data class AssignmentsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("assignments") val assignments: List<AssignmentDto> = emptyList(),
)

data class NotificationDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("body") val body: String? = null,
    @SerializedName("assignment_id") val assignmentId: Int = 0,
    @SerializedName("student_id") val studentId: Int = 0,
    @SerializedName("is_read") val isRead: Boolean = false,
    @SerializedName("created_at") val createdAt: String? = null,
)

data class NotificationsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("unread") val unread: Int = 0,
    @SerializedName("notifications") val notifications: List<NotificationDto> = emptyList(),
)

data class AssignmentDetailDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("assignment") val assignment: AssignmentDto? = null,
    @SerializedName("submitted") val submitted: Boolean = false,
    @SerializedName("result") val result: ResultSummaryDto? = null,
    @SerializedName("details") val details: List<StepResultDto> = emptyList(),
    @SerializedName("questions") val questions: List<QuestionDto> = emptyList(),
)

data class SubmitRequest(
    @SerializedName("answers") val answers: List<String>,
    @SerializedName("duration_sec") val durationSec: Int = 0,
)

data class SubmitResponse(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("score") val score: Int = 0,
    @SerializedName("max_score") val maxScore: Int = 0,
    @SerializedName("result") val result: ResultSummaryDto? = null,
    @SerializedName("details") val details: List<StepResultDto> = emptyList(),
)

data class CreateAssignmentRequest(
    @SerializedName("title") val title: String,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("task_type") val taskType: String? = null,
    @SerializedName("reference_text") val referenceText: String? = null,
    @SerializedName("audio_text") val audioText: String? = null,
    @SerializedName("allow_photo") val allowPhoto: Boolean = true,
    @SerializedName("allow_text") val allowText: Boolean = true,
    @SerializedName("class_id") val classId: Int? = null,
    @SerializedName("student_id") val studentId: Int? = null,
    @SerializedName("subject_id") val subjectId: Int? = null,
    @SerializedName("topic_slugs") val topicSlugs: List<String>,
    @SerializedName("questions_count") val questionsCount: Int = 10,
    @SerializedName("time_limit") val timeLimit: Int = 0,
    @SerializedName("due_date") val dueDate: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("child_ids") val childIds: List<Int>? = null,
)

data class CreateAssignmentResponse(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("assignment") val assignment: AssignmentDto? = null,
    @SerializedName("created") val created: Int = 0,
)

// ------------------------------------------------------------------ библиотека

data class LibraryBookDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("owner_id") val ownerId: Int = 0,
    @SerializedName("textbook_id") val textbookId: Int = 0,
    @SerializedName("subject_id") val subjectId: Int? = null,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("pages") val pages: Int = 0,
    @SerializedName("topics_count") val topicsCount: Int = 0,
    @SerializedName("classes_count") val classesCount: Int = 0,
    @SerializedName("subject_name") val subjectName: String? = null,
    @SerializedName("subject_icon") val subjectIcon: String? = null,
    @SerializedName("owner_name") val ownerName: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("class_ids") val classIds: List<Int> = emptyList(),
) {
    val displayTitle: String get() = title ?: "Книга"
}

data class RecommendationDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("teacher_id") val teacherId: Int = 0,
    @SerializedName("book_id") val bookId: Int = 0,
    @SerializedName("topic_slug") val topicSlug: String? = null,
    @SerializedName("target_kind") val targetKind: String? = null,
    @SerializedName("student_id") val studentId: Int? = null,
    @SerializedName("class_id") val classId: Int? = null,
    @SerializedName("note") val note: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("textbook_id") val textbookId: Int? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("pages") val pages: Int? = null,
    @SerializedName("topic_title") val topicTitle: String? = null,
    @SerializedName("topic_icon") val topicIcon: String? = null,
    @SerializedName("page") val page: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
    @SerializedName("teacher_first") val teacherFirst: String? = null,
    @SerializedName("teacher_last") val teacherLast: String? = null,
    @SerializedName("student_first") val studentFirst: String? = null,
    @SerializedName("student_last") val studentLast: String? = null,
    @SerializedName("class_grade") val classGrade: Int? = null,
    @SerializedName("class_letter") val classLetter: String? = null,
    @SerializedName("done") val done: Int = 0,
    @SerializedName("done_count") val doneCount: Int = 0,
    @SerializedName("total_count") val totalCount: Int = 0,
)

data class LibraryStatsDto(
    @SerializedName("books") val books: Int = 0,
    @SerializedName("active") val active: Int = 0,
    @SerializedName("done") val done: Int = 0,
)

data class LibraryDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("books") val books: List<LibraryBookDto> = emptyList(),
    @SerializedName("recommendations") val recommendations: List<RecommendationDto> = emptyList(),
    @SerializedName("stats") val stats: LibraryStatsDto = LibraryStatsDto(),
    @SerializedName("children") val children: List<UserDto>? = null,
    @SerializedName("child") val child: UserDto? = null,
)

data class BookTopicDto(
    @SerializedName("topic_slug") val topicSlug: String = "",
    @SerializedName("title") val title: String? = null,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("page") val page: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
)

data class BookInfoDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("book") val book: LibraryBookDto? = null,
    @SerializedName("topics") val topics: List<BookTopicDto> = emptyList(),
    @SerializedName("recommendations") val recommendations: List<RecommendationDto> = emptyList(),
    @SerializedName("manageable") val manageable: Boolean = false,
)

data class RecommendRequest(
    @SerializedName("topic_slug") val topicSlug: String? = null,
    @SerializedName("class_ids") val classIds: List<Int> = emptyList(),
    @SerializedName("student_ids") val studentIds: List<Int> = emptyList(),
    @SerializedName("note") val note: String? = null,
)

data class TeacherRecommendationsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("recommendations") val recommendations: List<RecommendationDto> = emptyList(),
)

data class TeacherLibraryStatsDto(
    @SerializedName("books") val books: Int = 0,
    @SerializedName("classes") val classes: Int = 0,
    @SerializedName("recommendations") val recommendations: Int = 0,
)

data class TeacherLibraryDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("books") val books: List<LibraryBookDto> = emptyList(),
    @SerializedName("stats") val stats: TeacherLibraryStatsDto = TeacherLibraryStatsDto(),
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("students") val students: List<StudentCardDto> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
)

data class RecommendTopicDto(
    @SerializedName("slug") val slug: String = "",
    @SerializedName("title") val title: String? = null,
    @SerializedName("page") val page: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
)

data class RecommendTextbookDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("subject_id") val subjectId: Int? = null,
    @SerializedName("subject_name") val subjectName: String? = null,
    @SerializedName("subject_icon") val subjectIcon: String? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("book_id") val bookId: Int? = null,
    @SerializedName("topics") val topics: List<RecommendTopicDto> = emptyList(),
)

data class RecommendTopicsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("textbooks") val textbooks: List<RecommendTextbookDto> = emptyList(),
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("students") val students: List<StudentCardDto> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
)

data class RecommendTextbookRequest(
    @SerializedName("textbook_id") val textbookId: Int,
    @SerializedName("topic_slug") val topicSlug: String? = null,
    @SerializedName("class_ids") val classIds: List<Int> = emptyList(),
    @SerializedName("student_ids") val studentIds: List<Int> = emptyList(),
    @SerializedName("note") val note: String? = null,
)

// ------------------------------------------------------------------ учитель

data class TeacherStatsDto(
    @SerializedName("classes") val classes: Int = 0,
    @SerializedName("students") val students: Int = 0,
    @SerializedName("assignments") val assignments: Int = 0,
    @SerializedName("open_assignments") val openAssignments: Int = 0,
    @SerializedName("books") val books: Int = 0,
    @SerializedName("recommendations") val recommendations: Int = 0,
)

data class ClassDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("school_id") val schoolId: Int = 0,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("letter") val letter: String? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("year") val year: String? = null,
    @SerializedName("students_count") val studentsCount: Int = 0,
    @SerializedName("school_name") val schoolName: String? = null,
    @SerializedName("city_name") val cityName: String? = null,
) {
    val displayTitle: String
        get() = title?.takeIf { it.isNotBlank() }
            ?: ("$grade" + (letter ?: "") + " класс")
}

data class StudentCardDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("login") val login: String? = null,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("class_id") val classId: Int? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("letter") val letter: String? = null,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("stats") val stats: StatsDto? = null,
) {
    val displayName: String
        get() = listOfNotNull(firstName, lastName).filter { it.isNotBlank() }
            .joinToString(" ").ifBlank { login ?: "Ученик" }
}

data class TeacherDashboardDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("stats") val stats: TeacherStatsDto = TeacherStatsDto(),
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("recent_assignments") val recentAssignments: List<AssignmentDto> = emptyList(),
    @SerializedName("students") val students: List<StudentCardDto> = emptyList(),
)

data class ClassesDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
)

data class TeacherStudentsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("students") val students: List<StudentCardDto> = emptyList(),
)

data class ScheduleItemDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("class_id") val classId: Int = 0,
    @SerializedName("subject_id") val subjectId: Int? = null,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("weekday") val weekday: Int = 0,
    @SerializedName("lesson_no") val lessonNo: Int = 0,
    @SerializedName("time_start") val timeStart: String? = null,
    @SerializedName("time_end") val timeEnd: String? = null,
    @SerializedName("topic_slug") val topicSlug: String? = null,
    @SerializedName("note") val note: String? = null,
    @SerializedName("subject_name") val subjectName: String? = null,
    @SerializedName("subject_icon") val subjectIcon: String? = null,
    @SerializedName("topic_title") val topicTitle: String? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("letter") val letter: String? = null,
)

data class ScheduleDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("class_id") val classId: Int? = null,
    @SerializedName("weekdays") val weekdays: List<String> = emptyList(),
    @SerializedName("schedule") val schedule: List<ScheduleItemDto> = emptyList(),
)

data class ClassDetailDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("class") val klass: ClassDto? = null,
    @SerializedName("students") val students: List<StudentCardDto> = emptyList(),
    @SerializedName("assignments") val assignments: List<AssignmentDto> = emptyList(),
    @SerializedName("schedule") val schedule: List<ScheduleItemDto> = emptyList(),
)

data class TopicProgressDto(
    @SerializedName("slug") val slug: String = "",
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("correct") val correct: Int = 0,
    @SerializedName("boss_cleared") val bossCleared: Boolean = false,
)

data class DayActivityDto(
    @SerializedName("day") val day: String = "",
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("correct") val correct: Int = 0,
)

data class StudentResultDto(
    @SerializedName("assignment_id") val assignmentId: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("score") val score: Int = 0,
    @SerializedName("max_score") val maxScore: Int = 0,
    @SerializedName("completed_at") val completedAt: String? = null,
)

data class StudentDetailDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("student") val student: UserDto? = null,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("stats") val stats: StatsDto? = null,
    @SerializedName("topics") val topics: List<TopicProgressDto> = emptyList(),
    @SerializedName("weekly") val weekly: List<DayActivityDto> = emptyList(),
    @SerializedName("results") val results: List<StudentResultDto> = emptyList(),
)

// ------------------------------------------------------------------ родитель

data class ChildStatsDto(
    @SerializedName("level") val level: Int = 1,
    @SerializedName("xp") val xp: Int = 0,
    @SerializedName("coins") val coins: Int = 0,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("accuracy") val accuracy: Int = 0,
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("streak_days") val streakDays: Int = 0,
    @SerializedName("daily_done") val dailyDone: Int = 0,
)

data class ChildDto(
    @SerializedName("user") val user: UserDto? = null,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("stats") val stats: ChildStatsDto? = null,
) {
    val displayName: String get() = learner?.displayName ?: user?.displayName ?: "Ребёнок"
    val emoji: String get() = learner?.emoji ?: "🧒"
}

data class ParentStatsDto(
    @SerializedName("children") val children: Int = 0,
    @SerializedName("stars") val stars: Int = 0,
    @SerializedName("attempts") val attempts: Int = 0,
)

data class ParentDashboardDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("children") val children: List<ChildDto> = emptyList(),
    @SerializedName("stats") val stats: ParentStatsDto = ParentStatsDto(),
)

data class ChildrenDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("children") val children: List<ChildDto> = emptyList(),
)

data class ChildResultDto(
    @SerializedName("assignment_id") val assignmentId: Int = 0,
    @SerializedName("student_id") val studentId: Int? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("score") val score: Int = 0,
    @SerializedName("max_score") val maxScore: Int = 0,
    @SerializedName("completed_at") val completedAt: String? = null,
)

data class TeacherResultRowDto(
    @SerializedName("student") val student: UserDto? = null,
    @SerializedName("result") val result: ResultSummaryDto? = null,
    @SerializedName("percent") val percent: Int = 0,
    @SerializedName("grade") val grade: Int = 0,
)

data class TeacherResultsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("assignment") val assignment: AssignmentDto? = null,
    @SerializedName("results") val results: List<TeacherResultRowDto> = emptyList(),
)

data class ChildDetailDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("learner") val learner: LearnerDto? = null,
    @SerializedName("user") val user: UserDto? = null,
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("stats") val stats: StatsDto? = null,
    @SerializedName("topics") val topics: List<TopicProgressDto> = emptyList(),
    @SerializedName("weekly") val weekly: List<DayActivityDto> = emptyList(),
    @SerializedName("results") val results: List<ChildResultDto> = emptyList(),
)

data class UpdateChildRequest(
    @SerializedName("name") val name: String? = null,
    @SerializedName("avatar") val avatar: String? = null,
    @SerializedName("grade") val grade: Int? = null,
    @SerializedName("sound_on") val soundOn: Boolean? = null,
    @SerializedName("voice_on") val voiceOn: Boolean? = null,
    @SerializedName("daily_limit") val dailyLimit: Int? = null,
)

data class ChildResponseDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("learner") val learner: LearnerDto? = null,
)

data class LinkChildResponseDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("child") val child: UserDto? = null,
    @SerializedName("children") val children: List<ChildDto> = emptyList(),
)

// ------------------------------------------------------------------ админ

data class AdminCountersDto(
    @SerializedName("users") val users: Int = 0,
    @SerializedName("students") val students: Int = 0,
    @SerializedName("teachers") val teachers: Int = 0,
    @SerializedName("parents") val parents: Int = 0,
    @SerializedName("admins") val admins: Int = 0,
    @SerializedName("cities") val cities: Int = 0,
    @SerializedName("schools") val schools: Int = 0,
    @SerializedName("classes") val classes: Int = 0,
    @SerializedName("topics") val topics: Int = 0,
    @SerializedName("textbooks") val textbooks: Int = 0,
    @SerializedName("library_books") val libraryBooks: Int = 0,
    @SerializedName("assignments") val assignments: Int = 0,
    @SerializedName("attempts") val attempts: Int = 0,
    @SerializedName("learners") val learners: Int = 0,
)

data class AiLastErrorDto(
    @SerializedName("detail") val detail: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

data class AiRecentDto(
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("ok") val ok: Int = 0,
    @SerializedName("detail") val detail: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

data class AiStatsDto(
    @SerializedName("total") val total: Int = 0,
    @SerializedName("ok") val ok: Int = 0,
    @SerializedName("failed") val failed: Int = 0,
    @SerializedName("explanations") val explanations: Int = 0,
    @SerializedName("last_error") val lastError: AiLastErrorDto? = null,
    @SerializedName("recent") val recent: List<AiRecentDto> = emptyList(),
)

data class AuditEntryDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("user_id") val userId: Int? = null,
    @SerializedName("action") val action: String? = null,
    @SerializedName("entity") val entity: String? = null,
    @SerializedName("entity_id") val entityId: String? = null,
    @SerializedName("details") val details: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("login") val login: String? = null,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
)

data class AdminStatsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("stats") val stats: AdminCountersDto = AdminCountersDto(),
    @SerializedName("by_role") val byRole: Map<String, Int> = emptyMap(),
    @SerializedName("ai") val ai: AiStatsDto = AiStatsDto(),
    @SerializedName("recent_users") val recentUsers: List<UserDto> = emptyList(),
    @SerializedName("recent_audit") val recentAudit: List<AuditEntryDto> = emptyList(),
)

data class AdminUsersDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("users") val users: List<UserDto> = emptyList(),
    @SerializedName("roles") val roles: List<String> = emptyList(),
)

data class TeacherUserDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("login") val login: String? = null,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
) {
    val displayName: String
        get() = listOfNotNull(firstName, lastName).filter { it.isNotBlank() }
            .joinToString(" ").ifBlank { login ?: "Учитель" }
}

data class CityDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("name") val name: String? = null,
    @SerializedName("region") val region: String? = null,
)

data class SchoolDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("city_id") val cityId: Int = 0,
    @SerializedName("name") val name: String? = null,
    @SerializedName("short_name") val shortName: String? = null,
    @SerializedName("address") val address: String? = null,
    @SerializedName("director") val director: String? = null,
    @SerializedName("city_name") val cityName: String? = null,
)

data class AdminOrgsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("cities") val cities: List<CityDto> = emptyList(),
    @SerializedName("schools") val schools: List<SchoolDto> = emptyList(),
    @SerializedName("classes") val classes: List<ClassDto> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
    @SerializedName("teachers") val teachers: List<TeacherUserDto> = emptyList(),
)

data class AdminTopicDto(
    @SerializedName("slug") val slug: String = "",
    @SerializedName("title") val title: String? = null,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("subject_id") val subjectId: Int = 0,
    @SerializedName("icon") val icon: String? = null,
    @SerializedName("color") val color: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("part") val part: String? = null,
    @SerializedName("page_start") val pageStart: Int? = null,
    @SerializedName("page_end") val pageEnd: Int? = null,
    @SerializedName("order_index") val orderIndex: Int = 0,
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("source") val source: String? = null,
    @SerializedName("subject_name") val subjectName: String? = null,
)

data class AdminTopicsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("topics") val topics: List<AdminTopicDto> = emptyList(),
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
)

data class TextbookDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("subject_id") val subjectId: Int = 0,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("publisher") val publisher: String? = null,
    @SerializedName("year") val year: String? = null,
    @SerializedName("filename") val filename: String? = null,
    @SerializedName("original_name") val originalName: String? = null,
    @SerializedName("size_bytes") val sizeBytes: Long = 0,
    @SerializedName("pages") val pages: Int = 0,
    @SerializedName("description") val description: String? = null,
    @SerializedName("topics_count") val topicsCount: Int = 0,
)

data class TextbooksDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("textbooks") val textbooks: List<TextbookDto> = emptyList(),
)

data class UploadTextbookResponse(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("textbook_id") val textbookId: Int = 0,
    @SerializedName("book_id") val bookId: Int = 0,
    @SerializedName("pages") val pages: Int = 0,
    @SerializedName("topics_linked") val topicsLinked: Int = 0,
    @SerializedName("topics_created") val topicsCreated: Int = 0,
    @SerializedName("visible_to_classes") val visibleToClasses: List<Int> = emptyList(),
)

data class AiSettingsDto(
    @SerializedName("enabled") val enabled: Boolean = false,
    @SerializedName("provider") val provider: String? = null,
    @SerializedName("provider_name") val providerName: String? = null,
    @SerializedName("base_url") val baseUrl: String? = null,
    @SerializedName("model") val model: String? = null,
    @SerializedName("temperature") val temperature: Double = 0.3,
    @SerializedName("max_tokens") val maxTokens: Int = 900,
    @SerializedName("system_note") val systemNote: String? = null,
    @SerializedName("has_key") val hasKey: Boolean = false,
)

data class AiTestDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("message") val message: String? = null,
)

data class AiProviderDto(
    @SerializedName("id") val id: String = "",
    @SerializedName("name") val name: String? = null,
    @SerializedName("base_url") val baseUrl: String? = null,
    @SerializedName("keys_url") val keysUrl: String? = null,
    @SerializedName("models") val models: List<String> = emptyList(),
    @SerializedName("note") val note: String? = null,
)

data class AdminAiDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("settings") val settings: AiSettingsDto = AiSettingsDto(),
    @SerializedName("providers") val providers: List<AiProviderDto> = emptyList(),
    @SerializedName("stats") val stats: AiStatsDto = AiStatsDto(),
)

data class SaveAiRequest(
    @SerializedName("enabled") val enabled: Boolean,
    @SerializedName("provider") val provider: String,
    @SerializedName("base_url") val baseUrl: String? = null,
    @SerializedName("api_key") val apiKey: String? = null,
    @SerializedName("keep_key") val keepKey: Boolean = true,
    @SerializedName("model") val model: String? = null,
    @SerializedName("temperature") val temperature: Double = 0.3,
    @SerializedName("max_tokens") val maxTokens: Int = 900,
    @SerializedName("system_note") val systemNote: String? = null,
)

data class AuditDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("entries") val entries: List<AuditEntryDto> = emptyList(),
)

data class ClassStudentsResponseDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("students") val students: List<TeacherUserDto> = emptyList(),
)

data class TopicResponseDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("topic") val topic: AdminTopicDto? = null,
)

data class CreateUserRequest(
    @SerializedName("login") val login: String,
    @SerializedName("password") val password: String,
    @SerializedName("role") val role: String,
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("city_id") val cityId: Int? = null,
    @SerializedName("school_id") val schoolId: Int? = null,
    @SerializedName("class_id") val classId: Int? = null,
)

data class UpdateUserRequest(
    @SerializedName("first_name") val firstName: String? = null,
    @SerializedName("last_name") val lastName: String? = null,
    @SerializedName("login") val login: String? = null,
    @SerializedName("role") val role: String? = null,
    @SerializedName("is_active") val isActive: Boolean? = null,
    @SerializedName("city_id") val cityId: Int? = null,
    @SerializedName("school_id") val schoolId: Int? = null,
)

data class UserResponse(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("user") val user: UserDto? = null,
)

data class CreateCityRequest(
    @SerializedName("name") val name: String,
    @SerializedName("region") val region: String? = null,
)

data class CreateSchoolRequest(
    @SerializedName("city_id") val cityId: Int,
    @SerializedName("name") val name: String,
    @SerializedName("address") val address: String? = null,
    @SerializedName("director") val director: String? = null,
)

data class CreateClassRequest(
    @SerializedName("school_id") val schoolId: Int,
    @SerializedName("grade") val grade: Int,
    @SerializedName("letter") val letter: String? = null,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("year") val year: String? = null,
    @SerializedName("title") val title: String? = null,
)

// ------------------------------------------------------------------ ИИ

data class AiExplainDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("cached") val cached: Boolean = false,
    @SerializedName("topic") val topic: TopicCardDto? = null,
    @SerializedName("content") val content: String? = null,
    @SerializedName("html") val html: String? = null,
    @SerializedName("model") val model: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

data class AiAskRequest(
    @SerializedName("question") val question: String,
    @SerializedName("page") val page: String? = null,
)

data class AiAnswerDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("answer") val answer: String? = null,
    @SerializedName("html") val html: String? = null,
)

// ------------------------------------------------------------------ e-padruchnik

data class PadruchnikItemDto(
    @SerializedName("id") val id: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("author") val author: String? = null,
    @SerializedName("grade") val grade: Int = 0,
    @SerializedName("year") val year: String? = null,
    @SerializedName("level") val level: String? = null,
    @SerializedName("language") val language: String? = null,
    @SerializedName("pdf_url") val pdfUrl: String? = null,
)

data class PadruchnikSearchDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("items") val items: List<PadruchnikItemDto> = emptyList(),
    @SerializedName("page") val page: Int = 0,
    @SerializedName("has_next") val hasNext: Boolean = false,
    @SerializedName("error") val error: String? = null,
    @SerializedName("source") val source: String? = null,
    @SerializedName("total") val total: Int? = null,
    @SerializedName("generated_at") val generatedAt: String? = null,
)

data class PadruchnikSubjectsDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("subjects") val subjects: List<SubjectDto> = emptyList(),
)

data class PadruchnikImportRequest(
    @SerializedName("book_id") val bookId: Int,
    @SerializedName("subject_id") val subjectId: Int,
    @SerializedName("grade") val grade: Int,
    @SerializedName("class_ids") val classIds: List<Int> = emptyList(),
)

data class PadruchnikImportDto(
    @SerializedName("ok") val ok: Boolean = false,
    @SerializedName("error") val error: String? = null,
    @SerializedName("message") val message: String? = null,
    @SerializedName("textbook_id") val textbookId: Int = 0,
    @SerializedName("book_id") val bookId: Int = 0,
    @SerializedName("title") val title: String? = null,
    @SerializedName("pages") val pages: Int = 0,
    @SerializedName("linked") val linked: Int = 0,
    @SerializedName("created") val created: Int = 0,
)

