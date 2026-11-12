from django.test import SimpleTestCase

from apps.identity.application.permissions import (
    ALL_PERMISSION_DEFINITIONS,
    APP_PERMISSION_DEFINITIONS,
    EDC_PERMISSION_DEFINITIONS,
)


class PermissionRegistryTests(SimpleTestCase):
    def test_app_permission_registry_has_unique_codes(self):
        permission_codes = [definition.permission_code for definition in APP_PERMISSION_DEFINITIONS]

        self.assertEqual(len(permission_codes), len(set(permission_codes)))

    def test_app_permission_registry_contains_used_permission_codes(self):
        permission_codes = {definition.permission_code for definition in ALL_PERMISSION_DEFINITIONS}
        permission_codes.update({definition.permission_code for definition in APP_PERMISSION_DEFINITIONS})

        self.assertTrue(
            {
                "dashboard.view_dashboard",
                "USER_ACCESS.VIEW",
                "USER_ACCESS.MANAGE",
                "site.view_site_membership_list",
                "STUDY_CONFIG.MANAGE",
                "study.update_study_field_name",
                "SDV.MARK",
                "QUERY.REOPEN",
                "VALIDATION_ISSUE.REOPEN",
                "reconcile.view_internal_query_thread",
            }.issubset(permission_codes)
        )

    def test_permission_registry_includes_edc_permissions(self):
        edc_permission_codes = {definition.codename for definition in EDC_PERMISSION_DEFINITIONS}
        all_permission_codes = {definition.permission_code for definition in ALL_PERMISSION_DEFINITIONS}

        self.assertIn("DATA.LOCK", edc_permission_codes)
        self.assertIn("DATA.LOCK", all_permission_codes)
