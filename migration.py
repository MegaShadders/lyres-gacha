import sqlite3
import os
import sys
from config import Config

db_uri = Config.DATABASE_URI
migrations_uri = Config.MIGRATIONS_URI

def upgrade_db():

    def get_current_db_version():
        with sqlite3.connect(db_uri) as con:
            cur = con.cursor()
            version = cur.execute("PRAGMA user_version").fetchone()[0]
        return version

    def get_script_version(path):
        return int(path.split('_')[0].split('/')[1])
    
    print("Checking for new migrations...")

    migration_files = list(os.listdir(migrations_uri))
    with sqlite3.connect(db_uri) as con:
        con.isolation_level = None
        cur = con.cursor()
        for migration in sorted(migration_files):
            try:
                path = "{0}{1}".format(migrations_uri, migration)
                migration_version = get_script_version(path)

                if migration_version > get_current_db_version():
                    print("Applying migration {0}".format(migration_version))
                    with open(path, 'r') as migration_file:
                        migration_script = migration_file.read()
                    cur.executescript(migration_script)
                    print("Database now at version {0}".format(migration_version))
                else:
                    print("Migration {0} already applied".format(migration_version))
            except Exception as e:
                print("Migration {0} failed".format(migration_version))
                print(e)
                sys.exit(1)

