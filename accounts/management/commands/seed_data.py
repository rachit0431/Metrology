from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, InstrumentOwnerProfile, LMOProfile, GATCProfile
from instruments.models import InstrumentCategory, Instrument
from verification.models import VerificationApplication, AuditLog
from certificates.models import VerificationCertificate
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Seeds essential Legal Metrology categories, roles, test accounts, instruments, applications, and audit trail.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Legal Metrology foundation...")

        # 1. Standard Categories
        categories_data = [
            {
                'name': 'Electronic Non-Automatic Weighing Instruments (NAWI)',
                'code': 'NAWI-E',
                'description': 'Counter scales, platform scales, and electronic precision balances.',
                'standard_verification_validity_months': 12
            },
            {
                'name': 'Fuel Dispensing Units (Petrol/Diesel/CNG Pumps)',
                'code': 'FDU-DISP',
                'description': 'Retail petroleum and gas measurement dispensers.',
                'standard_verification_validity_months': 12
            },
            {
                'name': 'Heavy Duty Electronic Weighbridges',
                'code': 'WB-ELEC',
                'description': 'Pit and pitless industrial truck weighbridges up to 100 tonnes.',
                'standard_verification_validity_months': 12
            },
            {
                'name': 'Volumetric Flow Meters & Liquid Measures',
                'code': 'VFM-VOL',
                'description': 'Bulk liquid flow meters for tankers, depots, and process plants.',
                'standard_verification_validity_months': 12
            },
            {
                'name': 'Linear Measures & Measuring Tapes',
                'code': 'LM-TAPE',
                'description': 'Commercial steel tapes, surveyor bands, and rigid measures of length.',
                'standard_verification_validity_months': 24
            }
        ]

        cat_objs = {}
        for c in categories_data:
            cat, _ = InstrumentCategory.objects.get_or_create(
                code=c['code'],
                defaults=c
            )
            cat_objs[c['code']] = cat

        # 2. Superuser Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin.metrology@gov.in',
                'first_name': 'Directorate',
                'last_name': 'Administrator',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'phone': '011-23381234'
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created Superuser Admin: admin / admin123"))

        # 3. Legal Metrology Officer (LMO)
        lmo_user, created = User.objects.get_or_create(
            username='officer_sharma',
            defaults={
                'email': 'r.sharma.lmo@gov.in',
                'first_name': 'Rajesh',
                'last_name': 'Sharma',
                'role': User.Role.LMO,
                'is_staff': False,
                'is_verified': True,
                'phone': '9822012345'
            }
        )
        if created:
            lmo_user.set_password('officer123')
            lmo_user.save()
        LMOProfile.objects.update_or_create(
            user=lmo_user,
            defaults={
                'officer_id': 'LMO-MH-PUN-014',
                'department': 'Department of Legal Metrology, Maharashtra',
                'designation': 'Senior Inspector of Legal Metrology',
                'jurisdiction_state': 'Maharashtra',
                'jurisdiction_district': 'Pune',
                'jurisdiction_circle': 'Shivajinagar Industrial & Commercial Zone',
                'office_phone': '020-25531420',
                'official_email': 'r.sharma.lmo@gov.in'
            }
        )

        # 4. GATC Lab
        gatc_user, created = User.objects.get_or_create(
            username='gatc_pune_lab',
            defaults={
                'email': 'director@punemetrologylab.org',
                'first_name': 'Pune',
                'last_name': 'Calibration Centre',
                'role': User.Role.GATC,
                'is_staff': False,
                'is_verified': True,
                'phone': '020-27129988'
            }
        )
        if created:
            gatc_user.set_password('gatc123')
            gatc_user.save()
        GATCProfile.objects.update_or_create(
            user=gatc_user,
            defaults={
                'centre_name': 'Western Regional Standards & Calibration Laboratory',
                'approval_number': 'GATC/REG/MH/2026/088',
                'accreditation_details': 'NABL Accredited CC-2194 / ISO 17025:2017',
                'valid_until': timezone.localdate() + timedelta(days=730),
                'contact_person': 'Dr. Sunita Kulkarni',
                'phone': '020-27129988',
                'email': 'director@punemetrologylab.org',
                'address': 'Plot 45, MIDC Bhosari Industrial Area',
                'state': 'Maharashtra',
                'district': 'Pune',
                'status': GATCProfile.Status.ACTIVE
            }
        )

        # 5. Instrument Owner
        owner_user, created = User.objects.get_or_create(
            username='patil_traders',
            defaults={
                'email': 'contact@patiltraders.com',
                'first_name': 'Anand',
                'last_name': 'Patil',
                'role': User.Role.INSTRUMENT_OWNER,
                'is_staff': False,
                'is_verified': True,
                'phone': '9890123456'
            }
        )
        if created:
            owner_user._skip_default_profile_signal = True
            owner_user.set_password('owner123')
            owner_user.save()
        InstrumentOwnerProfile.objects.update_or_create(
            user=owner_user,
            defaults={
                'business_name': 'Patil Agro Traders & Wholesale Mart',
                'trade_license_number': 'PMC-TL-2024-8841',
                'gstin': '27ABCDE1234F1Z5',
                'contact_person': 'Anand Patil',
                'phone': '9890123456',
                'email': 'contact@patiltraders.com',
                'address': 'Shop 12-14, Market Yard Commercial Complex',
                'state': 'Maharashtra',
                'district': 'Pune',
                'pincode': '411037'
            }
        )

        # 6. Sample Instruments
        today = timezone.localdate()
        inst1, _ = Instrument.objects.update_or_create(
            serial_number='EWB-MH-2024-0091',
            defaults={
                'owner': owner_user,
                'category': cat_objs['WB-ELEC'],
                'instrument_name': '50-Tonne Electronic Pitless Weighbridge',
                'instrument_type': Instrument.InstrumentType.WEIGHBRIDGE,
                'model_number': 'IND-WB-50T-PRO',
                'manufacturer': 'Bharat Precision Scales Ltd.',
                'capacity': 'Max 50,000 kg, e = 10 kg',
                'accuracy_class': Instrument.AccuracyClass.CLASS_III,
                'year_of_manufacture': 2024,
                'location': 'Gate No. 2 Weighbridge Bay',
                'address': 'Gate No. 2, Market Yard Wholesale Depot',
                'district': 'Pune',
                'state': 'Maharashtra',
                'status': Instrument.Status.VERIFIED,
                'last_verified_date': today - timedelta(days=180),
                'next_verification_date': today + timedelta(days=185),
            }
        )

        inst2, _ = Instrument.objects.update_or_create(
            serial_number='NAWI-CT-2025-4412',
            defaults={
                'owner': owner_user,
                'category': cat_objs['NAWI-E'],
                'instrument_name': 'Electronic Countertop Computing Scale',
                'instrument_type': Instrument.InstrumentType.COUNTER_SCALE,
                'model_number': 'ECS-30P',
                'manufacturer': 'Precision Tech Instruments',
                'capacity': 'Max 30 kg, e = 5 g',
                'accuracy_class': Instrument.AccuracyClass.CLASS_III,
                'year_of_manufacture': 2025,
                'location': 'Billing Counter 3',
                'address': 'Shop 12-14, Market Yard Commercial Complex',
                'district': 'Pune',
                'state': 'Maharashtra',
                'status': Instrument.Status.VERIFICATION_PENDING,
                'last_verified_date': today - timedelta(days=350),
                'next_verification_date': today + timedelta(days=15),
            }
        )

        inst3, _ = Instrument.objects.update_or_create(
            serial_number='PFM-MH-2026-1180',
            defaults={
                'owner': owner_user,
                'category': cat_objs['NAWI-E'],
                'instrument_name': 'Heavy Duty Platform Scale 500 kg',
                'instrument_type': Instrument.InstrumentType.PLATFORM_SCALE,
                'model_number': 'PFS-500-HD',
                'manufacturer': 'Deccan Industrial Scales',
                'capacity': 'Max 500 kg, e = 50 g',
                'accuracy_class': Instrument.AccuracyClass.CLASS_III,
                'year_of_manufacture': 2026,
                'location': 'Warehouse Loading Dock B',
                'address': 'Shop 12-14, Market Yard Commercial Complex',
                'district': 'Pune',
                'state': 'Maharashtra',
                'status': Instrument.Status.ACTIVE,
            }
        )

        # 7. Sample Verification Applications
        app1, created_app1 = VerificationApplication.objects.update_or_create(
            application_number='VA-2026-MH-00108',
            defaults={
                'instrument': inst2,
                'applicant': owner_user,
                'assigned_officer': lmo_user,
                'assigned_gatc': gatc_user,
                'application_type': VerificationApplication.ApplicationType.RE_VERIFICATION,
                'status': VerificationApplication.Status.INSPECTION_PENDING,
                'submitted_at': timezone.now() - timedelta(days=3),
                'preferred_date': today + timedelta(days=2),
                'scheduled_date': today + timedelta(days=5),
                'location': f"{inst2.location}, {inst2.address}, {inst2.district}",
                'remarks': 'Periodic annual re-verification scheduled at retail premises.'
            }
        )

        app2, _ = VerificationApplication.objects.update_or_create(
            application_number='VA-2025-MH-00042',
            defaults={
                'instrument': inst1,
                'applicant': owner_user,
                'assigned_officer': lmo_user,
                'application_type': VerificationApplication.ApplicationType.INITIAL_VERIFICATION,
                'status': VerificationApplication.Status.PASSED,
                'submitted_at': timezone.now() - timedelta(days=185),
                'scheduled_date': today - timedelta(days=181),
                'completed_date': today - timedelta(days=180),
                'location': f"{inst1.location}, {inst1.address}, {inst1.district}",
                'remarks': 'Zero error and eccentricity tests passed within permissible MPE limits.'
            }
        )

        # Seed initial AuditLog entries if empty
        if not AuditLog.objects.exists():
            AuditLog.log_event(
                actor=owner_user,
                action="Registered new instrument (Electronic Counter / Retail Scale)",
                instrument=inst2,
                new_status=Instrument.Status.ACTIVE,
                remarks="Initial registration by Patil Agro Traders.",
            )
            AuditLog.log_event(
                actor=owner_user,
                action="Application submitted for verification",
                instrument=inst2,
                application=app1,
                previous_status=VerificationApplication.Status.DRAFT,
                new_status=VerificationApplication.Status.SUBMITTED,
                remarks="Annual periodic re-verification requested.",
            )
            AuditLog.log_event(
                actor=admin_user,
                action=f"Application assigned (LMO: {lmo_user.display_name}, GATC: {gatc_user.display_name})",
                instrument=inst2,
                application=app1,
                previous_status=VerificationApplication.Status.SUBMITTED,
                new_status=VerificationApplication.Status.ASSIGNED,
                remarks="Assigned to Pune Circle LMO and Pune Calibration Centre.",
            )
            AuditLog.log_event(
                actor=lmo_user,
                action=f"Verification scheduled for {app1.scheduled_date} and moved to Inspection Pending",
                instrument=inst2,
                application=app1,
                previous_status=VerificationApplication.Status.ASSIGNED,
                new_status=VerificationApplication.Status.INSPECTION_PENDING,
                remarks="Field inspection scheduled.",
            )

        # 8. Sample Inspection & Certificate for Verified Instrument 1
        from verification.models import Inspection
        if not Inspection.objects.filter(application=app2).exists():
            Inspection.objects.create(
                application=app2,
                inspector=lmo_user,
                inspection_date=today - timedelta(days=180),
                location=f"{inst1.location}, {inst1.address}, {inst1.district}",
                instrument_condition=Inspection.Condition.GOOD_INTACT,
                test_parameters="Standard M1 20kg test weights; 5 corner eccentricity & full-range linearity test",
                observed_readings="Load 5,000 kg -> 5,000 kg (0 kg)\nLoad 25,000 kg -> 25,000 kg (0 kg)\nLoad 50,000 kg -> 50,010 kg (+10 kg)",
                remarks="Weighbridge passed all corner load and linearity checks. Statutory lead & digital seal applied.",
                result=Inspection.Result.PASS,
                is_locked=True,
            )

        existing_cert = VerificationCertificate.objects.filter(application=app2).first()
        if not existing_cert:
            VerificationCertificate.objects.create(
                certificate_number='LM-2026-000123',
                instrument=inst1,
                application=app2,
                owner=owner_user,
                issuing_officer=lmo_user,
                issue_date=today - timedelta(days=180),
                valid_until=today + timedelta(days=185),
                verification_status=VerificationCertificate.Status.VALID,
            )
            app2.status = VerificationApplication.Status.CERTIFICATE_ISSUED
            app2.save(update_fields=['status'])

        # 9. Notification
        Notification.objects.get_or_create(
            recipient=owner_user,
            title='Upcoming Re-verification Notice',
            defaults={
                'message': 'Your Electronic Countertop Computing Scale (S/N: NAWI-CT-2025-4412) is due for mandatory periodic re-verification within 15 days.',
                'notification_type': Notification.NotificationType.EXPIRY_WARNING,
                'is_read': False
            }
        )

        self.stdout.write(self.style.SUCCESS("All Legal Metrology seed data updated successfully!"))
