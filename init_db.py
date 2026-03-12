from db import connect, run_migrations

if __name__ == "__main__":
    conn = connect()
    run_migrations(conn)
    print("Schema initialized.")
