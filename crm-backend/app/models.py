"""Import model packages so SQLAlchemy metadata and Alembic see every table.

Keep this registry at the application level. A registry under ``shared`` would
make shared infrastructure import business modules as the monolith grows.
"""

from app.shared import models as _shared_models  # noqa: F401

# Register each business module here when it first owns SQLAlchemy models.
# Example: from app.modules.crm import models as _crm_models  # noqa: F401
