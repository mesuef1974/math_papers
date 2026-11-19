import pytest

# تجهيزات مشتركة في وحدات مستقلة (pytest لا يقبل pytest_plugins إلا في conftest الجذري)
pytest_plugins = ["apps.planning.tests.period_decks"]


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(username="staff", password="x" * 12, is_staff=True)


@pytest.fixture
def loaded_courses(db):
    """القاعدة كما في الإنتاج بعد preDeploy: التقاويم وكل المقررات ذات المصدر محمَّلة بالمحمِّل الواحد.

    الجداول مصدر القراءة الوحيد (الفهرس المشتق والخطة الفصلية والتقويم)، فكل اختبار يقرؤها يحتاج هذا التجهيز.
    """
    from apps.knowledge.services import load_all

    load_all()
