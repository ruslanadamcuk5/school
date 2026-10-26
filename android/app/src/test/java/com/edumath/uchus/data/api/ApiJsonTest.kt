package com.edumath.uchus.data.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiJsonTest {

    @Test
    fun parsesNumericAndLegacyActiveFlag() {
        val json = """
            {
              "ok": true,
              "token": "token",
              "user": {
                "id": 1,
                "login": "admin",
                "role": "admin",
                "is_Active": 1
              },
              "learner": null,
              "theme": "adult"
            }
        """.trimIndent()

        val session = ApiJson.gson.fromJson(json, SessionDto::class.java)

        assertNotNull(session)
        assertTrue(session.user?.isActive == true)
        assertEquals("admin", session.user?.login)
    }

    @Test
    fun parsesBooleanFlagFromCurrentServer() {
        val json = """
            {
              "ok": true,
              "user": {
                "id": 2,
                "login": "petrova",
                "role": "teacher",
                "is_active": false
              }
            }
        """.trimIndent()

        val session = ApiJson.gson.fromJson(json, SessionDto::class.java)

        assertFalse(session.user?.isActive == true)
    }

    @Test
    fun parsesTaskWidgetObjectWithoutLosingTask() {
        val json = """
            {
              "ok": true,
              "round_id": 7,
              "topic": {"slug": "numbers_1000", "title": "Числа до 1000"},
              "task": {
                "question": "Сравни числа: 125 и 251",
                "answer_type": "choice",
                "choices": ["125", "251"],
                "widget": {"kind": "number_line", "min": 0, "max": 1000},
                "difficulty": 1,
                "generator": "numbers_1000.compare",
                "index": 0,
                "total": 8,
                "method": {"slug": "compare", "name": "Сравнение"},
                "methods": [{"slug": "compare", "name": "Сравнение"}],
                "hints_left": 3,
                "can_switch_method": false
              },
              "state": {"correct": 0, "answered": 0, "index": 0, "total": 8},
              "done": false
            }
        """.trimIndent()

        val start = ApiJson.gson.fromJson(json, PlayStartDto::class.java)

        assertNotNull(start.task)
        assertEquals("Сравни числа: 125 и 251", start.task?.question)
        assertEquals(2, start.task?.choices?.size)
        assertEquals(
            "number_line",
            start.task?.widget?.asJsonObject?.get("kind")?.asString,
        )
    }
}
