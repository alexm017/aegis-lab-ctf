#include <stdio.h>
#include <string.h>

/*
 * Beginner reverse binary:
 * input is transformed and compared against encoded bytes.
 */
int main(int argc, char **argv) {
    char key[128] = {0};
    const unsigned char encoded[] = {
        0x62, 0x70, 0x78, 0x64, 0x0f, 0x7c, 0x68, 0x65, 0x70, 0x13, 0x68, 0x7f, 0x7e, 0x6b
    };
    size_t i = 0;

    if (argc > 1) {
        strncpy(key, argv[1], sizeof(key) - 1);
    } else {
        printf("License key: ");
        if (!fgets(key, sizeof(key), stdin)) {
            return 1;
        }
    }

    key[strcspn(key, "\r\n")] = '\0';

    if (strlen(key) != 14 || key[4] != '-' || key[9] != '-') {
        puts("Invalid key format.");
        return 1;
    }

    for (i = 0; i < 14; i++) {
        unsigned char x;
        if (key[i] == '-') {
            continue;
        }
        x = (unsigned char)key[i];
        x = (unsigned char)((x + (unsigned char)(i * 3U)) ^ 0x22U);
        if (x != encoded[i]) {
            puts("License rejected.");
            return 1;
        }
    }

    puts("License accepted.");
    puts("Token: REV-LIC-OK");
    return 0;
}

