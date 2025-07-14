#!/bin/bash
# This script creates a logical replica from the master database

set -e
set -o errexit
set -o nounset

# First we need to unset PGPASSWORD, more info at here:
#     https://forums.docker.com/t/docker-postgres-13-image-unable-to-execute-pg-basebackup-during-init/116093
unset PGPASSWORD

postgresql_conf="/home/postgres/pgdata/data/postgresql.conf"
pg_hba_conf="/home/postgres/pgdata/data/pg_hba.conf"
replica_path="/home/postgres/replica"
configured_flag="/home/postgres/replica/SUCCESSFULLY_CONFIGURED"

 # Create the pgpass file, syntax: "hostname:port:database:username:password"
echo "${db_master_host}:${db_master_port}:replication:${sta_db_replicator_user}:${sta_db_replicator_password}" > ~/.pgpass
chmod 600 ~/.pgpass

if [ -f $configured_flag ]; then
  echo "Skipping basebackup"
else

  echo "stopping PostgresQL..."
  service postgresql stop

  echo "Fix replica folder permissions"
  chown 1000:1000 ${replica_path}
  chmod 700 ${replica_path}

  echo "Running pg_basebackup, this can take a while..."
  pg_basebackup -D ${replica_path} -S replication_slot_slave1 -X stream -P -U ${sta_db_replicator_user} -Fp -R  \
      -p ${db_master_port} -h ${db_master_host}

  cp $postgresql_conf $replica_path
  cp $postgresql_conf $replica_path
  echo "Cat PostgresQL conf"
  cat $postgresql_conf

  echo "data_directory =  '""${replica_path}""'" >> $postgresql_conf

  service postgresql start

  psql -c "SELECT * FROM pg_replication_slots;"

  touch $configured_flag
fi