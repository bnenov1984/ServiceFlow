import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import every module that defines tables so autogenerate sees the full metadata.
from business_os.identity import models as _identity_models  # noqa: F401
from business_os.platform_admin import models as _platform_admin_models  # noqa: F401
from business_os.shared_kernel.db import Base
from professional_services.actions import models as _ps_actions_models  # noqa: F401
from professional_services.assignments import models as _ps_assignments_models  # noqa: F401
from professional_services.catalog import models as _ps_catalog_models  # noqa: F401
from professional_services.clients import models as _ps_clients_models  # noqa: F401
from serviceflow.assets import models as _assets_models  # noqa: F401
from serviceflow.attachments import models as _attachments_models  # noqa: F401
from serviceflow.catalog import models as _catalog_models  # noqa: F401
from serviceflow.commercial import models as _commercial_models  # noqa: F401
from serviceflow.contacts import models as _contacts_models  # noqa: F401
from serviceflow.customers import models as _customers_models  # noqa: F401
from serviceflow.service_orders import models as _service_orders_models  # noqa: F401
from serviceflow.tasks import models as _tasks_models  # noqa: F401
from serviceflow.timeline import models as _timeline_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which silently disables any
    # logger already created before this runs (e.g. business_os.identity.
    # router's, if some earlier-imported module already grabbed it) since
    # alembic.ini's [loggers] only lists root/sqlalchemy/alembic. Confirmed
    # bug: this made a caplog-based test flip pass/fail depending on whether
    # an unrelated, earlier-collected test file happened to import the app
    # (and thus that logger) before the first migration ran.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# URL comes from the environment (ADR-017: config via env), never from alembic.ini.
_url = os.environ.get("SERVICEFLOW_DATABASE_URL")
if _url:
    config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
