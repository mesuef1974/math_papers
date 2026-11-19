"""لوحة اقتراحات المعلمين لنصوص الأهداف (`docs/teacher_objective_review_plan.md`، جانب المالك).

يرى المالك النص المعتمد والمقترح متجاورين ويقبل أو يرفض بملاحظة؛ القرار عبر `services.decide_suggestion` وحدها
(الصلاحية والنهائية وسجل التدقيق). القبول لا يكتب ملف الوحدة: ذلك أمر `apply_objective_suggestions` ثم طلب دمج.
"""

from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from . import selectors, services
from .models import ObjectiveSuggestion

DECIDE = "planning.decide_objective_suggestion"
STATUS_LABELS = {
    ObjectiveSuggestion.PENDING: "قيد المراجعة",
    ObjectiveSuggestion.ACCEPTED: "مقبول (لم يُطبَّق)",
    ObjectiveSuggestion.REJECTED: "مرفوض",
    "applied": "مُطبَّق",
}


class SuggestionDecisionForm(forms.ModelForm):
    verdict = forms.ChoiceField(
        label="القرار",
        required=False,
        choices=[
            ("", "—"),
            (ObjectiveSuggestion.ACCEPTED, "قبول"),
            (ObjectiveSuggestion.REJECTED, "رفض"),
        ],
        help_text="القرار نهائي. القبول لا يغيّر ملف الوحدة حتى يُشغَّل أمر التطبيق ويُدمج طلبه.",
    )

    class Meta:
        model = ObjectiveSuggestion
        fields = ["decision_note"]
        labels = {"decision_note": "ملاحظة القرار"}

    def clean(self):
        data = super().clean()
        if data.get("verdict") and self.instance.decision != ObjectiveSuggestion.PENDING:
            raise forms.ValidationError("قُرِّر هذا الاقتراح من قبل")
        if data.get("decision_note") and not data.get("verdict"):
            raise forms.ValidationError("الملاحظة تُكتب مع القرار")
        return data


@admin.register(ObjectiveSuggestion)
class ObjectiveSuggestionAdmin(admin.ModelAdmin):
    form = SuggestionDecisionForm
    list_display = ("lesson_label", "example", "owner", "status_label", "created_at")
    list_filter = ("decision", "lesson__course", "lesson")
    search_fields = ("lesson__code", "owner__username", "condition", "criterion")
    list_select_related = ("lesson__course", "owner")
    actions = ["accept_selected", "reject_selected"]
    readonly_fields = (
        "comparison",
        "owner",
        "lesson",
        "example",
        "note",
        "status_label",
        "decided_by",
        "decided_at",
        "created_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("lesson__course", "owner", "decided_by")

    def get_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None and obj.decision == ObjectiveSuggestion.PENDING:
            fields += ["verdict", "decision_note"]
        else:
            fields.append("decision_note")
        return fields

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.decision != ObjectiveSuggestion.PENDING:
            return (*self.readonly_fields, "decision_note")
        return self.readonly_fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm(DECIDE)

    @admin.display(description="الدرس", ordering="lesson__code")
    def lesson_label(self, obj: ObjectiveSuggestion) -> str:
        return f"{obj.lesson.course.slug} · {obj.lesson.code}"

    @admin.display(description="الحالة")
    def status_label(self, obj: ObjectiveSuggestion) -> str:
        return STATUS_LABELS[selectors.suggestion_review(obj).status]

    @admin.display(description="المعتمد والمقترح")
    def comparison(self, obj: ObjectiveSuggestion) -> str:
        review = selectors.suggestion_review(obj)
        if review.shared is None:
            return "لا هدف لهذا المثال في ملف الوحدة الآن"
        behavior, condition, criterion = review.shared
        rows = format_html_join(
            "",
            "<tr><th scope='row'>{}</th><td>{}</td><td>{}</td></tr>",
            [
                ("السلوك", behavior, behavior),
                ("الشرط", condition, obj.condition),
                ("المعيار", criterion, obj.criterion),
            ],
        )
        warning = (
            format_html("<p>تغيّر النص المعتمد بعد كتابة الاقتراح؛ أمر التطبيق يتخطّاه.</p>")
            if review.stale and review.status != "applied"
            else ""
        )
        return format_html(
            "{}<table><thead><tr><th></th><th scope='col'>المعتمد الحالي</th>"
            "<th scope='col'>المقترح</th></tr></thead><tbody>{}</tbody></table>",
            warning,
            rows,
        )

    def save_model(self, request, obj, form, change):
        verdict = form.cleaned_data.get("verdict")
        if verdict:
            services.decide_suggestion(request.user, obj.pk, verdict, form.cleaned_data.get("decision_note"))

    def _decide_all(self, request, queryset, decision: str) -> None:
        pending = list(queryset.filter(decision=ObjectiveSuggestion.PENDING).values_list("pk", flat=True))
        done, skipped = 0, queryset.count() - len(pending)
        for pk in pending:
            try:
                services.decide_suggestion(request.user, pk, decision)
                done += 1
            except services.SuggestionDecidedError:
                skipped += 1
        self.message_user(request, f"قُرِّر {done} اقتراحًا", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"تُخطّي {skipped} اقتراحًا قُرِّر من قبل", messages.WARNING)

    @admin.action(description="قبول الاقتراحات المحددة", permissions=["change"])
    def accept_selected(self, request, queryset):
        self._decide_all(request, queryset, ObjectiveSuggestion.ACCEPTED)

    @admin.action(description="رفض الاقتراحات المحددة", permissions=["change"])
    def reject_selected(self, request, queryset):
        self._decide_all(request, queryset, ObjectiveSuggestion.REJECTED)
