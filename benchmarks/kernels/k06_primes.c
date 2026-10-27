// K6: trial-division primality test; counts and sums the primes up to n.
// input: 500
#include <stdio.h>

int is_prime(int n) {
    if (n < 2) {
        return 0;
    }
    int d = 2;
    while (d * d <= n) {
        if (n % d == 0) {
            return 0;
        }
        d = d + 1;
    }
    return 1;
}

int main() {
    int limit;
    int count = 0;
    int sum = 0;
    int last = 0;
    scanf("%d", &limit);
    for (int k = 2; k <= limit; k = k + 1) {
        if (is_prime(k)) {
            count = count + 1;
            sum = sum + k;
            last = k;
        }
    }
    printf("%d\n", count);
    printf("%d\n", sum);
    printf("%d\n", last);
    return 0;
}
