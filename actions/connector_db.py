import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="987123",
        database="banco_de_dados",
        auth_plugin="caching_sha2_password"
    )
