"""Starter departments and roles created by the seed script.

Roles are permission bundles. Admins can edit them later through the API.
Admin users (user_type = admin) implicitly hold every permission, so there is no Admin role.
"""

DEFAULT_DEPARTMENTS = [
    ("Sales", "sales"),
    ("Tender", "tender"),
    ("Purchase", "purchase"),
    ("Accounts", "accounts"),
    ("Logistics", "logistics"),
]

_SALES = [
    "crm.lead.view", "crm.lead.create", "crm.lead.update",
    "crm.contact.view", "crm.contact.create", "crm.contact.update",
    "crm.customer.view", "crm.customer.create", "crm.customer.update",
    "crm.deal.view", "crm.deal.create", "crm.deal.update",
    "crm.quote.view", "crm.quote.create", "crm.quote.update",
    "crm.order.view", "crm.report.view", "crm.master.view",
]

DEFAULT_ROLES: dict[str, tuple[str, list[str]]] = {
    "Sales Staff": ("Leads, contacts, deals and quotes", _SALES),
    "Tender Staff": ("Tender-sourced leads, deals and quotes", _SALES),
    "Purchase Staff": (
        "Fills rates on quotes",
        ["crm.customer.view", "crm.contact.view", "crm.quote.view", "crm.quote.fill_rate",
         "crm.order.view", "crm.master.view"],
    ),
    "Accounts Staff": (
        "Payment terms and payment status",
        ["crm.customer.view", "crm.deal.view", "crm.quote.view", "crm.order.view",
         "crm.order.update_payment", "crm.report.view", "crm.master.view"],
    ),
    "Logistics Staff": (
        "Dispatch and delivery updates",
        ["crm.customer.view", "crm.order.view", "crm.order.update_dispatch",
         "crm.report.view", "crm.master.view"],
    ),
    "CRM Manager": (
        "Team lead: assigns leads, approves rates, sees reports",
        _SALES + ["crm.lead.assign", "crm.lead.delete", "crm.quote.approve_rate",
                  "crm.order.create", "crm.order.update_payment", "crm.order.update_dispatch",
                  "core.department.view"],
    ),
}
