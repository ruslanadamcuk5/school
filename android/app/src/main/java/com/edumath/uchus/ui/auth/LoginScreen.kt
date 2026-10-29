package com.edumath.uchus.ui.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.data.api.LearnerDto
import com.edumath.uchus.ui.common.ErrorBox
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(vm: AuthViewModel) {
    val state by vm.state.collectAsState()

    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showCreate by remember { mutableStateOf(false) }
    var childName by remember { mutableStateOf("") }
    var childGrade by remember { mutableIntStateOf(3) }
    var childPin by remember { mutableStateOf("") }
    var pinFor by remember { mutableStateOf<LearnerDto?>(null) }
    var pinValue by remember { mutableStateOf("") }
    var googleBusy by remember { mutableStateOf(false) }

    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { vm.refreshLearners() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("📚 Учусь", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Школьная платформа: темы, тренировки, работы и библиотека.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(4.dp))

        OutlinedTextField(
            value = state.server,
            onValueChange = vm::setServer,
            label = { Text("Адрес сервера") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            "Например: https://virusadk.alwaysdata.net",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        OutlinedTextField(
            value = login,
            onValueChange = { login = it },
            label = { Text("Логин") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Пароль") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )

        Button(
            onClick = { vm.login(login, password) },
            enabled = !state.busy,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
        ) {
            if (state.busy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
            } else {
                Text("Войти")
            }
        }

        state.error?.let { message ->
            ErrorBox(message)
        }

        OutlinedButton(
            onClick = {
                if (googleBusy) return@OutlinedButton
                googleBusy = true
                vm.clearError()
                scope.launch {
                    try {
                        val result = GoogleSignIn.signIn(context)
                        vm.googleLogin(result.idToken, result.nonce)
                    } catch (e: GoogleSignInException) {
                        vm.showError(e.message)
                    } catch (e: Exception) {
                        vm.showError(
                            "Не удалось войти через Google: " +
                                (e.message ?: "неизвестная ошибка")
                        )
                    } finally {
                        googleBusy = false
                    }
                }
            },
            enabled = !state.busy && !googleBusy,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
        ) {
            if (googleBusy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.primary,
                )
            } else {
                Text("Войти через Google")
            }
        }
        Text(
            "Аккаунт Google создаётся и на сайте: роль и имя выберете при первом входе.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        HorizontalDivider(Modifier.padding(vertical = 8.dp))

        Text("👨‍👩‍👧 Профили детей", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text(
            "Вход без аккаунта — как на экране приветствия в веб-версии.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        when {
            !state.learnersLoaded -> Text("Загрузка…", style = MaterialTheme.typography.bodySmall)
            state.learners.isEmpty() -> Text(
                "Профилей пока нет. Создайте первый профиль ниже.",
                style = MaterialTheme.typography.bodySmall,
            )
            else -> state.learners.forEach { learner ->
                LearnerRow(learner) {
                    if (learner.hasPin) {
                        pinValue = ""
                        pinFor = learner
                    } else {
                        vm.loginLearner(learner)
                    }
                }
            }
        }

        OutlinedButton(
            onClick = { showCreate = !showCreate },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (showCreate) "Скрыть форму" else "Создать профиль ребёнка")
        }

        if (showCreate) {
            Card(Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedTextField(
                        value = childName,
                        onValueChange = { childName = it },
                        label = { Text("Имя ребёнка") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )

                    Text("Класс", style = MaterialTheme.typography.labelMedium)
                    LazyRow(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        contentPadding = PaddingValues(vertical = 2.dp),
                    ) {
                        items(11) { index ->
                            val grade = index + 1
                            FilterChip(
                                selected = childGrade == grade,
                                onClick = { childGrade = grade },
                                label = { Text("$grade") },
                            )
                        }
                    }

                    OutlinedTextField(
                        value = childPin,
                        onValueChange = { value ->
                            if (value.length <= 4 && value.all { it.isDigit() }) childPin = value
                        },
                        label = { Text("PIN (необязательно, 4 цифры)") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                    )

                    Button(
                        onClick = { vm.createLearner(childName, childGrade, childPin) },
                        enabled = !state.busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Создать и войти")
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        Text(
            "Приложение работает с вашим сервером. Администратор, учитель, родитель и ребёнок входят в один и тот же аккаунт, что и на сайте.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    val target = pinFor
    if (target != null) {
        AlertDialog(
            onDismissRequest = { pinFor = null },
            title = { Text("PIN профиля") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Введите PIN-код для профиля «${target.displayName}».")
                    OutlinedTextField(
                        value = pinValue,
                        onValueChange = { value ->
                            if (value.length <= 4 && value.all { it.isDigit() }) pinValue = value
                        },
                        label = { Text("PIN") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        vm.loginLearner(target, pinValue)
                        pinFor = null
                    },
                ) { Text("Войти") }
            },
            dismissButton = {
                TextButton(onClick = { pinFor = null }) { Text("Отмена") }
            },
        )
    }
    val signup = state.googlePrompt
    if (signup != null) {
        var role by remember(signup) { mutableStateOf("student") }
        var firstName by remember(signup) { mutableStateOf(signup.firstName) }
        var lastName by remember(signup) { mutableStateOf(signup.lastName) }
        var newLogin by remember(signup) { mutableStateOf(signup.suggestedLogin) }
        var childCode by remember(signup) { mutableStateOf("") }

        AlertDialog(
            onDismissRequest = { if (!state.busy) vm.cancelGoogleSignup() },
            title = { Text("Регистрация через Google") },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        "Вы вошли как ${signup.email}. Осталось выбрать роль и имя — " +
                            "пароль не нужен, входить будете через Google.",
                        style = MaterialTheme.typography.bodySmall,
                    )

                    Text("Кто вы?", style = MaterialTheme.typography.labelMedium)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(listOf("student" to "Ученик", "teacher" to "Учитель", "parent" to "Родитель")) { item ->
                            FilterChip(
                                selected = role == item.first,
                                onClick = { role = item.first },
                                label = { Text(item.second) },
                            )
                        }
                    }

                    OutlinedTextField(
                        value = firstName,
                        onValueChange = { firstName = it },
                        label = { Text("Имя") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = lastName,
                        onValueChange = { lastName = it },
                        label = { Text("Фамилия (необязательно)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = newLogin,
                        onValueChange = { newLogin = it.trim().take(32) },
                        label = { Text("Логин для входа на сайте") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (role == "parent") {
                        OutlinedTextField(
                            value = childCode,
                            onValueChange = { childCode = it.trim().uppercase().take(12) },
                            label = { Text("Код ребёнка (необязательно)") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }

                    state.error?.let { message ->
                        Text(
                            message,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        vm.googleFinishSignup(role, newLogin, firstName, lastName, childCode)
                    },
                    enabled = !state.busy,
                ) {
                    Text(if (state.busy) "Создаём…" else "Создать аккаунт")
                }
            },
            dismissButton = {
                TextButton(onClick = { vm.cancelGoogleSignup() }) { Text("Отмена") }
            },
        )
    }
}

@Composable
private fun LearnerRow(learner: LearnerDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(learner.emoji, fontSize = 28.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(learner.displayName, fontWeight = FontWeight.SemiBold)
                Text(
                    "${learner.grade} класс",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
    }
}
