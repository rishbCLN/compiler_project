// K2: integer square root by Newton's method and a perfect-square test.
// input: 5 0 15 16 1000000 123456789
#include <stdio.h>

int isqrt(int n) {
    if (n < 2) {
        return n;
    }
    int x = n;
    int y = (x + n / x) / 2;
    while (y < x) {
        x = y;
        y = (x + n / x) / 2;
    }
    return x;
}

int is_square(int n) {
    int r = isqrt(n);
    if (r * r == n) {
        return 1;
    }
    return 0;
}

int main() {
    int count;
    int v;
    scanf("%d", &count);
    for (int i = 0; i < count; i = i + 1) {
        scanf("%d", &v);
        printf("%d\n", isqrt(v));
        printf("%d\n", is_square(v));
    }
    return 0;
}
