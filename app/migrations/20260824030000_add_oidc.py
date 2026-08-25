from app.modules.db.db_model import OidcGroupMapping, OidcIdentity, OidcProvider, connect


def upgrade():
    database = connect()
    database.create_tables(
        [OidcProvider, OidcIdentity, OidcGroupMapping],
        safe=True,
    )


def downgrade():
    database = connect()
    database.drop_tables(
        [OidcGroupMapping, OidcIdentity, OidcProvider],
        safe=True,
    )
