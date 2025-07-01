from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable, pgsql_enable, SmonHttpCheck

# Get the migrator for the current database
migrator = connect(get_migrator=True)

if pgsql_enable == '1':
    from playhouse.postgres_ext import BinaryJSONField as JSONField
elif mysql_enable == '1':
    from playhouse.mysql_ext import JSONField
else:
    from playhouse.sqlite_ext import JSONField


def upgrade():
    # Convert accepted_status_codes from CharField to JSONField
    try:
        # Step 1: Rename the existing column to a temporary name
        migrate(
            migrator.rename_column('smon_http_check', 'accepted_status_codes', 'accepted_status_codes_old'),
        )
        print("Renamed accepted_status_codes column to accepted_status_codes_old")

        # Step 2: Add a new JSONField column with the original name
        migrate(
            migrator.add_column('smon_http_check', 'accepted_status_codes', JSONField(null=True)),
        )
        print("Added new accepted_status_codes column as JSONField")

        # Step 3: Copy the data from the temporary column to the new column, converting the string values to JSON format
        # Use direct SQL query to get the data from the renamed column
        conn = connect()
        cursor = conn.execute_sql('SELECT smon_id, accepted_status_codes_old FROM smon_http_check')

        for row in cursor.fetchall():
            smon_id, old_codes = row
            if old_codes:
                # Split by comma and convert to integers
                codes_list = [int(code.strip()) for code in old_codes.split(',')]
                # Update the record with the new JSON field
                SmonHttpCheck.update(accepted_status_codes=codes_list).where(SmonHttpCheck.smon_id == smon_id).execute()

        print("Converted and copied data from old column to new JSONField column")

        # Step 4: Drop the temporary column
        migrate(
            migrator.drop_column('smon_http_check', 'accepted_status_codes_old'),
        )
        print("Dropped temporary column accepted_status_codes_old")

    except Exception as e:
        print(f"Error converting accepted_status_codes to JSONField: {e}")


def downgrade():
    # Convert accepted_status_codes back from JSONField to CharField
    try:
        # Step 1: Rename the existing column to a temporary name
        migrate(
            migrator.rename_column('smon_http_check', 'accepted_status_codes', 'accepted_status_codes_json'),
        )
        print("Renamed accepted_status_codes column to accepted_status_codes_json")

        # Step 2: Add a new CharField column with the original name
        migrate(
            migrator.add_column('smon_http_check', 'accepted_status_codes', CharField(constraints=[SQL("DEFAULT '200'")])),
        )
        print("Added new accepted_status_codes column as CharField")

        # Step 3: Copy the data from the temporary column to the new column, converting the JSON values to string format
        # Use direct SQL query to get the data from the renamed column
        conn = connect()
        cursor = conn.execute_sql('SELECT smon_id, accepted_status_codes_json FROM smon_http_check')

        for row in cursor.fetchall():
            smon_id, json_codes = row
            if json_codes:
                # Convert the list of integers to a comma-separated string
                codes_string = ','.join(str(code) for code in json_codes)
                # Update the record with the new string field
                SmonHttpCheck.update(accepted_status_codes=codes_string).where(SmonHttpCheck.smon_id == smon_id).execute()

        print("Converted and copied data from JSON column to new CharField column")

        # Step 4: Drop the temporary column
        migrate(
            migrator.drop_column('smon_http_check', 'accepted_status_codes_json'),
        )
        print("Dropped temporary column accepted_status_codes_json")

    except Exception as e:
        print(f"Error converting accepted_status_codes back to CharField: {e}")
