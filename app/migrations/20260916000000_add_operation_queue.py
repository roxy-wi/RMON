from app.modules.db.db_model import InstallationTasks, OperationJob, OperationLock, connect


def upgrade():
    database = connect()
    with database.bind_ctx([OperationJob, OperationLock]):
        database.create_tables([OperationJob, OperationLock], safe=True)
    index_name = 'installation_tasks_status_finish_date'
    if index_name not in {index.name for index in database.get_indexes('installation_tasks')}:
        from playhouse.migrate import migrate
        migrate(connect(get_migrator=True).add_index('installation_tasks', ('status', 'finish_date')))


def downgrade():
    database = connect()
    if 'operation_jobs' in database.get_tables():
        with database.bind_ctx([OperationJob]):
            if OperationJob.select().where(OperationJob.status.in_(('queued', 'running'))).exists():
                raise RuntimeError('Finish pending agent operations before rolling back this migration')
    with database.bind_ctx([OperationJob, OperationLock]):
        database.drop_tables([OperationJob, OperationLock], safe=True)
