from django import forms
from django.utils.translation import gettext_lazy as _

from apps.shared.widgets import ToolbarFilterSelectWidget, ToolbarSearchInputWidget

STATUS_CHOICES = (
    ("open", _("Open")),
    ("answered", _("Answered")),
    ("resolved", _("Resolved")),
    ("closed", _("Closed")),
    ("cancelled", _("Cancelled")),
)
SEVERITY_CHOICES = (
    ("minor", _("Minor")),
    ("major", _("Major")),
    ("critical", _("Critical")),
)
SOURCE_CHOICES = (
    ("manual", _("Manual")),
    ("system", _("System")),
    ("import", _("Import")),
    ("validation_issues", _("Validation Issues")),
)


class QueryWorkbenchFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        label=_("Search"),
        widget=ToolbarSearchInputWidget(
            attrs={"placeholder": _("Search subject, screening or randomization code...")},
            aria_label=_("Search by subject, screening or randomization code"),
        ),
    )
    status = forms.ChoiceField(
        required=False,
        label=_("Status"),
        choices=(("", _("All statuses")),) + STATUS_CHOICES,
        widget=ToolbarFilterSelectWidget(
            filter_label=_("Status:"),
            aria_label=_("Filter queries by status"),
        ),
    )
    severity = forms.ChoiceField(
        required=False,
        label=_("Severity"),
        choices=(("", _("All severities")),) + SEVERITY_CHOICES,
        widget=ToolbarFilterSelectWidget(
            filter_label=_("Severity:"),
            aria_label=_("Filter queries by severity"),
        ),
    )
    source = forms.ChoiceField(
        required=False,
        label=_("Source"),
        choices=(("", _("All sources")),) + SOURCE_CHOICES,
        widget=ToolbarFilterSelectWidget(
            filter_label=_("Source:"),
            aria_label=_("Filter queries by source"),
        ),
    )
    blocking = forms.ChoiceField(
        required=False,
        label=_("Blocking"),
        choices=(
            ("", _("All")),
            ("yes", _("Blocking")),
            ("no", _("Non-blocking")),
        ),
        widget=ToolbarFilterSelectWidget(
            filter_label=_("Blocking:"),
            aria_label=_("Filter blocking queries"),
        ),
    )
    assigned_to_me = forms.BooleanField(
        required=False,
        label=_("Assigned To Me"),
        widget=forms.CheckboxInput(attrs={"class": "query-workbench__toolbar-checkbox-input"}),
    )
    opened_by_me = forms.BooleanField(
        required=False,
        label=_("Opened by Me"),
        widget=forms.CheckboxInput(attrs={"class": "query-workbench__toolbar-checkbox-input"}),
    )


__all__ = ["QueryWorkbenchFilterForm"]
