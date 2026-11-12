from django.db import models
from django.utils.translation import gettext_lazy as _


class ReconcileValidationRunSourceChoices(models.TextChoices):
    FILE_IMPORT = "FILE_IMPORT", _("File import")
    SUBMIT_FOR_REVIEW = "SUBMIT_FOR_REVIEW", _("Submit for review")
    VALIDATION_ISSUE_ACKNOWLEDGEMENT = "VALIDATION_ISSUE_ACKNOWLEDGEMENT", _("Validation issue acknowledgement")
    VALIDATION_ISSUE_REOPEN = "VALIDATION_ISSUE_REOPEN", _("Validation issue reopen")
