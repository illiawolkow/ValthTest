#!/bin/sh
# wait-for-postgres.sh

set -e

host="$1"
shift
# If the next argument is --, shift it off
if [ "$1" = "--" ]; then
  shift
fi

# Extract user, password, and dbname from DATABASE_URL if available in environment
# This is a simple extraction, might need adjustment based on DATABASE_URL format complexity
PGUSER=$(echo $DATABASE_URL | sed -n 's_.*postgresql\(pass\)?://\([^:]*\):.*_\2_p')
PGPASSWORD=$(echo $DATABASE_URL | sed -n 's_.*postgresql\(pass\)?://[^:]*:\([^@]*\)@.*_\2_p')
PGDATABASE=$(echo $DATABASE_URL | sed -n 's_.*@.*/\([^?]*\)_\1_p')

# Use environment variables if set, otherwise use defaults or extracted values
PGUSER=${POSTGRES_USER:-${PGUSER:-valth_user}}
PGPASSWORD=${POSTGRES_PASSWORD:-${PGPASSWORD:-valth_password}}
PGDATABASE=${POSTGRES_DB:-${PGDATABASE:-valth_db}}

# Try to connect to Postgres until it's ready
until PGPASSWORD=$PGPASSWORD psql -h "$(echo $host | cut -d: -f1)" -p "$(echo $host | cut -d: -f2 || echo 5432)" -U "$PGUSER" -d "$PGDATABASE" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec "$@" 