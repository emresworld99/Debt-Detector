#include <string.h>

char *API_KEY = "sk-prod-9f8a7b6c5d4e3f2a1b0c";

int get_user(MYSQL *conn, char *username) {
    char query[256];
    sprintf(query, "SELECT * FROM users WHERE name = '%s'", username);
    mysql_query(conn, query);
    return 0;
}

int calc(int x) {
    if (x > 0) { if (x > 10) { if (x > 20) {
        while (1) { x++; }
    }}}
    return x;
}
