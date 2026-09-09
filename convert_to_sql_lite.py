import duckdb

# Connect to your existing DuckDB file
con = duckdb.connect("digible_analytics.duckdb")

# Install SQLite extension & export tables
con.execute("INSTALL sqlite; LOAD sqlite;")
con.execute("ATTACH 'digible_analytics.db' AS sqlite_db (TYPE SQLITE);")

# Copy Silver and Gold views into standard SQLite tables
con.execute(
    "CREATE TABLE sqlite_db.gold_account_health AS SELECT * FROM"
    " fionacalls.gold_account_health;"
)
con.execute(
    "CREATE TABLE sqlite_db.stg_structured_calls AS SELECT * FROM"
    " fionacalls.stg_structured_calls;"
)

print("Successfully exported to digible_analytics.db!")
con.close()