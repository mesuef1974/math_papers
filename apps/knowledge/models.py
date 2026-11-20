"""معرفة المنهج: أهداف الدروس وتدرّج المفاهيم ودعم المعلم وقوالب الطلب. حقول وقيود فقط.

المحتوى كله بصياغتنا ومستخلص من دليل المعلم؛ لا صفحة خام ولا نص سؤال أو حل. المستويات (K/A/R) ومستويات بلوم
في قوالب الطلب مستنتجة منا من موضع التمرين وتقسيم الدليل، فالدليل لا يطبعها صراحة.
"""

from __future__ import annotations

from django.db import models

from apps.curriculum.models import Course, Lesson


class Level(models.TextChoices):
    EASY = "K", "سهل"
    MEDIUM = "A", "متوسط"
    HIGHER = "R", "مهارات عليا"


class Bloom(models.TextChoices):
    REMEMBER = "تذكر", "تذكر"
    UNDERSTAND = "فهم", "فهم"
    APPLY = "تطبيق", "تطبيق"
    ANALYZE = "تحليل", "تحليل"
    EVALUATE = "تقويم", "تقويم"
    CREATE = "إبداع", "إبداع"


class Standard(models.Model):
    """معيار من معايير المنهج مثل 12A.3.4."""

    code = models.CharField(max_length=16, unique=True)  # يحمل صفه في بادئته، ففرادته عامة لكل المقررات

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Practice(models.Model):
    """ممارسة رياضية من ممارسات المنهج مثل MP.4."""

    code = models.CharField(max_length=8, unique=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Source(models.TextChoices):
    AUTHORED = "authored", "صياغتنا من الدليل"
    EXTRACTED = "extracted", "مستخرج آليًا ومطابق للمعيار الذهبي"


class Status(models.TextChoices):
    DRAFT = "draft", "مسودة"
    REVIEWED = "reviewed", "مراجَع"


class LessonProfile(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="profile")
    # أصل ملف الدرس وحالته؛ تنطبق على بنوده كلها (الأهداف والأمثلة والتمارين...).
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.AUTHORED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REVIEWED)
    title_en = models.CharField(max_length=160, blank=True)
    objective = models.TextField(blank=True)
    rationale = models.TextField(blank=True)  # لماذا نتعلمه
    motivation = models.TextField(blank=True)  # تحفيز بداية الدرس
    self_assessment = models.JSONField(default=list, blank=True)  # أرقام تمارين التقييم الذاتي
    standards = models.ManyToManyField(Standard, related_name="lessons", blank=True)
    practices = models.ManyToManyField(Practice, related_name="lessons", blank=True)
    # مواصفة الدرس العددية. فارغ = لم يُستخرج (لا يُخمَّن)، وليس صفرًا.
    task_basic = models.CharField(max_length=40, blank=True)  # مدى تمارين دليل المهام الأساسي
    task_advanced = models.CharField(max_length=40, blank=True)
    quiz_depths = models.JSONField(default=list, blank=True)  # أعماق المعرفة لاختبار الدرس
    exercises_total = models.PositiveSmallIntegerField(null=True, blank=True)
    vocab_new = models.PositiveSmallIntegerField(null=True, blank=True)
    vocab_review = models.PositiveSmallIntegerField(null=True, blank=True)
    # صفحات التمارين المطبوعة: مديات {first, last, page} (domain/exercise_pages.py)؛ فارغ = لم تُستخرج
    exercise_pages = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["lesson__course_id", "lesson__unit", "lesson__number", "lesson__code"]

    def __str__(self) -> str:
        return f"ملف الدرس {self.lesson_id}"


class LessonItem(models.Model):
    """بند مرتب من معرفة الدرس. النوع يحدد دوره، والترتيب داخل النوع الواحد."""

    class Kind(models.TextChoices):
        LEARNING_GOAL = "learning_goal", "ما سيتعلمه الطالب"
        GUIDE_STEP = "guide_step", "خطوة دليل الدرس"
        PREREQUISITE = "prerequisite", "معرفة سابقة"
        CONCEPT_STEP = "concept_step", "خطوة في تدرّج المفهوم"
        THINK_QUESTION = "think_question", "سؤال للتفكر"
        STRUGGLING = "struggling", "دعم للطلاب الذين يواجهون صعوبات"
        FAST_FINISHER = "fast_finisher", "إثراء لسريعي الإنجاز"
        FOLLOW_UP = "follow_up", "متابعة"
        STUDY_TIP = "study_tip", "مساعدة دراسية"
        CAUTION = "caution", "تنبيه"
        REMINDER = "reminder", "تذكير"
        GUIDANCE = "guidance", "إرشاد"
        REAL_WORLD = "real_world", "ربط بالواقع أو بمادة أخرى"
        HISTORY = "history", "تاريخ الرياضيات"
        NOTE = "note", "ملاحظة"
        EXERCISE_NOTE = "exercise_note", "ملاحظة على التمارين"
        COMMON_ERROR = "common_error", "خطأ شائع"
        TECHNOLOGY = "technology", "استعمال التقنية"
        CONNECTION = "connection", "ارتباط بدرس أو مهارة"
        SOLUTION_STYLE = "solution_style", "أسلوب الحل النموذجي"
        PEARL = "pearl", "درّة للتحضير"

    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    order = models.PositiveSmallIntegerField(default=1)
    label = models.CharField(max_length=80, blank=True)  # عنوان الصندوق كما في الدليل إن اختلف عن النوع
    text = models.TextField()

    class Meta:
        ordering = ["profile_id", "kind", "order"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "kind", "order"], name="unique_lesson_item")
        ]

    def __str__(self) -> str:
        return f"{self.profile_id} {self.kind} {self.order}"


class LessonObjective(models.Model):
    """هدف تعلم مرتب بمستوى بلوم. النص فارغ للمصادر التي لا يدخل نصها المستودع."""

    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="objectives")
    order = models.PositiveSmallIntegerField()
    bloom = models.CharField(max_length=12)  # قيم Bloom أو unclassified
    text = models.TextField(blank=True)

    class Meta:
        ordering = ["profile_id", "order"]
        constraints = [models.UniqueConstraint(fields=["profile", "order"], name="unique_lesson_objective")]

    def __str__(self) -> str:
        return f"{self.profile_id} هدف {self.order}"


class ExerciseGroup(models.Model):
    """مجموعة تمارين: مثال الدرس الذي تدرّب عليه وعمقها المعرفي وأرقامها، ونوعها (تمرين المثال أو تمارين قسم «تمارين»)."""

    class Kind(models.TextChoices):
        TRY = "try", "تمرين المثال"
        PRACTICE = "practice", "تمارين الدرس"

    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="exercise_groups")
    order = models.PositiveSmallIntegerField()
    example = models.PositiveSmallIntegerField()
    dok = models.PositiveSmallIntegerField()
    exercises = models.JSONField(default=list)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TRY)

    class Meta:
        ordering = ["profile_id", "order"]
        constraints = [models.UniqueConstraint(fields=["profile", "order"], name="unique_exercise_group")]

    def __str__(self) -> str:
        return f"{self.profile_id} مثال {self.example} عمق {self.dok}"


class Term(models.Model):
    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="terms")
    ar = models.CharField(max_length=120)
    en = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["profile_id", "ar"]
        constraints = [models.UniqueConstraint(fields=["profile", "ar"], name="unique_lesson_term")]

    def __str__(self) -> str:
        return self.ar


class WorkedExample(models.Model):
    """مثال محلول في الدرس: المهارة وطرائقها، لا نصه."""

    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="examples")
    number = models.PositiveSmallIntegerField()
    page = models.PositiveSmallIntegerField(null=True, blank=True)  # صفحته المطبوعة في كتاب الطالب إن عُرفت
    skill = models.TextField()
    representation = models.CharField(max_length=60, blank=True)
    representations = models.JSONField(default=list, blank=True)  # التمثيلات من قائمة مغلقة
    methods = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["profile_id", "number"]
        constraints = [models.UniqueConstraint(fields=["profile", "number"], name="unique_lesson_example")]

    def __str__(self) -> str:
        return f"مثال {self.number} في {self.profile_id}"


class ExerciseTemplate(models.Model):
    """مجموعة تمارين متجانسة: صيغة الطلب المعيارية ومهارتها وتمثيلها ومستواها المستنتج."""

    class Category(models.TextChoices):
        PRACTICE = "practice", "تدريب"
        STANDARD_TEST = "standard_test", "أسئلة اختبار معيارية"
        EXPLORATION = "exploration", "استكشاف"
        WRITING = "writing", "الكتابة للتعلم"
        EXTENSION = "extension", "توسيع الأفكار"
        GROUP = "group", "نشاط جماعي"

    profile = models.ForeignKey(LessonProfile, on_delete=models.CASCADE, related_name="templates")
    order = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=40)  # نطاق أرقام التمارين في الدليل
    directive_template = models.TextField(blank=True)
    skill = models.TextField()
    representation = models.CharField(max_length=60, blank=True)
    level = models.CharField(max_length=1, choices=Level.choices, blank=True)
    bloom = models.CharField(max_length=8, choices=Bloom.choices, blank=True)
    inference_note = models.TextField(blank=True)  # تحفظ على المستوى أو بلوم المستنتجين
    count = models.PositiveSmallIntegerField(default=1)
    category = models.CharField(max_length=14, choices=Category.choices, default=Category.PRACTICE)

    class Meta:
        ordering = ["profile_id", "order"]
        constraints = [models.UniqueConstraint(fields=["profile", "order"], name="unique_lesson_template")]

    def __str__(self) -> str:
        return f"{self.profile_id} [{self.label}]"

    @property
    def uses_graph(self) -> bool:
        return "بياني" in self.representation


class UnitProfile(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="units")
    unit = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120)
    big_idea = models.TextField(blank=True)
    approach = models.TextField(blank=True)
    context = models.TextField(blank=True)  # تاريخ أو تطبيق يفتتح به الدليل الوحدة

    class Meta:
        ordering = ["course_id", "unit"]
        constraints = [models.UniqueConstraint(fields=["course", "unit"], name="unique_unit_per_course")]

    def __str__(self) -> str:
        return f"الوحدة {self.unit}: {self.title}"


class UnitProject(models.Model):
    unit = models.OneToOneField(UnitProfile, on_delete=models.CASCADE, related_name="project")
    goal = models.TextField()
    context = models.TextField(blank=True)
    data_used = models.TextField(blank=True)
    tasks = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"مشروع الوحدة {self.unit_id}"


class PedagogyNote(models.Model):
    """مبدأ تربوي عام من تمهيد الدليل، مثل قاعدة الطرائق الأربع. أساس لتحضير الدروس في المرحلة الثانية."""

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="pedagogy")
    slug = models.SlugField(max_length=48)
    title = models.CharField(max_length=120)
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["course_id", "order", "slug"]
        constraints = [models.UniqueConstraint(fields=["course", "slug"], name="unique_pedagogy_per_course")]

    def __str__(self) -> str:
        return self.title


class KnowledgeRelease(models.Model):
    """إصدار تحميل: ما حُمِّل لمقرر ولأي نسخة مخطط وبأي تجزئة محتوى. صف جديد حين تتغير التجزئة فقط."""

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="knowledge_releases")
    schema_version = models.PositiveSmallIntegerField()
    content_hash = models.CharField(max_length=64)
    report = models.JSONField(default=dict, blank=True)  # ما تغيّر في هذا التحميل
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["course", "-created_at"], name="knowledge_release_latest")]

    def __str__(self) -> str:
        return f"{self.course_id} {self.content_hash[:8]}"
