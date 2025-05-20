# Database Initialization Setup Guide

## Directory Structure

Create an `init-db` directory in your project root:

```
project/
├── backend/
│   └── ...
├── frontend/
│   └── ...
├── init-db/
│   ├── 01-init-tables.sql   # Database tables creation
│   └── 02-seed-data.sql     # Optional seed data
└── ...
```

## How it Works

1. **For Docker Deployment:**
   - The SQL files in the `init-db` directory are automatically executed during container startup
   - PostgreSQL executes these files in alphanumeric order (hence the numbered prefixes)
   - No manual action is required for Docker deployments

2. **For Local Development:**
   - If you want to initialize the database manually, run:
   ```bash
   # Connect to your PostgreSQL server
   psql -h localhost -U postgres -d mobeus -f init-db/01-init-tables.sql
   ```

## Adding New Migrations

When making database schema changes:

1. Create a new numbered SQL file (e.g., `03-add-user-preferences.sql`)
2. Add it to the `init-db` directory
3. For production deployments:
   - The changes will be applied on container restart
   - Make sure migrations are idempotent (use `IF NOT EXISTS` clauses)

## Troubleshooting

If tables aren't being created:

1. Check permissions on the init-db directory and files
2. Verify the volume is properly mounted in docker-compose.yml
3. Check PostgreSQL logs:
   ```bash
   docker-compose logs postgres
   ```

## Sample Commands

**List all tables:**
```sql
\dt
```

**Manually run migrations:**
```bash
cat init-db/*.sql | docker-compose exec -T postgres psql -U postgres -d mobeus
```

**Drop and recreate database:**
```bash
docker-compose exec postgres psql -U postgres -c "DROP DATABASE mobeus;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE mobeus;"
cat init-db/*.sql | docker-compose exec -T postgres psql -U postgres -d mobeus
```
