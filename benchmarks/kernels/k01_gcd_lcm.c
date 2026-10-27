// K1: greatest common divisor (Euclid) and least common multiple of input pairs.
// input: 4 48 18 1071 462 270 192 17 5
#include <stdio.h>

int gcd(int a, int b) {
    while (b != 0) {
        int r = a % b;
        a = b;
        b = r;
    }
    return a;
}

int lcm(int a, int b) {
    return a / gcd(a, b) * b;
}

int main() {
    int n;
    int a;
    int b;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d %d", &a, &b);
        printf("%d\n", gcd(a, b));
        printf("%d\n", lcm(a, b));
    }
    return 0;
}
