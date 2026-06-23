int get_admin(MYSQL *conn, char *username) {
    char query[256];
    sprintf(query, "SELECT * FROM admins WHERE name = '%s'", username);
    mysql_query(conn, query);
    return 0;
}

int add_numbers(int a, int b) {
    return a + b;
}
