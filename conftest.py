import pytest


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(username="staff", password="x" * 12, is_staff=True)
