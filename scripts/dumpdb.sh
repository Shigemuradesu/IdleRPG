#!/bin/bash
if [ -z "$1" ]
  then
    echo "No database name supplied"
    exit 1
fi
echo "Removing old schema..."
rm schema.sql
touch schema.sql
echo "Dumping database $1..."
podman exec postgresql pg_dump -U postgres $1 --schema-only > schema.sql.tmp
echo "Adding license header..."
cat <(cat assets/licenses/agpl_header_sql.txt) schema.sql.tmp > schema.sql
rm schema.sql.tmp
