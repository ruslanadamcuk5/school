package com.edumath.uchus.data.api

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/** Контракт JSON API v1 (см. docs/API.md). */
interface ApiService {

    @GET("health")
    suspend fun health(): HealthDto

    // ---------------------------------------------------------- вход
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): SessionDto

    @POST("auth/logout")
    suspend fun logout(): SimpleOkDto

    @GET("auth/me")
    suspend fun me(): SessionDto

    // ---------------------------------------------------------- семейные профили
    @GET("learners")
    suspend fun learners(): LearnersDto

    @POST("learners")
    suspend fun createLearner(@Body body: CreateLearnerRequest): SessionDto

    @POST("learners/{id}/login")
    suspend fun loginLearner(
        @Path("id") id: Int,
        @Body body: LearnerLoginRequest,
    ): SessionDto

    @POST("learners/switch")
    suspend fun switchLearner(@Body body: Map<String, Int>): SessionDto

    // ---------------------------------------------------------- метаданные
    @GET("meta")
    suspend fun meta(): MetaDto

    @GET("topics")
    suspend fun topics(
        @Query("grade") grade: Int?,
        @Query("subject_id") subjectId: Int?,
        @Query("search") search: String?,
    ): TopicCatalogDto

    // ---------------------------------------------------------- карта и темы
    @GET("map")
    suspend fun map(
        @Query("grade") grade: Int?,
        @Query("subject") subject: String?,
    ): MapDto

    @GET("topics/{slug}")
    suspend fun topic(@Path("slug") slug: String): TopicDetailDto

    @GET("topics/{slug}/text")
    suspend fun topicText(@Path("slug") slug: String): TopicTextDto

    @GET("topics/{slug}/quiz")
    suspend fun quiz(@Path("slug") slug: String): QuizStartDto

    @POST("topics/{slug}/quiz")
    suspend fun quizSubmit(
        @Path("slug") slug: String,
        @Body body: QuizSubmitRequest,
    ): QuizResultDto

    @POST("topics/{slug}/read")
    suspend fun markRead(@Path("slug") slug: String): SimpleOkDto

    // ---------------------------------------------------------- игра
    @POST("play/start")
    suspend fun playStart(@Body body: PlayStartRequest): PlayStartDto

    @GET("play/{id}")
    suspend fun playRound(@Path("id") id: Int): PlayRoundDto

    @POST("play/{id}/answer")
    suspend fun playAnswer(
        @Path("id") id: Int,
        @Body body: AnswerRequest,
    ): AnswerDto

    @POST("play/{id}/hint")
    suspend fun playHint(@Path("id") id: Int): HintDto

    @POST("play/{id}/switch-method")
    suspend fun playSwitch(@Path("id") id: Int): SwitchMethodDto

    @GET("play/{id}/result")
    suspend fun playResult(@Path("id") id: Int): PlayResultDto

    @GET("daily")
    suspend fun daily(): DailyDto

    @POST("daily/start")
    suspend fun dailyStart(@Body body: DailyStartRequest): PlayStartDto

    // ---------------------------------------------------------- работы: ученик
    @GET("assignments")
    suspend fun studentAssignments(): AssignmentsDto

    @GET("assignments/{id}")
    suspend fun assignment(@Path("id") id: Int): AssignmentDetailDto

    @POST("assignments/{id}/submit")
    suspend fun submitAssignment(
        @Path("id") id: Int,
        @Body body: SubmitRequest,
    ): SubmitResponse

    @POST("assignments/{id}/retry")
    suspend fun retryAssignment(@Path("id") id: Int): SimpleOkDto

    @GET("assignments/{id}/result")
    suspend fun assignmentResult(@Path("id") id: Int): AssignmentDetailDto

    // ---------------------------------------------------------- работы: учитель
    @GET("teacher/assignments")
    suspend fun teacherAssignments(): AssignmentsDto

    @POST("teacher/assignments")
    suspend fun createTeacherAssignment(
        @Body body: CreateAssignmentRequest,
    ): CreateAssignmentResponse

    @PATCH("teacher/assignments/{id}")
    suspend fun updateTeacherAssignment(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): CreateAssignmentResponse

    @POST("teacher/assignments/{id}/publish")
    suspend fun publishAssignment(@Path("id") id: Int): SimpleOkDto

    @POST("teacher/assignments/{id}/close")
    suspend fun closeAssignment(@Path("id") id: Int): SimpleOkDto

    @DELETE("teacher/assignments/{id}")
    suspend fun deleteAssignment(@Path("id") id: Int): SimpleOkDto

    @GET("teacher/assignments/{id}/results")
    suspend fun assignmentResults(@Path("id") id: Int): TeacherResultsDto

    // ---------------------------------------------------------- работы: родитель
    @GET("parent/assignments")
    suspend fun parentAssignments(): AssignmentsDto

    @POST("parent/assignments")
    suspend fun createParentAssignment(
        @Body body: CreateAssignmentRequest,
    ): CreateAssignmentResponse

    // ---------------------------------------------------------- библиотека
    @GET("library")
    suspend fun library(): LibraryDto

    @GET("library/books/{id}")
    suspend fun libraryBook(@Path("id") id: Int): BookInfoDto

    @GET("books/{id}")
    suspend fun book(@Path("id") id: Int): BookInfoDto

    @POST("library/recommendations/{id}/done")
    suspend fun recommendationDone(@Path("id") id: Int): SimpleOkDto

    @GET("parent/library")
    suspend fun parentLibrary(@Query("child_id") childId: Int?): LibraryDto

    @GET("teacher/library")
    suspend fun teacherLibrary(
        @Query("search") search: String?,
        @Query("grade") grade: Int?,
        @Query("subject_id") subjectId: Int?,
    ): TeacherLibraryDto

    @POST("teacher/library")
    suspend fun createTeacherBook(@Body body: Map<String, Any?>): BookInfoDto

    @PATCH("teacher/library/{id}")
    suspend fun updateTeacherBook(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): BookInfoDto

    @DELETE("teacher/library/{id}")
    suspend fun deleteTeacherBook(@Path("id") id: Int): SimpleOkDto

    @POST("teacher/library/{id}/recommend")
    suspend fun recommendBook(
        @Path("id") id: Int,
        @Body body: RecommendRequest,
    ): SimpleOkDto

    @GET("teacher/library/recommendations")
    suspend fun teacherRecommendations(): TeacherRecommendationsDto

    @DELETE("teacher/library/recommendations/{id}")
    suspend fun revokeRecommendation(@Path("id") id: Int): SimpleOkDto

    @GET("teacher/textbooks")
    suspend fun teacherTextbooks(
        @Query("subject_id") subjectId: Int?,
        @Query("grade") grade: Int?,
        @Query("search") search: String?,
    ): TextbooksDto

    @Multipart
    @POST("teacher/textbooks")
    suspend fun uploadTextbook(
        @Part file: MultipartBody.Part,
        @Part("subject_id") subjectId: RequestBody,
        @Part("grade") grade: RequestBody,
        @Part("title") title: RequestBody,
        @Part("author") author: RequestBody,
        @Part("description") description: RequestBody,
    ): UploadTextbookResponse

    // ---------------------------------------------------------- учитель
    @GET("teacher/dashboard")
    suspend fun teacherDashboard(): TeacherDashboardDto

    @GET("teacher/classes")
    suspend fun teacherClasses(): ClassesDto

    @GET("teacher/classes/{id}")
    suspend fun teacherClass(@Path("id") id: Int): ClassDetailDto

    @GET("teacher/students")
    suspend fun teacherStudents(): TeacherStudentsDto

    @GET("teacher/students/{id}")
    suspend fun teacherStudent(@Path("id") id: Int): StudentDetailDto

    @GET("teacher/schedule")
    suspend fun teacherSchedule(@Query("class_id") classId: Int?): ScheduleDto

    @POST("teacher/schedule")
    suspend fun saveSchedule(@Body body: Map<String, Any?>): ScheduleDto

    @DELETE("teacher/schedule/{id}")
    suspend fun deleteSchedule(@Path("id") id: Int): SimpleOkDto

    @GET("schedule")
    suspend fun studentSchedule(): ScheduleDto

    // ---------------------------------------------------------- родитель
    @GET("parent/dashboard")
    suspend fun parentDashboard(): ParentDashboardDto

    @GET("parent/children")
    suspend fun parentChildren(): ChildrenDto

    @GET("parent/children/{id}")
    suspend fun parentChild(@Path("id") id: Int): ChildDetailDto

    @PATCH("parent/children/{id}")
    suspend fun updateChild(
        @Path("id") id: Int,
        @Body body: UpdateChildRequest,
    ): ChildResponseDto

    @POST("parent/children/{id}/reset")
    suspend fun resetChild(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): SimpleOkDto

    @POST("parent/link")
    suspend fun linkChild(@Body body: Map<String, String>): LinkChildResponseDto

    // ---------------------------------------------------------- админ
    @GET("admin/stats")
    suspend fun adminStats(): AdminStatsDto

    @GET("admin/users")
    suspend fun adminUsers(
        @Query("role") role: String?,
        @Query("search") search: String?,
    ): AdminUsersDto

    @POST("admin/users")
    suspend fun createUser(@Body body: CreateUserRequest): UserResponse

    @PATCH("admin/users/{id}")
    suspend fun updateUser(
        @Path("id") id: Int,
        @Body body: UpdateUserRequest,
    ): UserResponse

    @POST("admin/users/{id}/password")
    suspend fun setUserPassword(
        @Path("id") id: Int,
        @Body body: Map<String, String>,
    ): SimpleOkDto

    @DELETE("admin/users/{id}")
    suspend fun deleteUser(@Path("id") id: Int): SimpleOkDto

    @GET("admin/orgs")
    suspend fun adminOrgs(): AdminOrgsDto

    @POST("admin/cities")
    suspend fun createCity(@Body body: CreateCityRequest): IdDto

    @POST("admin/schools")
    suspend fun createSchool(@Body body: CreateSchoolRequest): IdDto

    @PATCH("admin/schools/{id}")
    suspend fun updateSchool(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): SimpleOkDto

    @DELETE("admin/schools/{id}")
    suspend fun deleteSchool(@Path("id") id: Int): SimpleOkDto

    @POST("admin/classes")
    suspend fun createClass(@Body body: CreateClassRequest): IdDto

    @PATCH("admin/classes/{id}")
    suspend fun updateClass(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): SimpleOkDto

    @DELETE("admin/classes/{id}")
    suspend fun deleteClass(@Path("id") id: Int): SimpleOkDto

    @POST("admin/classes/{id}/students")
    suspend fun classStudents(
        @Path("id") id: Int,
        @Body body: Map<String, Any?>,
    ): ClassStudentsResponseDto

    @GET("admin/topics")
    suspend fun adminTopics(
        @Query("subject_id") subjectId: Int?,
        @Query("grade") grade: Int?,
        @Query("search") search: String?,
    ): AdminTopicsDto

    @POST("admin/topics")
    suspend fun createTopic(@Body body: Map<String, Any?>): IdDto

    @PATCH("admin/topics/{slug}")
    suspend fun updateTopic(
        @Path("slug") slug: String,
        @Body body: Map<String, Any?>,
    ): TopicResponseDto

    @DELETE("admin/topics/{slug}")
    suspend fun deleteTopic(@Path("slug") slug: String): SimpleOkDto

    @GET("admin/textbooks")
    suspend fun adminTextbooks(
        @Query("subject_id") subjectId: Int?,
        @Query("grade") grade: Int?,
        @Query("search") search: String?,
    ): TextbooksDto

    @DELETE("admin/textbooks/{id}")
    suspend fun deleteTextbook(@Path("id") id: Int): SimpleOkDto

    @GET("admin/ai")
    suspend fun adminAi(): AdminAiDto

    @PUT("admin/ai")
    suspend fun saveAi(@Body body: SaveAiRequest): AdminAiDto

    @POST("admin/ai/test")
    suspend fun adminAiTest(): AiTestDto

    @GET("admin/audit")
    suspend fun adminAudit(@Query("limit") limit: Int?): AuditDto

    // ---------------------------------------------------------- ИИ
    @GET("ai/status")
    suspend fun aiStatus(): AiStatusResponseDto

    @GET("ai/explain/{slug}")
    suspend fun aiExplain(@Path("slug") slug: String): AiExplainDto

    @POST("ai/explain/{slug}/refresh")
    suspend fun aiExplainRefresh(@Path("slug") slug: String): AiExplainDto

    @POST("ai/assistant")
    suspend fun aiAsk(@Body body: AiAskRequest): AiAnswerDto
}
