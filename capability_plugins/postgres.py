"""PostgreSQL & Database Capability Plugin for S-Class EOS."""

PLUGIN_INFO = {
    "name": "dss_builder_sql",
    "domains": ["sql", "postgres", "sqlite", "orm", "database_migration", "prisma"],
    "commands": {"migration": "npm run db:migrate"},
    "can_write": True
}
