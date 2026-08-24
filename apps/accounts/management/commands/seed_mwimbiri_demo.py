from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import (
    ConsultationRoom,
    Department,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilitySpecialty,
    FacilityType,
    Organization,
    ServicePoint,
    ServicePointType,
    Specialty,
)
from apps.patients.models import Patient
from apps.patients.services.patient_number_service import generate_patient_number
from apps.practitioners.models import (
    Practitioner,
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
    PractitionerType,
)
from apps.practitioners.services.practitioner_number_service import generate_practitioner_number
from apps.scheduling.models import AppointmentSlot, PractitionerAvailabilityPeriod, PractitionerShift
from common.services.code_generation import generate_code


DEMO_PASSWORD = "2002@-francy"
SUPERUSER_EMAIL = "mwangobora37@gmail.com"
PATIENT_EMAIL = "neema.mwimbiri.patient@gmail.com"


@dataclass(frozen=True)
class PersonSeed:
    first_name: str
    last_name: str
    phone_suffix: str


DOCTORS = [
    PersonSeed("Asha", "Mwangobora", "601001"),
    PersonSeed("Neema", "Matemu", "601002"),
    PersonSeed("Fatuma", "Kassim", "601003"),
    PersonSeed("Rehema", "Mushi", "601004"),
    PersonSeed("Zainabu", "Mwita", "601005"),
    PersonSeed("Halima", "Kimaro", "601006"),
    PersonSeed("Grace", "Komba", "601007"),
    PersonSeed("Witness", "Msuya", "601008"),
    PersonSeed("Sarah", "Mrema", "601009"),
    PersonSeed("Mariam", "Mhando", "601010"),
    PersonSeed("John", "Mbowe", "601011"),
    PersonSeed("Joseph", "Nyerere", "601012"),
    PersonSeed("Jackson", "Kalinga", "601013"),
    PersonSeed("Juma", "Lema", "601014"),
    PersonSeed("Ally", "Mwakyusa", "601015"),
    PersonSeed("Hassan", "Makame", "601016"),
    PersonSeed("Omari", "Nyoni", "601017"),
    PersonSeed("Baraka", "Mrope", "601018"),
    PersonSeed("Emmanuel", "Kapinga", "601019"),
    PersonSeed("Peter", "Mkude", "601020"),
    PersonSeed("David", "Ndossi", "601021"),
    PersonSeed("Daniel", "Chacha", "601022"),
    PersonSeed("Kelvin", "Manyama", "601023"),
    PersonSeed("George", "Lugakingira", "601024"),
    PersonSeed("Michael", "Mwakalinga", "601025"),
    PersonSeed("Salum", "Nyanda", "601026"),
    PersonSeed("Abdallah", "Mbilinyi", "601027"),
    PersonSeed("Said", "Mhina", "601028"),
    PersonSeed("Faraja", "Ngalawa", "601029"),
    PersonSeed("James", "Mapunda", "601030"),
]

RECEPTIONISTS = [
    PersonSeed("Nancy", "Matemu", "602001"),
    PersonSeed("Judith", "Mwangobola", "602002"),
    PersonSeed("Rose", "Komba", "602003"),
    PersonSeed("Ester", "Mushi", "602004"),
    PersonSeed("Agnes", "Mrema", "602005"),
    PersonSeed("Janeth", "Mhina", "602006"),
    PersonSeed("Paulina", "Mbowe", "602007"),
    PersonSeed("Violet", "Kimaro", "602008"),
    PersonSeed("Monica", "Chacha", "602009"),
    PersonSeed("Helena", "Msuya", "602010"),
    PersonSeed("Joyce", "Kassim", "602011"),
    PersonSeed("Lydia", "Ngalawa", "602012"),
    PersonSeed("Doreen", "Kapinga", "602013"),
    PersonSeed("Clara", "Nyanda", "602014"),
    PersonSeed("Irene", "Mwakyusa", "602015"),
    PersonSeed("Beatrice", "Mhando", "602016"),
    PersonSeed("Amina", "Makame", "602017"),
    PersonSeed("Upendo", "Mbilinyi", "602018"),
    PersonSeed("Gladness", "Mrope", "602019"),
    PersonSeed("Veronica", "Mapunda", "602020"),
    PersonSeed("Elizabeth", "Ndossi", "602021"),
    PersonSeed("Martha", "Lema", "602022"),
    PersonSeed("Prisca", "Manyama", "602023"),
    PersonSeed("Angelina", "Mkude", "602024"),
    PersonSeed("Sophia", "Nyoni", "602025"),
    PersonSeed("Catherine", "Kalinga", "602026"),
    PersonSeed("Jackline", "Lugakingira", "602027"),
    PersonSeed("Tatu", "Said", "602028"),
    PersonSeed("Subira", "Omari", "602029"),
    PersonSeed("Gloria", "Mwita", "602030"),
]

OTHER_STAFF = {
    "Facility Manager": [PersonSeed("Musa", "Mgaya", "603001"), PersonSeed("Hilda", "Sanga", "603002")],
    "Nurse": [PersonSeed("Leah", "Swai", "604001"), PersonSeed("Edith", "Madata", "604002"), PersonSeed("Mercy", "Lugano", "604003")],
    "Lab Technician": [PersonSeed("Rashid", "Kileo", "605001"), PersonSeed("Theresia", "Makala", "605002")],
    "Pharmacist": [PersonSeed("Godfrey", "Massawe", "606001"), PersonSeed("Hadija", "Rajabu", "606002")],
}

ROLE_PERMISSION_PREFIXES = {
    "Facility Manager": ("accounts_", "facilities_", "patients_", "practitioners_", "scheduling_", "checkins_", "queueing_", "notifications_", "reporting_", "intelligence_"),
    "Receptionist": ("facilities_facility.view", "patients_patient.", "scheduling_appointment.", "scheduling_slot.manage", "checkins_", "queueing_"),
    "Doctor": ("patients_patient.view", "scheduling_appointment.view", "queueing_entry.view", "queueing_entry.call", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.transfer", "notifications_notification.create"),
    "Nurse": ("patients_patient.view", "checkins_checkin.view", "queueing_entry.view", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.transfer"),
    "Lab Technician": ("patients_patient.view", "queueing_entry.view", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.transfer"),
    "Pharmacist": ("patients_patient.view", "queueing_entry.view", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.transfer"),
}


class Command(BaseCommand):
    help = "Seed persistent Mwimbiri-only demo data for local UI/mobile testing."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)

    def handle(self, *args, **options):
        call_command("sync_permissions", verbosity=0)
        days = max(1, options["days"])
        with transaction.atomic():
            context = self._seed_core()
            self._seed_roles(context)
            self._seed_staff(context)
            self._seed_patient(context)

        self._seed_schedule(context, days)
        self._print_summary(context, days)

    def _seed_core(self):
        admin = self._upsert_user(SUPERUSER_EMAIL, "Francis", "Mwangobora", None, is_staff=True, is_superuser=True)
        org = self._get_or_create_model(Organization, {"name": "Mwimbiri Health Organization"}, code_key="organization", legal_name="Mwimbiri Health Organization", email="info@mwimbirihealth.com", phone_number="+255744600001")
        facility_type = self._get_or_create_model(FacilityType, {"name": "National Hospital"}, code_key="facility_type", description="Large referral hospital")
        facility = self._get_or_create_model(Facility, {"organization": org, "name": "Mwimbiri National Hospital"}, code_key="facility", facility_type=facility_type, email="care@mwimbirihospital.com", phone_number="+255744600002", country_code="TZ", region="Dar es Salaam", district="Ilala", ward="Upanga", timezone="Africa/Dar_es_Salaam", is_primary=True)
        FacilityFlowSetting.objects.update_or_create(facility=facility, defaults={"max_advance_booking_days": 120, "minimum_booking_notice_minutes": 0, "early_checkin_minutes": 60, "queue_number_padding": 3, "created_by": admin})
        for day in range(1, 8):
            FacilityOperatingHour.objects.update_or_create(facility=facility, day_of_week=day, period_order=1, defaults={"opens_at": time(7, 0), "closes_at": time(18, 0), "is_24_hours": False, "is_active": True})
        departments = self._seed_departments(facility)
        facility_specialties = self._seed_specialties(facility, departments)
        service_points = self._seed_service_points(facility, departments)
        rooms = self._seed_rooms(facility, departments)
        practitioner_type = self._get_or_create_model(PractitionerType, {"name": "Medical Doctor"}, code_key="practitioner_type", requires_license=True, created_by=admin)
        return {"admin": admin, "organization": org, "facility": facility, "departments": departments, "facility_specialties": facility_specialties, "service_points": service_points, "rooms": rooms, "practitioner_type": practitioner_type}

    def _seed_departments(self, facility):
        names = ["Outpatient Department", "General Medicine", "Pediatrics", "Emergency", "Laboratory", "Pharmacy"]
        return {name: self._get_or_create_model(Department, {"facility": facility, "name": name}, code_key="department") for name in names}

    def _seed_specialties(self, facility, departments):
        pairs = [("General Medicine", "General Medicine", 30), ("Pediatrics", "Pediatrics", 30), ("Emergency Care", "Emergency", 20), ("Laboratory Services", "Laboratory", 15), ("Pharmacy Services", "Pharmacy", 10)]
        result = {}
        for specialty_name, department_name, duration in pairs:
            specialty = self._get_or_create_model(Specialty, {"name": specialty_name}, code_key="specialty")
            result[specialty_name] = self._get_or_create_facility_specialty(facility, specialty, departments[department_name], duration)
        return result

    def _seed_service_points(self, facility, departments):
        types = {
            "Reception Desk": self._get_or_create_model(ServicePointType, {"name": "Reception Desk"}, code_key="service_point_type"),
            "Consultation Desk": self._get_or_create_model(ServicePointType, {"name": "Consultation Desk"}, code_key="service_point_type"),
            "Laboratory Counter": self._get_or_create_model(ServicePointType, {"name": "Laboratory Counter"}, code_key="service_point_type"),
            "Pharmacy Counter": self._get_or_create_model(ServicePointType, {"name": "Pharmacy Counter"}, code_key="service_point_type"),
        }
        data = [
            ("OPD Reception", types["Reception Desk"], departments["Outpatient Department"], "Ground floor", 1),
            ("General Consultation", types["Consultation Desk"], departments["General Medicine"], "Ground floor wing A", 2),
            ("Pediatrics Consultation", types["Consultation Desk"], departments["Pediatrics"], "First floor wing B", 3),
            ("Emergency Triage", types["Consultation Desk"], departments["Emergency"], "Emergency unit", 4),
            ("Main Laboratory", types["Laboratory Counter"], departments["Laboratory"], "Ground floor lab", 5),
            ("Main Pharmacy", types["Pharmacy Counter"], departments["Pharmacy"], "Ground floor pharmacy", 6),
        ]
        return {name: self._get_or_create_model(ServicePoint, {"facility": facility, "name": name}, code_key="service_point", service_point_type=point_type, department=department, location_description=location, display_order=order) for name, point_type, department, location, order in data}

    def _seed_rooms(self, facility, departments):
        rooms = []
        room_departments = ["General Medicine", "Pediatrics", "Emergency", "Laboratory", "Pharmacy"]
        for department_name in room_departments:
            short_name = department_name.replace("General Medicine", "Consultation")
            for index in range(1, 11):
                rooms.append(
                    self._get_or_create_model(
                        ConsultationRoom,
                        {"facility": facility, "name": f"{short_name} Room {index}"},
                        code_key="consultation_room",
                        department=departments[department_name],
                        capacity=1,
                        floor="Ground floor",
                    )
                )
        return rooms

    def _seed_roles(self, context):
        roles = {}
        for role_name in ROLE_PERMISSION_PREFIXES:
            role = self._get_or_create_model(Role, {"organization": context["organization"], "facility": context["facility"], "name": role_name}, code_key="role", description=f"Mwimbiri {role_name.lower()} role", created_by=context["admin"])
            roles[role_name] = role
            self._grant_permissions(role, ROLE_PERMISSION_PREFIXES[role_name], context["admin"])
        context["roles"] = roles

    def _seed_staff(self, context):
        for person in DOCTORS:
            user = self._upsert_user(self._email("doctor", person), person.first_name, person.last_name, person.phone_suffix)
            self._ensure_facility_access(user, context["roles"]["Doctor"], context)
            self._ensure_practitioner(user, person, context)
        for person in RECEPTIONISTS:
            user = self._upsert_user(self._email("reception", person), person.first_name, person.last_name, person.phone_suffix)
            self._ensure_facility_access(user, context["roles"]["Receptionist"], context)
        for role_name, people in OTHER_STAFF.items():
            for person in people:
                user = self._upsert_user(self._email(role_name.lower().replace(" ", ""), person), person.first_name, person.last_name, person.phone_suffix)
                self._ensure_facility_access(user, context["roles"][role_name], context)

    def _seed_patient(self, context):
        user = self._upsert_user(PATIENT_EMAIL, "Neema", "Kassim", "607001")
        organization = Organization.objects.select_for_update().get(id=context["organization"].id)
        patient = Patient.objects.filter(organization=organization, user=user).first()
        if not patient:
            patient = Patient.objects.create(organization=organization, user=user, registered_facility=context["facility"], patient_number=generate_patient_number(organization=organization), first_name="Neema", last_name="Kassim", date_of_birth="1997-05-14", sex_code=Patient.SexCode.FEMALE, email=PATIENT_EMAIL, phone_number="+255756607001")
        else:
            patient.is_active = True
            patient.registered_facility = context["facility"]
            patient.save(update_fields=["is_active", "registered_facility", "updated_at"])

    def _ensure_practitioner(self, user, person, context):
        org = Organization.objects.select_for_update().get(id=context["organization"].id)
        practitioner = Practitioner.objects.filter(organization=org, user=user).first()
        if not practitioner:
            practitioner = Practitioner.objects.create(organization=org, user=user, practitioner_type=context["practitioner_type"], practitioner_number=generate_practitioner_number(organization=org), first_name=person.first_name, last_name=person.last_name, email=user.email, phone_number=user.phone_number, created_by=context["admin"])
        assignment, _ = PractitionerFacilityAssignment.objects.update_or_create(practitioner=practitioner, facility=context["facility"], defaults={"starts_on": timezone.localdate(), "ends_on": None, "is_primary": True, "is_active": True, "assigned_by": context["admin"]})
        specialty_names = list(context["facility_specialties"].keys())[:4]
        specialty_name = specialty_names[DOCTORS.index(person) % len(specialty_names)]
        facility_specialty = context["facility_specialties"][specialty_name]
        department = facility_specialty.department
        dept_assignment, _ = PractitionerDepartmentAssignment.objects.update_or_create(practitioner_facility_assignment=assignment, department=department, defaults={"starts_on": timezone.localdate(), "ends_on": None, "is_primary": True, "is_active": True, "assigned_by": context["admin"]})
        spec_assignment, _ = PractitionerSpecialtyAssignment.objects.update_or_create(practitioner_facility_assignment=assignment, facility_specialty=facility_specialty, defaults={"starts_on": timezone.localdate(), "ends_on": None, "is_primary": True, "is_active": True, "assigned_by": context["admin"]})
        practitioner.seed_department_assignment = dept_assignment
        practitioner.seed_specialty_assignment = spec_assignment
        practitioner.seed_facility_assignment = assignment
        return practitioner

    def _seed_schedule(self, context, days):
        start_date = timezone.localdate()
        doctors = Practitioner.objects.filter(organization=context["organization"], user__email__startswith="doctor.").select_related("user").order_by("last_name", "first_name")
        doctor_contexts = []
        for practitioner in doctors:
            pfa = practitioner.facility_assignments.select_related("facility").get(facility=context["facility"])
            specialty_assignment = pfa.specialty_assignments.select_related("facility_specialty__specialty").filter(is_active=True).first()
            department_assignment = pfa.department_assignments.filter(is_active=True).first()
            if not specialty_assignment:
                continue
            service_point = self._service_point_for_specialty(context, specialty_assignment.facility_specialty)
            doctor_contexts.append((pfa, specialty_assignment, department_assignment, service_point))
            for weekday in range(1, 8):
                PractitionerAvailabilityPeriod.objects.get_or_create(practitioner_facility_assignment=pfa, day_of_week=weekday, starts_at=time(7, 30), ends_at=time(15, 30), valid_from=start_date, defaults={"valid_until": start_date + timedelta(days=days), "is_available_for_appointments": True, "created_by": context["admin"]})

        range_start = timezone.make_aware(datetime.combine(start_date, time(0, 0)))
        range_end = timezone.make_aware(datetime.combine(start_date + timedelta(days=days), time(0, 0)))
        pfa_ids = [pfa.id for pfa, _specialty_assignment, _department_assignment, _service_point in doctor_contexts]
        existing_shift_keys = set(
            PractitionerShift.objects.filter(
                practitioner_facility_assignment_id__in=pfa_ids,
                starts_at__gte=range_start,
                starts_at__lt=range_end,
            ).values_list("practitioner_facility_assignment_id", "starts_at", "ends_at")
        )

        shift_candidates = []
        for day_offset in range(days):
            work_date = start_date + timedelta(days=day_offset)
            starts_at = timezone.make_aware(datetime.combine(work_date, time(7, 30)))
            ends_at = timezone.make_aware(datetime.combine(work_date, time(15, 30)))
            for pfa, _specialty_assignment, department_assignment, service_point in doctor_contexts:
                key = (pfa.id, starts_at, ends_at)
                if key in existing_shift_keys:
                    continue
                shift_candidates.append(
                    PractitionerShift(
                        practitioner_facility_assignment=pfa,
                        practitioner_department_assignment=department_assignment,
                        service_point=service_point,
                        consultation_room=None,
                        starts_at=starts_at,
                        ends_at=ends_at,
                        accepts_appointments=True,
                        status=PractitionerShift.Status.SCHEDULED,
                        created_by=context["admin"],
                    )
                )
        PractitionerShift.objects.bulk_create(shift_candidates, batch_size=500)
        shifts_created = len(shift_candidates)

        shift_map = {
            (shift.practitioner_facility_assignment_id, shift.starts_at, shift.ends_at): shift
            for shift in PractitionerShift.objects.filter(
                practitioner_facility_assignment_id__in=pfa_ids,
                starts_at__gte=range_start,
                starts_at__lt=range_end,
            )
        }
        slot_candidates = []
        slots_before = AppointmentSlot.objects.count()
        for day_offset in range(days):
            work_date = start_date + timedelta(days=day_offset)
            starts_at = timezone.make_aware(datetime.combine(work_date, time(7, 30)))
            ends_at = timezone.make_aware(datetime.combine(work_date, time(15, 30)))
            for pfa, specialty_assignment, _department_assignment, _service_point in doctor_contexts:
                shift = shift_map.get((pfa.id, starts_at, ends_at))
                if not shift:
                    continue
                slot_start = starts_at
                while slot_start < ends_at:
                    slot_end = slot_start + timedelta(minutes=specialty_assignment.facility_specialty.appointment_duration_minutes)
                    slot_candidates.append(AppointmentSlot(practitioner_shift=shift, facility_specialty=specialty_assignment.facility_specialty, starts_at=slot_start, ends_at=slot_end, capacity=1, booked_count=0, status=AppointmentSlot.Status.AVAILABLE, is_online_bookable=True))
                    slot_start = slot_end
        AppointmentSlot.objects.bulk_create(slot_candidates, ignore_conflicts=True, batch_size=1000)
        slots_created = AppointmentSlot.objects.count() - slots_before
        context["shifts_created"] = shifts_created
        context["slots_created"] = slots_created

    def _get_or_create_facility_specialty(self, facility, specialty, department, duration):
        obj, created = FacilitySpecialty.objects.get_or_create(facility=facility, specialty=specialty, department=department, defaults={"appointment_duration_minutes": duration, "accepts_appointments": True, "accepts_walk_ins": True})
        if not created:
            obj.appointment_duration_minutes = duration
            obj.accepts_appointments = True
            obj.accepts_walk_ins = True
            obj.is_active = True
            obj.save(update_fields=["appointment_duration_minutes", "accepts_appointments", "accepts_walk_ins", "is_active", "updated_at"])
        return obj

    def _service_point_for_specialty(self, context, facility_specialty):
        mapping = {"General Medicine": "General Consultation", "Pediatrics": "Pediatrics Consultation", "Emergency Care": "Emergency Triage", "Laboratory Services": "Main Laboratory", "Pharmacy Services": "Main Pharmacy"}
        return context["service_points"].get(mapping.get(facility_specialty.specialty.name), context["service_points"]["General Consultation"])

    def _get_or_create_model(self, model, lookup, *, code_key=None, **defaults):
        obj = model.objects.filter(**lookup).first()
        if obj:
            for field, value in defaults.items():
                setattr(obj, field, value)
            if hasattr(obj, "is_active"):
                obj.is_active = True
            obj.save()
            return obj
        if code_key:
            defaults["code"] = generate_code(code_key)
        return model.objects.create(**lookup, **defaults)

    def _upsert_user(self, email, first_name, last_name, phone_suffix=None, *, is_staff=False, is_superuser=False):
        defaults = {"first_name": first_name, "last_name": last_name, "is_active": True, "is_staff": is_staff, "is_superuser": is_superuser, "email_verified_at": timezone.now()}
        if phone_suffix:
            defaults["phone_number"] = f"+255756{phone_suffix}"
        user = User.objects.filter(email=email.lower()).first()
        if user:
            for field, value in defaults.items():
                setattr(user, field, value)
            user.set_password(DEMO_PASSWORD)
            user.save()
            return user
        return User.objects.create_user(email=email.lower(), password=DEMO_PASSWORD, **defaults)

    def _ensure_facility_access(self, user, role, context):
        now = timezone.now()
        UserMembership.objects.update_or_create(user=user, organization=context["organization"], facility=context["facility"], defaults={"starts_at": now, "ends_at": None, "is_active": True, "created_by": context["admin"]})
        UserRoleAssignment.objects.update_or_create(user=user, role=role, defaults={"starts_at": now, "ends_at": None, "is_active": True, "assigned_by": context["admin"]})

    def _grant_permissions(self, role, prefixes, admin):
        permissions = Permission.objects.filter(is_active=True)
        selected = [permission for permission in permissions if any(permission.code == prefix.rstrip(".") or permission.code.startswith(prefix) for prefix in prefixes)]
        for permission in selected:
            RolePermission.objects.update_or_create(role=role, permission=permission, defaults={"is_active": True, "granted_by": admin})

    def _email(self, prefix, person):
        return f"{prefix}.{person.first_name.lower()}.{person.last_name.lower()}@mwimbirihealth.com"

    def _print_summary(self, context, days):
        facility = context["facility"]
        self.stdout.write(self.style.SUCCESS("Mwimbiri demo data ready."))
        self.stdout.write(f"Superuser: {SUPERUSER_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"Mobile patient: {PATIENT_EMAIL} / {DEMO_PASSWORD}")
        self.stdout.write(f"Facility: {facility.name} ({facility.code})")
        self.stdout.write(f"Doctors: {Practitioner.objects.filter(organization=context['organization']).count()}")
        self.stdout.write(f"Receptionists: {User.objects.filter(email__startswith='reception.').count()}")
        self.stdout.write(f"Schedule horizon: {days} days")
        self.stdout.write(f"New shifts: {context.get('shifts_created', 0)}")
        self.stdout.write(f"New slots: {context.get('slots_created', 0)}")
