// K4: population count, parity and highest set bit using division by two
// (in the spirit of the MiBench bitcount kernel, without bitwise operators).
// input: 6 0 1 7 255 1023 65535
#include <stdio.h>

int popcount(int x) {
    int c = 0;
    while (x > 0) {
        c = c + x % 2;
        x = x / 2;
    }
    return c;
}

int highest_bit(int x) {
    int h = 0 - 1;
    while (x > 0) {
        h = h + 1;
        x = x / 2;
    }
    return h;
}

int main() {
    int n;
    int v;
    int total = 0;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d", &v);
        int c = popcount(v);
        total = total + c;
        printf("%d\n", c);
        printf("%d\n", c % 2);
        printf("%d\n", highest_bit(v));
    }
    printf("%d\n", total);
    return 0;
}
