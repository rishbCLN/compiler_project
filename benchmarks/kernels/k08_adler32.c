// K8: Adler-32 style checksum over an input stream of byte values
// (the two running sums of RFC 1950, kept separate to avoid overflow).
// input: 12 87 105 107 105 112 101 100 105 97 32 49 50
#include <stdio.h>

int mod_adler(int x) {
    return x % 65521;
}

int main() {
    int n;
    int value;
    int a = 1;
    int b = 0;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d", &value);
        a = mod_adler(a + value);
        b = mod_adler(b + a);
    }
    printf("%d\n", a);
    printf("%d\n", b);
    return 0;
}
