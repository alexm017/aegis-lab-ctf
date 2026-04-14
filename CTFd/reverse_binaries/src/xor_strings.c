#include <stdio.h>
#include <string.h>

int main(void) {
    char buf[128] = {0};
    const unsigned char cipher[] = {
        0x1f, 0x0c, 0x0e, 0x0a, 0x16, 0x39, 0x13, 0x0c, 0x06
    };
    const unsigned char key = 0x6a;
    char plain[sizeof(cipher) + 1];
    size_t i;

    puts("== XOR Strings ==");
    printf("passphrase: ");
    if (!fgets(buf, sizeof(buf), stdin)) {
        return 1;
    }
    buf[strcspn(buf, "\r\n")] = '\0';

    for (i = 0; i < sizeof(cipher); i++) {
        plain[i] = (char)(cipher[i] ^ key);
    }
    plain[sizeof(cipher)] = '\0';

    if (strcmp(buf, plain) != 0) {
        puts("nope");
        return 1;
    }

    puts("nice");
    puts("Token: REV-XOR-OK");
    return 0;
}

