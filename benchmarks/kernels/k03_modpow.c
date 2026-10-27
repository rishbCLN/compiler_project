// K3: modular exponentiation by repeated squaring, without bitwise operators.
// input: 3 2 10 1000 7 128 13 12345 6789 9973
#include <stdio.h>

int mulmod(int a, int b, int m) {
    return (a % m) * (b % m) % m;
}

int modpow(int base, int exp, int m) {
    int result = 1 % m;
    base = base % m;
    while (exp > 0) {
        if (exp % 2 == 1) {
            result = mulmod(result, base, m);
        }
        base = mulmod(base, base, m);
        exp = exp / 2;
    }
    return result;
}

int main() {
    int n;
    int b;
    int e;
    int m;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d %d %d", &b, &e, &m);
        printf("%d\n", modpow(b, e, m));
    }
    return 0;
}
