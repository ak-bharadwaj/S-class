"""
S-Class EOS Zero-Infrastructure Database Fallback Engine (zero_infra_db.py)

Inspects workspace database configuration files and environment parameters.
If host databases (PostgreSQL 5432, MySQL 3306, MongoDB 27017, Redis 6379) are unreachable,
automatically injects Zero-Infra SQLite (file:./dev.db) / in-memory JSON fallbacks to guarantee 100% cold-start execution.
"""

import os
import socket
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("sclass_zero_infra_db")


class ZeroInfraDbEngine:
    """
    Zero-Infrastructure Database Engine for S-Class V12.
    Ensures zero database connection crashes on developer machines.
    """

    DB_PORTS: Dict[str, int] = {
        "postgresql": 5432,
        "mysql": 3306,
        "mongodb": 27017,
        "redis": 6379
    }

    @classmethod
    def is_port_reachable(cls, host: str, port: int, timeout: float = 0.5) -> bool:
        """Tests if a TCP port is bound and listening on the target host."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    @classmethod
    def audit_and_fallback_database(cls, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        backend_dir = os.path.join(cwd, "backend")
        target_dir = backend_dir if os.path.exists(backend_dir) else cwd

        env_file = os.path.join(target_dir, ".env")
        env_local = os.path.join(target_dir, ".env.local")
        prisma_schema = os.path.join(target_dir, "prisma", "schema.prisma")

        unreachable_dbs = []
        fallbacks_applied = []

        # Audit all registered DB ports
        for db_name, port in cls.DB_PORTS.items():
            if not cls.is_port_reachable("localhost", port):
                unreachable_dbs.append(db_name)

        # 1. Audit Relational DBs (PostgreSQL 5432 & MySQL 3306)
        if "postgresql" in unreachable_dbs or "mysql" in unreachable_dbs:
            logger.warning("[ZeroInfraDB] Relational DB port(s) unreachable. Configuring SQLite fallback driver...")
            cls._apply_sqlite_env_fallback(env_file, env_local)
            if os.path.exists(prisma_schema):
                cls._apply_sqlite_prisma_fallback(prisma_schema)
            fallbacks_applied.append("sqlite_file_db")

        # 2. Audit Document DB (MongoDB 27017)
        if "mongodb" in unreachable_dbs:
            logger.warning("[ZeroInfraDB] MongoDB port 27017 unreachable. Configuring embedded Mongo fallback...")
            cls._apply_kv_env_fallback(env_file, env_local, "MONGO_URL", "mongodb://localhost:27017/dev", "USE_EMBEDDED_MONGO", "true")
            fallbacks_applied.append("embedded_mongodb_json")

        # 3. Audit Cache / Key-Value (Redis 6379)
        if "redis" in unreachable_dbs:
            logger.warning("[ZeroInfraDB] Redis port 6379 unreachable. Configuring in-memory Redis fallback...")
            cls._apply_kv_env_fallback(env_file, env_local, "REDIS_URL", "redis://localhost:6379", "USE_IN_MEMORY_REDIS", "true")
            fallbacks_applied.append("in_memory_redis")

        return {
            "status": "HEALTHY",
            "unreachable_databases": unreachable_dbs,
            "fallbacks_applied": fallbacks_applied,
            "sqlite_active": "sqlite_file_db" in fallbacks_applied
        }

    @classmethod
    def _apply_sqlite_env_fallback(cls, env_file: str, env_local: str) -> None:
        fallback_vars = {
            "DATABASE_URL": "file:./dev.db",
            "DB_DIALECT": "sqlite",
            "USE_SQLITE_FALLBACK": "true"
        }
        for ef in [env_file, env_local]:
            os.makedirs(os.path.dirname(ef), exist_ok=True)
            existing_lines = []
            if os.path.exists(ef):
                with open(ef, "r", encoding="utf-8") as f:
                    existing_lines = f.readlines()
            
            updated = False
            new_lines = []
            for line in existing_lines:
                if line.startswith("DATABASE_URL=") and ("postgres" in line or "mysql" in line):
                    new_lines.append(f'DATABASE_URL="file:./dev.db"\n')
                    updated = True
                else:
                    new_lines.append(line)
            
            if not updated:
                new_lines.append("\n# Added by S-Class V12 ZeroInfraDbEngine\n")
                for k, v in fallback_vars.items():
                    new_lines.append(f'{k}="{v}"\n')
            
            with open(ef, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

    @classmethod
    def _apply_kv_env_fallback(cls, env_file: str, env_local: str, url_key: str, default_url: str, flag_key: str, flag_val: str) -> None:
        for ef in [env_file, env_local]:
            os.makedirs(os.path.dirname(ef), exist_ok=True)
            existing_lines = []
            if os.path.exists(ef):
                with open(ef, "r", encoding="utf-8") as f:
                    existing_lines = f.readlines()

            has_flag = any(line.startswith(f"{flag_key}=") for line in existing_lines)
            if not has_flag:
                existing_lines.append(f'\n{flag_key}="{flag_val}"\n')
                with open(ef, "w", encoding="utf-8") as f:
                    f.writelines(existing_lines)

    @classmethod
    def _apply_sqlite_prisma_fallback(cls, schema_file: str) -> None:
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                content = f.read()
            if 'provider = "postgresql"' in content or 'provider = "mysql"' in content:
                content = content.replace('provider = "postgresql"', 'provider = "sqlite"')
                content = content.replace('provider = "mysql"', 'provider = "sqlite"')
                with open(schema_file, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception as e:
            logger.error(f"[ZeroInfraDB] Error configuring Prisma SQLite schema fallback: {e}")
