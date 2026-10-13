from app.modules.db.db_model import Setting, connect
from app.modules.receivers.models import RECEIVER_TABLES, ReceiverEndpoint
from app.modules.receivers.schemas import receiver_url


def upgrade():
    db = connect()
    with db.bind_ctx(RECEIVER_TABLES):
        db.create_tables(RECEIVER_TABLES, safe=True)
        # Import the common defaults for discovery. Existing agents keep their
        # legacy host list and transport until a new default is explicitly saved.
        values = {r.param: r.value for r in Setting.select().where(
            (Setting.group_id == 1) & Setting.param.in_(('master_ip', 'master_port')))}
        port = values.get('master_port') or '5100'
        for host in (values.get('master_ip') or '').split(','):
            host = host.strip()
            if not host:
                continue
            if ':' in host and not host.startswith('['):
                host = f'[{host}]'
            try:
                url = receiver_url(f'http://{host}:{port}')
            except ValueError:
                # Preserve unsupported legacy configuration verbatim; do not
                # make upgrading dependent on an operator changing addresses.
                continue
            ReceiverEndpoint.get_or_create(group=1, role='classic', url=url,
                defaults={'name': host[:160], 'kind': 'external', 'transport': 'http'})


def downgrade():
    raise RuntimeError('Receiver routing cannot be removed while agents and projects may use it')
