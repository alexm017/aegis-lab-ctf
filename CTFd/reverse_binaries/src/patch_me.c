#include <stdio.h>
#include <stdint.h>

static uint32_t guard_check(void) {
    uint32_t a = 0x11223344U;
    uint32_t b = 0x55667788U;
    uint32_t x = (a ^ b) + 0x1234U;
    return x;
}

int main(void) {
    uint32_t g = guard_check();

    puts("Patch Me");
    puts("trial build: unlock routine disabled");

    if (g != 0x13371337U) {
        puts("Activation failed.");
        return 1;
    }

    puts("Activation success.");
    puts("Token: REV-PATCH-OK");
    return 0;
}

