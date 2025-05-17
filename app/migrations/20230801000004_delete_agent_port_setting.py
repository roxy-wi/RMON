from app.modules.db.db_model import connect, Setting

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Delete agent_port setting
    try:
        Setting.delete().where(Setting.param == 'agent_port').execute()
        print("Deleted agent_port setting")
    except Exception as e:
        print(f"Error deleting agent_port setting: {e}")


def downgrade():
    # Restore agent_port setting
    # Note: Since we don't know the original value, we're setting a default value
    try:
        Setting.insert(
            param='agent_port',
            value='5101',
            section='smon',
            desc='Agent port',
            group_id=1
        ).execute()
        print("Restored agent_port setting")
    except Exception as e:
        print(f"Error restoring agent_port setting: {e}")
