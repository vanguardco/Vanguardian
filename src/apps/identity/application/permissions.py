from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    app_label: str
    codename: str
    label: str

    @property
    def permission_code(self):
        if "." in self.codename and self.codename == self.codename.upper():
            return self.codename
        return f"{self.app_label}.{self.codename}"


APP_PERMISSION_DEFINITIONS = (
    PermissionDefinition("dashboard", "view_dashboard", "Can view dashboard"),
    PermissionDefinition("identity", "create_user", "Can create user"),
    PermissionDefinition("identity", "delete_user", "Can delete user"),
    PermissionDefinition("identity", "restore_user", "Can restore user"),
    PermissionDefinition("identity", "update_user", "Can update user"),
    PermissionDefinition("identity", "view_user_detail", "Can view user detail"),
    PermissionDefinition("identity", "view_user_list", "Can view user list"),
    PermissionDefinition("reconcile", "answer_dataquery", "Can answer data queries"),
    PermissionDefinition("reconcile", "close_dataquery", "Can close data queries"),
    PermissionDefinition("reconcile", "reopen_dataquery", "Can reopen data queries"),
    PermissionDefinition("reconcile", "resolve_dataquery", "Can resolve data queries"),
    PermissionDefinition("reconcile", "view_dataquery", "Can view data queries"),
    PermissionDefinition(
        "reconcile",
        "view_internal_query_thread",
        "Can view internal query thread messages",
    ),
    PermissionDefinition("site", "create_site", "Can create site"),
    PermissionDefinition("site", "create_site_membership", "Can create site membership"),
    PermissionDefinition("site", "delete_site", "Can delete site"),
    PermissionDefinition("site", "delete_site_membership", "Can delete site membership"),
    PermissionDefinition("site", "update_site", "Can update site"),
    PermissionDefinition("site", "update_site_membership", "Can update site membership"),
    PermissionDefinition("site", "view_site_detail", "Can view site detail"),
    PermissionDefinition("site", "view_site_list", "Can view site list"),
    PermissionDefinition(
        "site",
        "view_site_membership_detail",
        "Can view site membership detail",
    ),
    PermissionDefinition(
        "site",
        "view_site_membership_history",
        "Can view site membership audit history",
    ),
    PermissionDefinition(
        "site",
        "view_site_membership_list",
        "Can view site membership list",
    ),
    PermissionDefinition(
        "study",
        "assess_subject_eligibility",
        "Can assess subject eligibility",
    ),
    PermissionDefinition(
        "study",
        "change_study_status",
        "Can activate or deactivate a study",
    ),
    PermissionDefinition("study", "create_study", "Can create study"),
    PermissionDefinition(
        "study",
        "create_study_eventdefinition",
        "Can create/import study event definitions",
    ),
    PermissionDefinition("study", "delete_study", "Can delete study"),
    PermissionDefinition(
        "study",
        "delete_study_eventdefinition",
        "Can delete study event definition",
    ),
    PermissionDefinition(
        "study",
        "filter_study_by_code",
        "Can filter studies by code",
    ),
    PermissionDefinition(
        "study",
        "filter_study_by_status",
        "Can filter studies by status",
    ),
    PermissionDefinition(
        "study",
        "finalize_subject_eligibility",
        "Can finalize subject eligibility",
    ),
    PermissionDefinition(
        "study",
        "manage_crf_template",
        "Can manage CRF templates and field definitions",
    ),
    PermissionDefinition(
        "study",
        "override_subject_eligibility",
        "Can override subject eligibility",
    ),
    PermissionDefinition(
        "study",
        "retract_subject_eligibility",
        "Can retract subject eligibility",
    ),
    PermissionDefinition(
        "study",
        "search_study_by_name",
        "Can search studies by name",
    ),
    PermissionDefinition("study", "update_study", "Can update study"),
    PermissionDefinition(
        "study",
        "update_study_eventdefinition",
        "Can update study event definition",
    ),
    PermissionDefinition(
        "study",
        "update_study_field_code",
        "Can update study code field",
    ),
    PermissionDefinition(
        "study",
        "update_study_field_dates",
        "Can update study start/end date fields",
    ),
    PermissionDefinition(
        "study",
        "update_study_field_description",
        "Can update study description field",
    ),
    PermissionDefinition(
        "study",
        "update_study_field_name",
        "Can update study name field",
    ),
    PermissionDefinition(
        "study",
        "update_study_field_sponsor",
        "Can update study sponsor field",
    ),
    PermissionDefinition(
        "study",
        "view_study_detail",
        "Can view study detail",
    ),
    PermissionDefinition(
        "study",
        "view_study_eventdefinition_list",
        "Can view study event definition list",
    ),
    PermissionDefinition(
        "study",
        "view_study_field_code",
        "Can view study code field",
    ),
    PermissionDefinition(
        "study",
        "view_study_field_dates",
        "Can view study start/end date fields",
    ),
    PermissionDefinition(
        "study",
        "view_study_field_description",
        "Can view study description field",
    ),
    PermissionDefinition(
        "study",
        "view_study_field_name",
        "Can view study name field",
    ),
    PermissionDefinition(
        "study",
        "view_study_field_sponsor",
        "Can view study sponsor field",
    ),
    PermissionDefinition("study", "view_study_history", "Can view study audit history"),
    PermissionDefinition("study", "view_study_list", "Can view study list"),
    PermissionDefinition("subject", "create_subject", "Can create subject"),
    PermissionDefinition("subject", "delete_subject", "Can delete subject"),
    PermissionDefinition(
        "subject",
        "update_subject",
        "Can update subject and trigger workflow actions",
    ),
    PermissionDefinition("subject", "verify_form", "Can verify form / quality check"),
    PermissionDefinition(
        "subject",
        "view_subject_detail",
        "Can view subject detail and enter data",
    ),
    PermissionDefinition("subject", "view_subject_list", "Can view subject list"),
)


APP_PERMISSION_LABELS = {definition.permission_code: definition.label for definition in APP_PERMISSION_DEFINITIONS}


EDC_PERMISSION_LABELS = {
    "SUBJECT.VIEW": "View subjects",
    "SUBJECT.CREATE": "Create subjects",
    "SUBJECT.UPDATE": "Update subjects",
    "SUBJECT.PERIOD_OVERRIDE": "Override subject treatment period transition",
    "SUBJECT.SCREEN": "Screen subjects",
    "SUBJECT.ENROLL": "Enroll subjects",
    "SUBJECT.RANDOMIZE": "Randomize subjects",
    "SUBJECT.EARLY_TERMINATE": "Start subject early termination",
    "RANDOMIZATION.LIST.VIEW": "View concealed randomization master lists",
    "RANDOMIZATION.LIST.MANAGE": "Import and approve randomization master lists",
    "RANDOMIZATION.ASSIGNMENT.VIEW": "View assigned subject treatment and kit",
    "CRF.VIEW": "View CRF data",
    "CRF.ENTER": "Enter CRF data",
    "CRF.UPDATE": "Update CRF data",
    "CRF.SUBMIT": "Submit CRF data",
    "CRF.REOPEN": "Reopen CRF data",
    "VALIDATION_ISSUE.VIEW": "View validation issues",
    "VALIDATION_ISSUE.ACKNOWLEDGE": "Acknowledge validation issues",
    "VALIDATION_ISSUE.REOPEN": "Reopen acknowledged validation issues",
    "QUERY.VIEW": "View data queries",
    "QUERY.CREATE": "Create data queries",
    "QUERY.RESPOND": "Respond to data queries",
    "QUERY.CLOSE": "Close data queries",
    "QUERY.RETURN": "Return data queries",
    "QUERY.REOPEN": "Reopen resolved or closed data queries",
    "QUERY.CANCEL": "Cancel data queries",
    "SDV.VIEW": "View SDV",
    "SDV.MARK": "Mark SDV",
    "SDR.MARK": "Mark SDR",
    "EVENT_REVIEW.COMPLETE": "Complete event review",
    "EVENT_CERTIFICATION.CERTIFY": "Certify event data",
    "EVENT_ATTESTATION.REVOKE": "Revoke event review/certification",
    "AE.VIEW": "View adverse events",
    "AE.ENTER": "Enter adverse events",
    "AE.MEDICAL_ASSESS": "Perform AE medical assessment",
    "SAE.REPORT": "Report SAE",
    "CASEBOOK.VIEW": "View casebook",
    "CASEBOOK.SIGN": "Sign casebook",
    "DATA.FREEZE": "Freeze data",
    "DATA.UNFREEZE": "Unfreeze data",
    "DATA.LOCK": "Lock data",
    "DATA.UNLOCK": "Unlock data",
    "STUDY_CONFIG.VIEW": "View study configuration",
    "STUDY_CONFIG.MANAGE": "Manage study configuration",
    "USER_ACCESS.VIEW": "View user access",
    "USER_ACCESS.MANAGE": "Manage user access",
    "DELEGATION.VIEW": "View delegation",
    "DELEGATION.MANAGE": "Manage delegation",
    "AUDIT_TRAIL.VIEW": "View audit trail",
    "DATA_EXPORT.RUN": "Run data export",
}


EDC_PERMISSION_DEFINITIONS = tuple(PermissionDefinition("edc", codename, label) for codename, label in EDC_PERMISSION_LABELS.items())


ALL_PERMISSION_DEFINITIONS = APP_PERMISSION_DEFINITIONS + EDC_PERMISSION_DEFINITIONS


__all__ = [
    "ALL_PERMISSION_DEFINITIONS",
    "APP_PERMISSION_DEFINITIONS",
    "APP_PERMISSION_LABELS",
    "EDC_PERMISSION_DEFINITIONS",
    "EDC_PERMISSION_LABELS",
    "PermissionDefinition",
]
