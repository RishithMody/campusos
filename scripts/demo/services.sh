#!/usr/bin/env bash
# PostgreSQL and Redis for the demo, on whatever ports .env asks for.
#
# Idempotent: run it as often as you like. It uses Docker when the daemon is up and
# falls back to local PostgreSQL/Redis binaries when it is not -- which is the common
# case on a laptop that has just booted, and the reason this script exists rather than a
# bare `docker compose up -d` in the runbook.
#
#   ./scripts/demo/services.sh up        start both, create the database, apply migrations
#   ./scripts/demo/services.sh status    what is listening, and where the data lives
#   ./scripts/demo/services.sh stop      stop what this script started
#
# The data directory is ~/.campusos-demo by default, deliberately NOT a temp directory:
# a demo database that evaporates between a rehearsal and the talk is worse than none.
# Override with CAMPUSOS_DEMO_HOME.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOME_DIR="${CAMPUSOS_DEMO_HOME:-$HOME/.campusos-demo}"
PGDATA="$HOME_DIR/pg"
SOCKDIR="$HOME_DIR/sock"
LOGDIR="$HOME_DIR/log"

if [ ! -f "$ROOT/.env" ]; then
  echo "no $ROOT/.env -- copy backend/.env.example and groupchat/.env.example first" >&2
  exit 1
fi

# Read the ports and names out of .env rather than guessing them.
read_env() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | tr -d '"'"'"; }
DB_URL="$(read_env CAMPUSOS_DATABASE_URL)"
REDIS_URL="$(read_env CAMPUSOS_REDIS_URL)"
PG_PORT="$(printf '%s' "$DB_URL" | sed -n 's|.*@[^:]*:\([0-9]*\)/.*|\1|p')"
PG_USER="$(printf '%s' "$DB_URL" | sed -n 's|.*://\([^:@/]*\)[:@].*|\1|p')"
PG_DB="$(printf '%s' "$DB_URL" | sed -n 's|.*/\([^/?]*\)$|\1|p')"
REDIS_PORT="$(printf '%s' "$REDIS_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')"
: "${PG_PORT:?could not read a port from CAMPUSOS_DATABASE_URL}"
: "${REDIS_PORT:?could not read a port from CAMPUSOS_REDIS_URL}"

PG_BIN=""
for candidate in /opt/homebrew/opt/postgresql@15/bin /opt/homebrew/opt/postgresql@16/bin \
                 /usr/local/opt/postgresql@15/bin /usr/lib/postgresql/15/bin; do
  [ -x "$candidate/pg_ctl" ] && PG_BIN="$candidate" && break
done

pg_up()    { "${PG_BIN:-/usr/bin}/pg_isready" -h 127.0.0.1 -p "$PG_PORT" >/dev/null 2>&1; }
redis_up() { redis-cli -h 127.0.0.1 -p "$REDIS_PORT" ping >/dev/null 2>&1; }
docker_up(){ command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

wait_for() {  # wait_for <name> <predicate>
  for _ in $(seq 1 40); do
    if "$2"; then echo "  $1 is accepting connections on 127.0.0.1"; return 0; fi
    sleep 1
  done
  echo "  $1 did not come up -- see $LOGDIR" >&2
  return 1
}

cmd_up() {
  mkdir -p "$SOCKDIR" "$LOGDIR"

  if pg_up; then
    echo "  PostgreSQL already up on :$PG_PORT"
  elif docker_up; then
    echo "  starting PostgreSQL and Redis with Docker"
    (cd "$ROOT" && docker compose up -d >/dev/null)
    wait_for "PostgreSQL" pg_up
  else
    if [ -z "$PG_BIN" ]; then
      echo "no local PostgreSQL found and the Docker daemon is not running." >&2
      echo "Start Docker Desktop, or: brew install postgresql@15 redis" >&2
      exit 1
    fi
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
      echo "  creating a PostgreSQL cluster in $PGDATA"
      "$PG_BIN/initdb" -D "$PGDATA" -U "$PG_USER" --auth=trust >/dev/null
    fi
    echo "  starting PostgreSQL on :$PG_PORT (data in $PGDATA)"
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$LOGDIR/postgres.log" \
      -o "-p $PG_PORT -k $SOCKDIR -c listen_addresses=127.0.0.1" start >/dev/null
    wait_for "PostgreSQL" pg_up
  fi

  if redis_up; then
    echo "  Redis already up on :$REDIS_PORT"
  elif docker_up; then
    wait_for "Redis" redis_up
  else
    if ! command -v redis-server >/dev/null 2>&1; then
      echo "no redis-server found. brew install redis" >&2
      exit 1
    fi
    echo "  starting Redis on :$REDIS_PORT"
    redis-server --port "$REDIS_PORT" --bind 127.0.0.1 --save '' --appendonly no \
      --daemonize yes --logfile "$LOGDIR/redis.log"
    wait_for "Redis" redis_up
  fi

  # docker-compose.yml creates POSTGRES_DB=postgres; .env asks for its own database.
  if ! psql -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c '' >/dev/null 2>&1; then
    echo "  creating database $PG_DB"
    psql -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d postgres \
      -c "CREATE DATABASE \"$PG_DB\"" >/dev/null
  fi

  echo "  applying migrations"
  ( cd "$ROOT/backend" && CAMPUSOS_DATABASE_URL="$DB_URL" \
      "$ROOT/backend/.venv/bin/alembic" upgrade head >/dev/null )
  echo "  database $PG_DB is migrated"
}

cmd_status() {
  pg_up    && echo "  PostgreSQL  UP   :$PG_PORT  db=$PG_DB user=$PG_USER" \
           || echo "  PostgreSQL  DOWN :$PG_PORT"
  redis_up && echo "  Redis       UP   :$REDIS_PORT" \
           || echo "  Redis       DOWN :$REDIS_PORT"
  if pg_up; then
    echo "  data        $(psql -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
      -tAc 'SHOW data_directory' 2>/dev/null || echo '(in Docker)')"
    echo "  students    $(psql -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
      -tAc 'SELECT count(*) FROM students' 2>/dev/null || echo '?') provisioned"
  fi
}

cmd_stop() {
  if docker_up && [ -n "$(cd "$ROOT" && docker compose ps -q 2>/dev/null)" ]; then
    (cd "$ROOT" && docker compose down >/dev/null) && echo "  Docker services stopped"
  fi
  if [ -n "$PG_BIN" ] && [ -f "$PGDATA/postmaster.pid" ]; then
    "$PG_BIN/pg_ctl" -D "$PGDATA" stop -m fast >/dev/null && echo "  PostgreSQL stopped"
  fi
  redis_up && redis-cli -h 127.0.0.1 -p "$REDIS_PORT" shutdown nosave 2>/dev/null \
    && echo "  Redis stopped" || true
}

case "${1:-up}" in
  up)     cmd_up ;;
  status) cmd_status ;;
  stop)   cmd_stop ;;
  *) echo "usage: $0 [up|status|stop]" >&2; exit 2 ;;
esac
