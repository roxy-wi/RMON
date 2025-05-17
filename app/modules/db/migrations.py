import os
import re
import importlib.util
from datetime import datetime
from typing import List, Optional, Tuple

from app.modules.db.db_model import Migration


class MigrationError(Exception):
    """Exception raised for migration errors."""
    pass


def get_migrations_dir() -> str:
    """
    Get the directory where migration files are stored.

    Returns:
        str: Path to the migrations directory
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    migrations_dir = os.path.join(base_dir, 'migrations')

    # Create the migrations directory if it doesn't exist
    if not os.path.exists(migrations_dir):
        os.makedirs(migrations_dir)

    return migrations_dir


def get_migration_files() -> List[str]:
    """
    Get a list of all migration files in the migrations directory.

    Returns:
        List[str]: List of migration filenames
    """
    migrations_dir = get_migrations_dir()
    migration_files = []

    for filename in os.listdir(migrations_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            migration_files.append(filename)

    return sorted(migration_files)


def get_applied_migrations() -> List[str]:
    """
    Get a list of migrations that have already been applied.

    Returns:
        List[str]: List of applied migration names
    """
    try:
        return [m.name for m in Migration.select().order_by(Migration.id)]
    except Exception as e:
        print(f"Error getting applied migrations: {e}")
        return []


def create_migration(name: str) -> str:
    """
    Create a new migration file.

    Args:
        name (str): Name of the migration

    Returns:
        str: Path to the created migration file

    Raises:
        MigrationError: If the migration name is invalid or a file with that name already exists
    """
    # Validate migration name
    if not re.match(r'^[a-z0-9_]+$', name):
        raise MigrationError("Migration name must contain only lowercase letters, numbers, and underscores")

    # Create timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{timestamp}_{name}.py"

    migrations_dir = get_migrations_dir()
    filepath = os.path.join(migrations_dir, filename)

    # Check if file already exists
    if os.path.exists(filepath):
        raise MigrationError(f"Migration file {filename} already exists")

    # Create migration file from template
    template = """from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)

def upgrade():
    # Write your upgrade migration code here
    # Example:
    # migrate(
    #     migrator.add_column('table_name', 'column_name', CharField(null=True)),
    # )
    pass

def downgrade():
    # Write your downgrade migration code here (optional)
    # Example:
    # migrate(
    #     migrator.drop_column('table_name', 'column_name'),
    # )
    pass
"""

    with open(filepath, 'w') as f:
        f.write(template)

    return filepath


def load_migration_module(filepath: str) -> Tuple[callable, callable]:
    """
    Load a migration module from a file.

    Args:
        filepath (str): Path to the migration file

    Returns:
        Tuple[callable, callable]: Upgrade and downgrade functions

    Raises:
        MigrationError: If the migration module is invalid
    """
    try:
        module_name = os.path.basename(filepath).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, 'upgrade'):
            raise MigrationError(f"Migration {module_name} does not have an upgrade function")

        upgrade_func = module.upgrade
        downgrade_func = getattr(module, 'downgrade', None)

        return upgrade_func, downgrade_func
    except Exception as e:
        raise MigrationError(f"Failed to load migration {os.path.basename(filepath)}: {str(e)}")


def apply_migration(filepath: str) -> None:
    """
    Apply a migration.

    Args:
        filepath (str): Path to the migration file

    Raises:
        MigrationError: If the migration fails
    """
    filename = os.path.basename(filepath)
    migration_name = filename.replace('.py', '')

    # Check if migration has already been applied
    if Migration.select().where(Migration.name == migration_name).exists():
        print(f"Migration {migration_name} has already been applied")
        return

    # Load migration module
    upgrade_func, _ = load_migration_module(filepath)

    # Apply migration
    try:
        print(f"Applying migration {migration_name}...")
        upgrade_func()

        # Record migration
        Migration.create(name=migration_name)
        print(f"Migration {migration_name} applied successfully")
    except Exception as e:
        raise MigrationError(f"Failed to apply migration {migration_name}: {str(e)}")


def rollback_migration(migration_name: str) -> None:
    """
    Rollback a migration.

    Args:
        migration_name (str): Name of the migration to rollback

    Raises:
        MigrationError: If the migration fails to rollback
    """
    # Check if migration has been applied
    try:
        migration = Migration.get(Migration.name == migration_name)
    except Migration.DoesNotExist:
        raise MigrationError(f"Migration {migration_name} has not been applied")

    # Find migration file
    migrations_dir = get_migrations_dir()
    filepath = os.path.join(migrations_dir, f"{migration_name}.py")

    if not os.path.exists(filepath):
        raise MigrationError(f"Migration file {migration_name}.py not found")

    # Load migration module
    _, downgrade_func = load_migration_module(filepath)

    if downgrade_func is None:
        raise MigrationError(f"Migration {migration_name} does not have a downgrade function")

    # Apply downgrade
    try:
        print(f"Rolling back migration {migration_name}...")
        downgrade_func()

        # Remove migration record
        migration.delete_instance()
        print(f"Migration {migration_name} rolled back successfully")
    except Exception as e:
        raise MigrationError(f"Failed to rollback migration {migration_name}: {str(e)}")


def migrate(up_to: Optional[str] = None) -> None:
    """
    Apply all pending migrations or up to a specific migration.

    Args:
        up_to (Optional[str]): Name of the migration to migrate up to

    Raises:
        MigrationError: If any migration fails
    """
    # Get all migration files
    migration_files = get_migration_files()

    # Get applied migrations
    applied_migrations = get_applied_migrations()

    # Determine which migrations to apply
    pending_migrations = []
    for filename in migration_files:
        migration_name = filename.replace('.py', '')
        if migration_name not in applied_migrations:
            pending_migrations.append(filename)
            if up_to and migration_name == up_to:
                break

    if not pending_migrations:
        print("No pending migrations to apply")
        return

    # Apply migrations
    migrations_dir = get_migrations_dir()
    for filename in pending_migrations:
        filepath = os.path.join(migrations_dir, filename)
        apply_migration(filepath)


def rollback(count: int = 1) -> None:
    """
    Rollback the last n migrations.

    Args:
        count (int): Number of migrations to rollback

    Raises:
        MigrationError: If any migration fails to rollback
    """
    # Get applied migrations in reverse order
    applied_migrations = list(reversed(get_applied_migrations()))

    if not applied_migrations:
        print("No migrations to rollback")
        return

    # Determine which migrations to rollback
    migrations_to_rollback = applied_migrations[:count]

    if not migrations_to_rollback:
        print("No migrations to rollback")
        return

    # Rollback migrations
    for migration_name in migrations_to_rollback:
        rollback_migration(migration_name)


def list_migrations() -> None:
    """
    List all migrations and their status.
    """
    # Get all migration files
    migration_files = get_migration_files()

    # Get applied migrations
    applied_migrations = get_applied_migrations()

    # Print migrations
    print("Migrations:")
    for filename in migration_files:
        migration_name = filename.replace('.py', '')
        status = "Applied" if migration_name in applied_migrations else "Pending"
        print(f"  {migration_name}: {status}")
