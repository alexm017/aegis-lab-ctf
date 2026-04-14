#include <stdio.h>
#include <string.h>

/*
 * Tiny state machine. Correct move sequence wins.
 */
static int step(int state, char c) {
    switch (state) {
        case 0: return (c == 'U') ? 1 : -1;
        case 1: return (c == 'R') ? 2 : -1;
        case 2: return (c == 'R') ? 3 : -1;
        case 3: return (c == 'D') ? 4 : -1;
        case 4: return (c == 'L') ? 5 : -1;
        case 5: return (c == 'U') ? 6 : -1;
        case 6: return (c == 'L') ? 7 : -1;
        case 7: return (c == 'D') ? 8 : -1;
        default: return -1;
    }
}

int main(void) {
    char moves[128] = {0};
    int state = 0;
    size_t i;

    puts("Jump Maze");
    puts("Use only U, D, L, R");
    printf("moves: ");
    if (!fgets(moves, sizeof(moves), stdin)) {
        return 1;
    }
    moves[strcspn(moves, "\r\n")] = '\0';

    if (strlen(moves) != 8) {
        puts("wrong path");
        return 1;
    }

    for (i = 0; i < 8; i++) {
        state = step(state, moves[i]);
        if (state < 0) {
            puts("dead end");
            return 1;
        }
    }

    if (state == 8) {
        puts("maze clear");
        puts("Token: REV-JMP-OK");
        return 0;
    }

    puts("dead end");
    return 1;
}

