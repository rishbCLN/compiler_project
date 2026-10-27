// K7: Fibonacci numbers, iterative and recursive, for an input n.
// input: 20 15
#include <stdio.h>

int fib_iter(int n) {
    int a = 0;
    int b = 1;
    for (int i = 0; i < n; i = i + 1) {
        int t = a + b;
        a = b;
        b = t;
    }
    return a;
}

int fib_rec(int n) {
    if (n < 2) {
        return n;
    }
    return fib_rec(n - 1) + fib_rec(n - 2);
}

int main() {
    int n;
    int m;
    scanf("%d %d", &n, &m);
    printf("%d\n", fib_iter(n));
    printf("%d\n", fib_rec(m));
    printf("%d\n", fib_iter(m) == fib_rec(m));
    return 0;
}
