"""Single source of truth for permission codes.  Format:  <module>.<resource>.<action>

Adding a new module (e.g. HRMS) = add its codes here, then run:  python -m app.scripts.seed
"""

PERMISSIONS: dict[str, str] = {
    # ---- core (users, roles, departments, audit) ----
    "core.user.view": "View users",
    "core.user.create": "Create users",
    "core.user.update": "Edit users, activate or deactivate",
    "core.user.manage_roles": "Assign roles to users",
    "core.user.reset_password": "Reset a user's password",
    "core.role.view": "View roles and permissions",
    "core.role.manage": "Create, edit and delete roles",
    "core.department.view": "View departments",
    "core.department.manage": "Create and edit departments",
    "core.audit.view": "View the audit log",
    # ---- crm ----
    "crm.lead.view": "View leads",
    "crm.lead.create": "Create leads",
    "crm.lead.update": "Edit leads",
    "crm.lead.delete": "Delete leads",
    "crm.lead.assign": "Assign or reassign leads",
    "crm.contact.view": "View contacts",
    "crm.contact.create": "Create contacts",
    "crm.contact.update": "Edit contacts",
    "crm.customer.view": "View customers",
    "crm.customer.create": "Create customers",
    "crm.customer.update": "Edit customers",
    "crm.deal.view": "View deals",
    "crm.deal.create": "Create deals",
    "crm.deal.update": "Edit deals",
    "crm.quote.view": "View quotes",
    "crm.quote.create": "Create quotes",
    "crm.quote.update": "Edit quotes",
    "crm.quote.fill_rate": "Fill rates on quote items",
    "crm.quote.approve_rate": "Approve or reject quote rates",
    "crm.order.view": "View sales orders",
    "crm.order.create": "Create sales orders",
    "crm.order.update_payment": "Update payment fields on orders",
    "crm.order.update_dispatch": "Update dispatch and delivery fields",
    "crm.report.view": "View CRM reports",
    "crm.master.view": "View master lists (dropdowns)",
    "crm.master.manage": "Manage master lists (dropdowns)",
}


def module_of(code: str) -> str:
    return code.split(".", 1)[0]
