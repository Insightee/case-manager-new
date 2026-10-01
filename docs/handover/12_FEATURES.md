# 12 — Features

End-to-end inventory. **Access** assumes default role permissions + module grants; exact matrix in [docs/RBAC_SCOPE.md](../RBAC_SCOPE.md).

---

## 1. Authentication & account lifecycle

| | |
|--|--|
| **Purpose** | Secure login, token refresh, invites, password reset |
| **Users** | All |
| **Frontend** | `LoginPage`, `InvitePage`, `ForgotPasswordPage`, `AuthContext` |
| **Backend** | `auth.py`, `auth_service`, `password_reset_service` |
| **API** | `/api/v1/auth/*` |
| **Tables** | `users`, `invite_tokens`, `password_reset_tokens`, `email_logs` |
| **External** | SMTP |
| **Rules** | Portal allowlist; employment status block + restore request |
| **Limits** | Therapist self-onboarding UI disabled (TODOs in scheduling components) |

---

## 2. Therapist session logs & sessions

| | |
|--|--|
| **Purpose** | Daily execution: timer, submit logs, forgot session |
| **Users** | `THERAPIST` |
| **Frontend** | `DailyLogsPage`, session components under `daily-logs/` |
| **Backend** | `sessions.py`, `daily_logs.py`, `session_log_service` |
| **API** | `/sessions`, `/daily-logs` |
| **Tables** | `therapy_sessions`, `daily_logs`, optional evidence tables |
| **Rules** | Void window; structured evidence behind flags |

---

## 3. My Cases (therapist CRM)

| | |
|--|--|
| **Purpose** | Per-case overview, tabs for logs/reports/booking |
| **Users** | `THERAPIST` |
| **Frontend** | `MyCasesPage`, `CaseDetailPage` |
| **Backend** | `cases.py`, `therapist_portal.py` |
| **API** | `/cases`, case-scoped reads |
| **Tables** | `cases`, assignments, clinical profile |

---

## 4. Admin case management

| | |
|--|--|
| **Purpose** | Create/edit cases, assignments, billing fields, status |
| **Users** | `MODULE_ADMIN`, `CASE_MANAGER`, `SUPER_ADMIN` |
| **Frontend** | `AdminCasesPage`, `AdminCaseDetailPage` |
| **Backend** | `admin.py`, `cases.py`, assignment routers |
| **API** | `/admin/*`, `/cases` |
| **Tables** | `cases`, `case_assignments`, `case_services`, audits |

---

## 5. Session log approval (admin/CM)

| | |
|--|--|
| **Purpose** | Approve/reject logs; parent-facing notes |
| **Users** | CM, module admin |
| **Frontend** | `AdminSessionLogsPage`, `AdminWorkbenchPage`, `AdminCmLogReviewPage` |
| **Backend** | `daily_logs.py`, admin aggregates |
| **API** | `/daily-logs/{id}/approve`, admin log queues |
| **Rules** | Visibility transition on approve |

---

## 6. Monthly & observation reports

| | |
|--|--|
| **Purpose** | Report draft → submit → admin → parent |
| **Users** | Therapist, admin, parent (read) |
| **Frontend** | `MonthlyReportsPage`, `AdminReportsPage`, `ParentReportsPage` |
| **Backend** | `reports.py`, report services |
| **API** | `/reports`, `/parent/reports` |
| **Tables** | `monthly_reports`, `observation_reports`, attachments |

---

## 7. Clinical reports engine (observation/IEP builders)

| | |
|--|--|
| **Purpose** | Structured clinical report builder |
| **Users** | Therapist, admin reviewers |
| **Frontend** | `reports-engine/*`, `TherapistClinicalReportPage` |
| **Backend** | `clinical_reports.py` |
| **API** | Case-scoped clinical report routes |
| **Tables** | `clinical_reports`, sections, versions, evidence |
| **Flag** | `ENABLE_CLINICAL_REPORTS_ENGINE`, `VITE_REPORTS_REVAMP` |
| **Limits** | Requires Alembic revision noted in env docs |

---

## 8. IEP administration & parent acknowledgement

| | |
|--|--|
| **Purpose** | IEP upload/share; parent ack |
| **Users** | Admin, CM, parent |
| **Frontend** | `AdminIepPage`, parent reports hub |
| **Backend** | `cases.py` IEP endpoints, `parent.py` |
| **Tables** | `iep_plans`, attachments, suggestions |

---

## 9. Therapist invoices

| | |
|--|--|
| **Purpose** | Therapist-facing invoice history/submit |
| **Users** | `THERAPIST`, finance admin |
| **Frontend** | `InvoicesPage`, `AdminInvoicesPage` |
| **Backend** | `invoices.py`, billing services |
| **Tables** | `invoices`, invoice lines |

---

## 10. Client billing & finance control tower

| | |
|--|--|
| **Purpose** | Client invoices, ledger, finance dashboard, corrections |
| **Users** | `FINANCE`, `MODULE_ADMIN` (billing module) |
| **Frontend** | Finance admin pages, `InvoiceComposer`, control tower components |
| **Backend** | `finance_ops`, `ledger_billing`, `finance_control_tower`, `finance_writable`, `client_billing` |
| **Flag** | `ENABLE_BILLING`, Vite finance flags |
| **External** | Zoho Books (optional) |
| **Docs** | [billing-architecture.md](../billing-architecture.md), finance handover docs |

---

## 11. Therapist payouts

| | |
|--|--|
| **Purpose** | Payout queue, export batch, TDS, disputes |
| **Users** | Finance |
| **Frontend** | `AdminTherapistPayoutsPage` |
| **Backend** | `finance_ops.py` |
| **Tables** | `therapist_payout_*`, disputes |
| **Flag** | `PAYOUT_EXPORT_ENABLED`, `PAYOUT_RELEASE_ENABLED` |

---

## 12. Parent portal

| | |
|--|--|
| **Purpose** | Approved logs, reports, billing, booking, support |
| **Users** | `PARENT` |
| **Frontend** | `client-portal/*`, `ParentRoutes` |
| **Backend** | `parent.py` |
| **API** | `/parent/*` |
| **Guide** | [PARENT_CLIENT_PORTAL_GUIDE.md](../PARENT_CLIENT_PORTAL_GUIDE.md) |

---

## 13. Booking & scheduling

| | |
|--|--|
| **Purpose** | Slots, appointments, recurring schedules, calendar |
| **Users** | Therapist, parent, admin |
| **Frontend** | `TherapistSlotsPage`, `ClientBookAppointmentPage`, scheduling components |
| **Backend** | `booking.py`, `slots.py`, `scheduling.py`, `calendar.py` |
| **Tables** | `therapist_slots`, `recurring_schedule_assignments`, calendar models |

---

## 14. CM meetings

| | |
|--|--|
| **Purpose** | Case manager meeting scheduling and actions |
| **Users** | CM, admin |
| **Frontend** | `CaseManagerMeetingsPage` |
| **Backend** | `meetings.py` |
| **Tables** | `case_manager_meetings`, `meeting_actions` |
| **External** | Google Calendar `ctz` for invites |

---

## 15. Support hub (tickets, memos)

| | |
|--|--|
| **Purpose** | Cross-portal support desk |
| **Users** | All portals (scoped) |
| **Frontend** | `*SupportHubPage`, memo pages |
| **Backend** | `tickets.py`, `memos.py`, `admin_support.py` |
| **Tables** | `support_tickets`, `memos`, attachments |

---

## 16. Incidents

| | |
|--|--|
| **Purpose** | Incident reporting and workflow |
| **Users** | Therapist, parent, admin (role-scoped) |
| **Frontend** | Support hub incident tabs |
| **Backend** | `incidents.py` |
| **Tables** | `incidents`, messages, attachments |

---

## 17. HR — people, attendance, leave

| | |
|--|--|
| **Purpose** | Staff roster, RBAC editor, attendance, leave management |
| **Users** | `HR`, `MODULE_ADMIN`, `SPOT` role pages |
| **Frontend** | `AdminPeoplePage`, `StaffAttendancePage`, `LeaveManagementPage`, Spot pages |
| **Backend** | `hr.py`, `staff_attendance.py`, `leave.py`, `hr_ops.py` |
| **Handover** | [HANDOVER_SUPPORT_HR.md](../HANDOVER_SUPPORT_HR.md) |

---

## 18. Therapist profiles & reviews

| | |
|--|--|
| **Purpose** | Therapist HR profile submission and reviews |
| **Users** | Therapist, HR |
| **Frontend** | `TherapistProfilePage`, `AdminTherapistProfilesPage` |
| **Backend** | `therapist_profile.py` |
| **Tables** | `therapist_profiles`, reviews |

---

## 19. Case documents workflow

| | |
|--|--|
| **Purpose** | Document upload, CM review, parent approval |
| **Users** | Staff, parent |
| **Backend** | `case_documents.py` |
| **Tables** | `case_documents`, versions, workflow events |

---

## 20. Notifications

| | |
|--|--|
| **Purpose** | In-app notification center |
| **Users** | All portals |
| **Frontend** | `NotificationCenterPage` |
| **Backend** | `notifications.py` |
| **Tables** | `notifications` |

---

## 21. Admin integrations & webhooks

| | |
|--|--|
| **Purpose** | Machine clients, webhooks, read-only integration API |
| **Users** | Super admin |
| **Frontend** | `AdminIntegrationsPage` |
| **Backend** | `integrations.py`, admin integration routers |
| **Flag** | `INTEGRATION_API_ENABLED`, `MCP_ENABLED` |
| **Docs** | [INTEGRATIONS_MCP.md](../INTEGRATIONS_MCP.md) |

---

## 22. Platform stats & operational exports

| | |
|--|--|
| **Purpose** | KPIs, CSV/XLSX exports (finance, HR, CRM) |
| **Users** | Admin, finance, HR |
| **Frontend** | `AdminPlatformStatsPage`, finance/HR report pages |
| **Backend** | `admin.py`, `finance_ops`, `hr_ops` |
| **Docs** | [Cursor_Handover_Admin_Operational_Reports.md](../Cursor_Handover_Admin_Operational_Reports.md) |

---

## 23. Geocoding & addresses

| | |
|--|--|
| **Purpose** | Service address geocoding |
| **Backend** | `geocode.py`, `address_service` |
| **UNKNOWN** | External geocoder API key — verify in `geocode.py` |

---

## 24. PWA / mobile therapist UX

| | |
|--|--|
| **Purpose** | Installable therapist portal |
| **Frontend** | `vite-plugin-pwa`, mobile CSS |
| **Docs** | [THERAPIST_PORTAL_GUIDE.md](../THERAPIST_PORTAL_GUIDE.md) |

---

## Feature flag summary

See [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md) for billing, finance dashboard, clinical engine, structured evidence.
