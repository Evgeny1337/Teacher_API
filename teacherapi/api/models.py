from django.db import models


class AgeBucketChoices(models.TextChoices):
    KIDS = "kids", "Kids"
    TEENS = "teens", "Teens"
    ADULTS = "adults", "Adults"


class StatusLessonChoices(models.TextChoices):
    GENERATED = "generated", "Generated"
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    ERROR = "error", "Error"


class GeneratedLesson(models.Model):
    topic = models.CharField(max_length=255, blank=True, null=True)
    level = models.CharField(max_length=255, default="B1")
    age_bucket = models.CharField(max_length=10, choices=AgeBucketChoices, null=True, default=None)
    duration_minutes = models.PositiveIntegerField(default=80)
    teacher_context = models.TextField(blank=True, null=True)
    extra_instructions = models.TextField(blank=True, null=True)
    textbook_hint = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=StatusLessonChoices, default=StatusLessonChoices.DRAFT)
    final = models.JSONField(blank=True, null=True)
    task_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)


class ReferenceLesson(models.Model):
    title = models.CharField(max_length=255, blank=True, null=True)
    structured_content = models.JSONField(blank=True, null=True)
    level = models.CharField(max_length=255, default="B1")
    age_bucket = models.CharField(max_length=10, choices=AgeBucketChoices, null=True, default=None)
    teacher_context = models.TextField(blank=True, null=True)

class LessonIteration(models.Model):
    body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    draft = models.JSONField(blank=True, null=True)
    generated_lesson = models.ForeignKey(GeneratedLesson, on_delete=models.CASCADE, null=True, default=None, related_name="iterations")
    iteration_number = models.PositiveIntegerField(default=1)


class Attachment(models.Model):
    class AttachmentTypes(models.TextChoices):
        REFERENCE = "reference", "Reference"
        MATERIAL = "material", "Material"
        FINAL = "final", "Final"

    type = models.CharField(choices=AttachmentTypes, default=AttachmentTypes.REFERENCE, max_length=10)
    file = models.FileField(upload_to="attachments/", max_length=255, blank=True, null=True)
    generated_lesson = models.ForeignKey(GeneratedLesson, on_delete=models.CASCADE, null=True, default=None)
    reference_lesson = models.ForeignKey(ReferenceLesson, on_delete=models.CASCADE, null=True, default=None)


class TeacherRemark(models.Model):
    remark = models.TextField()
    lesson_iteration = models.ForeignKey(LessonIteration, on_delete=models.CASCADE)

