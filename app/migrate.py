#!/usr/bin/env python3
import os
import sys
import argparse

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.db.migrations import (
    create_migration, migrate, rollback, list_migrations, MigrationError
)


def main():
    parser = argparse.ArgumentParser(description='RMON Database Migration Tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # create command
    create_parser = subparsers.add_parser('create', help='Create a new migration')
    create_parser.add_argument('name', help='Name of the migration (use lowercase letters, numbers, and underscores)')

    # migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Apply pending migrations')
    migrate_parser.add_argument('--up-to', help='Migrate up to a specific migration')

    # rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback migrations')
    rollback_parser.add_argument('--count', type=int, default=1, help='Number of migrations to rollback (default: 1)')

    # list command
    subparsers.add_parser('list', help='List all migrations and their status')

    args = parser.parse_args()

    try:
        if args.command == 'create':
            filepath = create_migration(args.name)
            print(f"Created migration file: {filepath}")
        elif args.command == 'migrate':
            migrate(args.up_to)
        elif args.command == 'rollback':
            rollback(args.count)
        elif args.command == 'list':
            list_migrations()
        else:
            parser.print_help()
    except MigrationError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
