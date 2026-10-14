import json
from typing import Any

import httpx


class TeacherApiClient:
    def __init__(self, base_url: str, token: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout

    async def create_lesson(
        self,
        *,
        topic: str,
        level: str,
        files: list[tuple[str, bytes, str]],
        duration_minutes: int = 80,
        teacher_context: str | None = None,
        age_bucket: str | None = None,
        extra_instructions: str | None = None,
        textbook_hint: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, str] = {
            "topic": topic,
            "level": level,
            "duration_minutes": str(duration_minutes),
        }
        if teacher_context:
            data["teacher_context"] = teacher_context
        if age_bucket:
            data["age_bucket"] = age_bucket
        if extra_instructions:
            data["extra_instructions"] = extra_instructions
        if textbook_hint:
            data["textbook_hint"] = textbook_hint

        multipart = [
            ("files", (name, content, content_type))
            for name, content, content_type in files
        ]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/lesson/",
                headers=self.headers,
                data=data,
                files=multipart or None,
            )
            response.raise_for_status()
            return response.json()

    async def task_status(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/task/{task_id}/status/",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def wait_task(
        self,
        task_id: str,
        *,
        poll_interval: float = 2.0,
        max_attempts: int = 90,
    ) -> dict[str, Any]:
        import asyncio

        last: dict[str, Any] = {}
        for _ in range(max_attempts):
            last = await self.task_status(task_id)
            if last.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                return last
            await asyncio.sleep(poll_interval)
        return last

    async def download_lesson_docx(self, lesson_id: int) -> bytes:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/lesson/{lesson_id}/docx/",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.content

    async def get_lesson(self, lesson_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/lesson/{lesson_id}/",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def approve_lesson(self, lesson_id: int, draft: dict) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/lesson/{lesson_id}/approve/",
                headers=self.headers,
                data={
                    "use_uploaded_file": "false",
                    "final_content": json.dumps(draft, ensure_ascii=False),
                },
            )
            response.raise_for_status()
            return response.json()

    async def remark_lesson(self, lesson_id: int, remarks: list[str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/lesson/{lesson_id}/remarks/",
                headers=self.headers,
                json={"remarks": remarks},
            )
            response.raise_for_status()
            return response.json()

    async def approve_lesson_with_file(
        self,
        lesson_id: int,
        *,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/lesson/{lesson_id}/approve/",
                headers=self.headers,
                data={"use_uploaded_file": "true"},
                files={"file": (filename, content, content_type)},
            )
            response.raise_for_status()
            return response.json()
