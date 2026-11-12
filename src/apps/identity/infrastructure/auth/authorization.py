from dataclasses import dataclass, field
from datetime import datetime

from django.utils import timezone

from apps.audit.public import AuditContextAdapter
from apps.identity.models import (
    DelegationOfAuthority,
    DelegationTask,
    IdentityPermission,
    MembershipStatus,
    Role,
    RoleAssignmentStatus,
    RoleScopeLevel,
    StudyMembership,
    StudyMembershipRole,
    StudySiteMembership,
    StudySiteMembershipRole,
    TrainingCompletion,
    TrainingRequirement,
    User,
)

MUTATING_PERMISSION_PREFIXES = (
    "SUBJECT.CREATE",
    "SUBJECT.UPDATE",
    "SUBJECT.SCREEN",
    "SUBJECT.ENROLL",
    "SUBJECT.RANDOMIZE",
    "CRF.ENTER",
    "CRF.UPDATE",
    "CRF.SUBMIT",
    "QUERY.CREATE",
    "QUERY.RESPOND",
    "QUERY.CLOSE",
    "QUERY.RETURN",
    "QUERY.REOPEN",
    "QUERY.CANCEL",
    "VALIDATION_ISSUE.ACKNOWLEDGE",
    "VALIDATION_ISSUE.REOPEN",
    "EVENT_REVIEW.COMPLETE",
    "EVENT_CERTIFICATION.CERTIFY",
    "EVENT_ATTESTATION.REVOKE",
    "AE.ENTER",
    "AE.MEDICAL_ASSESS",
    "SAE.REPORT",
    "CASEBOOK.SIGN",
    "DATA.FREEZE",
    "DATA.UNFREEZE",
    "DATA.LOCK",
    "DATA.UNLOCK",
)

DELEGATION_TASK_BY_PERMISSION = {
    "CRF.ENTER": "DATA_ENTRY",
    "CRF.SUBMIT": "DATA_ENTRY",
    "QUERY.RESPOND": "QUERY_RESPONSE",
    "AE.MEDICAL_ASSESS": "AE_ASSESSMENT",
    "SAE.REPORT": "SAE_REPORTING",
    "CASEBOOK.SIGN": "CASEBOOK_SIGN",
    "SUBJECT.RANDOMIZE": "RANDOMIZATION",
}


@dataclass(frozen=True)
class ResourceContext:
    study_id: int
    study_site_id: int | None = None
    subject_id: int | None = None
    visit_instance_id: int | None = None
    form_instance_id: int | None = None
    field_instance_id: int | None = None
    form_status: str | None = None
    is_frozen: bool = False
    is_locked: bool = False
    is_signed: bool = False
    is_blinded_resource: bool = False
    query_status: str | None = None


@dataclass(frozen=True)
class EffectivePermissionSet:
    user_id: int
    study_id: int
    study_site_id: int | None
    permission_codes: frozenset[str] = field(default_factory=frozenset)
    role_codes: frozenset[str] = field(default_factory=frozenset)
    membership_ids: frozenset[int] = field(default_factory=frozenset)
    matched_scope: str | None = None


@dataclass(frozen=True)
class AuthorizationResult:
    is_allowed: bool
    deny_reason_code: str | None = None
    deny_reason_message: str = ""
    matched_permission_codes: tuple[str, ...] = ()
    matched_role_codes: tuple[str, ...] = ()
    matched_scope: str | None = None

    @classmethod
    def allow(cls, effective_permissions: EffectivePermissionSet):
        return cls(
            is_allowed=True,
            matched_permission_codes=tuple(sorted(effective_permissions.permission_codes)),
            matched_role_codes=tuple(sorted(effective_permissions.role_codes)),
            matched_scope=effective_permissions.matched_scope,
        )

    @classmethod
    def deny(cls, code, message="", effective_permissions=None):
        effective_permissions = effective_permissions or EffectivePermissionSet(
            user_id=0,
            study_id=0,
            study_site_id=None,
        )
        return cls(
            is_allowed=False,
            deny_reason_code=code,
            deny_reason_message=message,
            matched_permission_codes=tuple(sorted(effective_permissions.permission_codes)),
            matched_role_codes=tuple(sorted(effective_permissions.role_codes)),
            matched_scope=effective_permissions.matched_scope,
        )


@dataclass(frozen=True)
class PolicyDecision:
    is_allowed: bool
    deny_reason_code: str | None = None
    deny_reason_message: str = ""

    @classmethod
    def allow(cls):
        return cls(is_allowed=True)

    @classmethod
    def deny(cls, code, message=""):
        return cls(is_allowed=False, deny_reason_code=code, deny_reason_message=message)


@dataclass(frozen=True)
class AuditEventInput:
    action: str
    object_type: str
    object_id: str
    old_value_json: object = None
    new_value_json: object = None
    performed_by_id: int | None = None
    ip_address: str | None = None
    user_agent: str = ""


class EffectivePermissionResolver:
    def resolve(self, *, user_id: int, study_id: int, study_site_id: int | None = None):
        now = timezone.now()
        permission_codes = set()
        role_codes = set()
        membership_ids = set()
        matched_scopes = []

        study_membership = self._active_study_membership(user_id=user_id, study_id=study_id, now=now)
        if study_membership:
            membership_ids.add(study_membership.pk)
            study_roles = self._active_study_roles(study_membership_id=study_membership.pk)
            self._collect_role_permissions(study_roles, permission_codes, role_codes)
            if study_roles:
                matched_scopes.append(RoleScopeLevel.STUDY)

        if study_site_id is not None:
            site_membership = self._active_site_membership(
                user_id=user_id,
                study_id=study_id,
                study_site_id=study_site_id,
                now=now,
            )
            if site_membership:
                membership_ids.add(site_membership.pk)
                site_roles = self._active_site_roles(study_site_membership_id=site_membership.pk)
                self._collect_role_permissions(site_roles, permission_codes, role_codes)
                if site_roles:
                    matched_scopes.append(RoleScopeLevel.STUDY_SITE)

        return EffectivePermissionSet(
            user_id=user_id,
            study_id=study_id,
            study_site_id=study_site_id,
            permission_codes=frozenset(permission_codes),
            role_codes=frozenset(role_codes),
            membership_ids=frozenset(membership_ids),
            matched_scope="+".join(matched_scopes) or None,
        )

    def has_active_study_membership(self, *, user_id: int, study_id: int):
        return (
            self._active_study_membership(
                user_id=user_id,
                study_id=study_id,
                now=timezone.now(),
            )
            is not None
        )

    def has_active_site_membership(self, *, user_id: int, study_id: int, study_site_id: int):
        return (
            self._active_site_membership(
                user_id=user_id,
                study_id=study_id,
                study_site_id=study_site_id,
                now=timezone.now(),
            )
            is not None
        )

    def _active_study_membership(self, *, user_id: int, study_id: int, now: datetime):
        return (
            StudyMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__isnull=True)
            .filter(valid_to__isnull=True)
            .first()
            or StudyMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__lte=now, valid_to__isnull=True)
            .first()
            or StudyMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__isnull=True, valid_to__gt=now)
            .first()
            or StudyMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__lte=now, valid_to__gt=now)
            .first()
        )

    def _active_site_membership(self, *, user_id: int, study_id: int, study_site_id: int, now: datetime):
        return (
            StudySiteMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                site_id=study_site_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__isnull=True)
            .filter(valid_to__isnull=True)
            .first()
            or StudySiteMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                site_id=study_site_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__lte=now, valid_to__isnull=True)
            .first()
            or StudySiteMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                site_id=study_site_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__isnull=True, valid_to__gt=now)
            .first()
            or StudySiteMembership.objects.filter(
                user_id=user_id,
                study_id=study_id,
                site_id=study_site_id,
                deleted=False,
                status=MembershipStatus.ACTIVE,
            )
            .filter(valid_from__lte=now, valid_to__gt=now)
            .first()
        )

    def _active_study_roles(self, *, study_membership_id: int):
        return [
            assignment.role
            for assignment in StudyMembershipRole.objects.select_related("role")
            .filter(study_membership_id=study_membership_id, status=RoleAssignmentStatus.ACTIVE)
            .filter(role__scope_level=RoleScopeLevel.STUDY, role__is_active=True)
        ]

    def _active_site_roles(self, *, study_site_membership_id: int):
        return [
            assignment.role
            for assignment in StudySiteMembershipRole.objects.select_related("role")
            .filter(study_site_membership_id=study_site_membership_id, status=RoleAssignmentStatus.ACTIVE)
            .filter(role__scope_level=RoleScopeLevel.STUDY_SITE, role__is_active=True)
        ]

    def _collect_role_permissions(self, roles, permission_codes, role_codes):
        for role in roles:
            role_codes.add(role.code or role.name.upper().replace(" ", "_"))
            for permission in role.permissions.all():
                permission_codes.add(permission_code_for(permission))


class ResourceStatePolicy:
    def evaluate(self, *, permission_code: str, resource_context: ResourceContext):
        normalized_code = normalize_permission_code(permission_code)
        if not self._is_mutating_permission(normalized_code):
            return PolicyDecision.allow()
        if resource_context.is_locked:
            return PolicyDecision.deny("FORM_LOCKED", "The form is locked.")
        if resource_context.is_frozen:
            return PolicyDecision.deny("FORM_FROZEN", "The form is frozen.")
        if resource_context.is_signed:
            return PolicyDecision.deny("FORM_SIGNED", "The form is signed.")
        return PolicyDecision.allow()

    @staticmethod
    def _is_mutating_permission(permission_code: str):
        return any(permission_code == prefix for prefix in MUTATING_PERMISSION_PREFIXES)


class DelegationPolicy:
    def evaluate(self, *, user_id: int, permission_code: str, resource_context: ResourceContext):
        normalized_code = normalize_permission_code(permission_code)
        task_code = DELEGATION_TASK_BY_PERMISSION.get(normalized_code)
        task = self._configured_task(normalized_code, task_code)
        if task is None:
            return PolicyDecision.allow()
        if resource_context.study_site_id is None:
            return PolicyDecision.deny("DELEGATION_REQUIRED", "Delegation requires a study-site context.")
        if self._has_active_delegation(
            user_id=user_id,
            study_site_id=resource_context.study_site_id,
            task_code=task.code,
        ):
            return PolicyDecision.allow()
        return PolicyDecision.deny("DELEGATION_REQUIRED", "Active delegation is required.")

    def _configured_task(self, permission_code, task_code):
        queryset = DelegationTask.objects.filter(is_active=True)
        return queryset.filter(required_permission_code=permission_code).first() or (queryset.filter(code=task_code).first() if task_code else None)

    def _has_active_delegation(self, *, user_id: int, study_site_id: int, task_code: str):
        now = timezone.now()
        queryset = DelegationOfAuthority.objects.filter(
            user_id=user_id,
            study_site_id=study_site_id,
            task_code=task_code,
            status="ACTIVE",
        )
        return (
            queryset.filter(valid_from__isnull=True, valid_to__isnull=True).exists()
            or queryset.filter(
                valid_from__lte=now,
                valid_to__isnull=True,
            ).exists()
            or queryset.filter(
                valid_from__isnull=True,
                valid_to__gt=now,
            ).exists()
            or queryset.filter(
                valid_from__lte=now,
                valid_to__gt=now,
            ).exists()
        )


class TrainingPolicy:
    def evaluate(self, *, user_id: int, permission_code: str, resource_context: ResourceContext):
        normalized_code = normalize_permission_code(permission_code)
        task_code = DELEGATION_TASK_BY_PERMISSION.get(normalized_code, "")
        requirements = TrainingRequirement.objects.filter(
            study_id=resource_context.study_id,
            is_active=True,
        ).filter(permission_code__in=("", normalized_code), task_code__in=("", task_code))
        requirement = requirements.exclude(training_code="").first()
        if requirement is None:
            return PolicyDecision.allow()
        if self._has_current_completion(
            user_id=user_id,
            study_id=resource_context.study_id,
            training_code=requirement.training_code,
        ):
            return PolicyDecision.allow()
        return PolicyDecision.deny("TRAINING_REQUIRED", "Current training completion is required.")

    def _has_current_completion(self, *, user_id: int, study_id: int, training_code: str):
        now = timezone.now()
        return (
            TrainingCompletion.objects.filter(
                user_id=user_id,
                study_id=study_id,
                training_code=training_code,
            )
            .filter(expires_at__isnull=True)
            .exists()
            or TrainingCompletion.objects.filter(
                user_id=user_id,
                study_id=study_id,
                training_code=training_code,
                expires_at__gt=now,
            ).exists()
        )


class AuditWriter:
    def __init__(self, audit_context_adapter=None):
        self.audit_context_adapter = audit_context_adapter or AuditContextAdapter()

    def write(self, audit_event_input: AuditEventInput):
        return self.audit_context_adapter.record_event(
            action=audit_event_input.action,
            object_type=audit_event_input.object_type,
            object_id=audit_event_input.object_id,
            before_data=audit_event_input.old_value_json,
            after_data=audit_event_input.new_value_json,
            actor_user_id=audit_event_input.performed_by_id,
            ip_address=audit_event_input.ip_address,
            user_agent=audit_event_input.user_agent,
        )


class AccessControlMutationService:
    def __init__(self, audit_writer=None):
        self.audit_writer = audit_writer or AuditWriter()

    def assign_study_role(self, *, study_membership_id: int, role_id: int, actor_user_id: int | None = None):
        assignment, _ = StudyMembershipRole.objects.update_or_create(
            study_membership_id=study_membership_id,
            role_id=role_id,
            defaults={
                "assigned_at": timezone.now(),
                "assigned_by_id": actor_user_id,
                "revoked_at": None,
                "revoked_by_id": None,
                "status": RoleAssignmentStatus.ACTIVE,
            },
        )
        self.audit_writer.write(
            AuditEventInput(
                action="identity.role_assigned",
                object_type="study_membership_role",
                object_id=str(assignment.pk),
                new_value_json={
                    "study_membership_id": study_membership_id,
                    "role_id": role_id,
                    "status": RoleAssignmentStatus.ACTIVE,
                },
                performed_by_id=actor_user_id,
            ),
        )
        return assignment

    def assign_study_site_role(
        self,
        *,
        study_site_membership_id: int,
        role_id: int,
        actor_user_id: int | None = None,
    ):
        assignment, _ = StudySiteMembershipRole.objects.update_or_create(
            study_site_membership_id=study_site_membership_id,
            role_id=role_id,
            defaults={
                "assigned_at": timezone.now(),
                "assigned_by_id": actor_user_id,
                "revoked_at": None,
                "revoked_by_id": None,
                "status": RoleAssignmentStatus.ACTIVE,
            },
        )
        self.audit_writer.write(
            AuditEventInput(
                action="identity.role_assigned",
                object_type="study_site_membership_role",
                object_id=str(assignment.pk),
                new_value_json={
                    "study_site_membership_id": study_site_membership_id,
                    "role_id": role_id,
                    "status": RoleAssignmentStatus.ACTIVE,
                },
                performed_by_id=actor_user_id,
            ),
        )
        return assignment

    def revoke_study_site_role(self, *, assignment_id: int, actor_user_id: int | None = None):
        assignment = StudySiteMembershipRole.objects.get(pk=assignment_id)
        before_data = {"status": assignment.status, "role_id": assignment.role_id}
        assignment.status = RoleAssignmentStatus.REVOKED
        assignment.revoked_at = timezone.now()
        assignment.revoked_by_id = actor_user_id
        assignment.save(update_fields=["status", "revoked_at", "revoked_by_id"])
        self.audit_writer.write(
            AuditEventInput(
                action="identity.role_revoked",
                object_type="study_site_membership_role",
                object_id=str(assignment.pk),
                old_value_json=before_data,
                new_value_json={"status": assignment.status, "role_id": assignment.role_id},
                performed_by_id=actor_user_id,
            ),
        )
        return assignment

    def add_permission_to_role(self, *, role_id: int, permission_code: str, actor_user_id: int | None = None):
        role = Role.objects.get(pk=role_id)
        permission = get_permission_by_code(permission_code)
        role.permissions.add(permission)
        self.audit_writer.write(
            AuditEventInput(
                action="identity.role_permission_added",
                object_type="identity_role",
                object_id=str(role.pk),
                new_value_json={"role_id": role.pk, "permission_code": normalize_permission_code(permission_code)},
                performed_by_id=actor_user_id,
            ),
        )
        return role


class AuthorizationService:
    def __init__(
        self,
        *,
        effective_permission_resolver=None,
        resource_state_policy=None,
        delegation_policy=None,
        training_policy=None,
    ):
        self.effective_permission_resolver = effective_permission_resolver or EffectivePermissionResolver()
        self.resource_state_policy = resource_state_policy or ResourceStatePolicy()
        self.delegation_policy = delegation_policy or DelegationPolicy()
        self.training_policy = training_policy or TrainingPolicy()

    def can_perform(self, *, user_id: int, permission_code: str, resource_context: ResourceContext):
        user = User.objects.filter(pk=user_id, is_active=True, deleted=False).first()
        if user is None:
            return AuthorizationResult.deny("USER_INACTIVE", "The user account is inactive.")
        if not permission_exists(permission_code):
            return AuthorizationResult.deny("PERMISSION_NOT_FOUND", "The permission code is not registered.")
        if not self.effective_permission_resolver.has_active_study_membership(
            user_id=user_id,
            study_id=resource_context.study_id,
        ):
            return AuthorizationResult.deny(
                "NO_ACTIVE_STUDY_MEMBERSHIP",
                "No active study membership was found.",
            )

        effective_permissions = self.effective_permission_resolver.resolve(
            user_id=user_id,
            study_id=resource_context.study_id,
            study_site_id=resource_context.study_site_id,
        )
        normalized_code = normalize_permission_code(permission_code)
        if normalized_code not in effective_permissions.permission_codes:
            if not effective_permissions.role_codes:
                return AuthorizationResult.deny(
                    "ROLE_NOT_ASSIGNED",
                    "No active role assignment was found for this scope.",
                    effective_permissions,
                )
            if resource_context.study_site_id is not None and not self.effective_permission_resolver.has_active_site_membership(
                user_id=user_id,
                study_id=resource_context.study_id,
                study_site_id=resource_context.study_site_id,
            ):
                return AuthorizationResult.deny(
                    "NO_ACTIVE_STUDY_SITE_MEMBERSHIP",
                    "No active study-site membership was found.",
                    effective_permissions,
                )
            return AuthorizationResult.deny(
                "PERMISSION_NOT_GRANTED",
                "The permission is not granted in this resource scope.",
                effective_permissions,
            )

        for decision in (
            self.resource_state_policy.evaluate(
                permission_code=normalized_code,
                resource_context=resource_context,
            ),
            self.delegation_policy.evaluate(
                user_id=user_id,
                permission_code=normalized_code,
                resource_context=resource_context,
            ),
            self.training_policy.evaluate(
                user_id=user_id,
                permission_code=normalized_code,
                resource_context=resource_context,
            ),
        ):
            if not decision.is_allowed:
                return AuthorizationResult.deny(
                    decision.deny_reason_code,
                    decision.deny_reason_message,
                    effective_permissions,
                )

        if resource_context.is_blinded_resource:
            return AuthorizationResult.deny(
                "BLINDING_RESTRICTED",
                "The resource is blinded.",
                effective_permissions,
            )
        return AuthorizationResult.allow(effective_permissions)


def permission_exists(permission_code: str):
    return get_permission_by_code(permission_code) is not None


def get_permission_by_code(permission_code: str):
    normalized_code = normalize_permission_code(permission_code)
    permission = IdentityPermission.objects.filter(codename=normalized_code).first()
    if permission is not None:
        return permission
    if "." not in normalized_code:
        return None
    app_label, codename = normalized_code.split(".", 1)
    return IdentityPermission.objects.filter(
        app_label=app_label,
        codename=codename,
    ).first()


def permission_code_for(permission: IdentityPermission):
    codename = str(permission.codename).strip()
    if "." in codename and codename == codename.upper():
        return codename
    return f"{permission.app_label}.{codename}"


def normalize_permission_code(permission_code: str):
    permission_code = str(permission_code or "").strip()
    if "." in permission_code and permission_code == permission_code.upper():
        return permission_code
    return permission_code
