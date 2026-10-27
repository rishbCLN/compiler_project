// K5: Collatz sequence lengths and the input with the longest sequence.
// input: 6 1 7 27 97 871 6171
#include <stdio.h>

int collatz_steps(int n) {
    int steps = 0;
    while (n != 1) {
        if (n % 2 == 0) {
            n = n / 2;
        } else {
            n = 3 * n + 1;
        }
        steps = steps + 1;
    }
    return steps;
}

int main() {
    int count;
    int v;
    int best = 0;
    int best_steps = 0 - 1;
    scanf("%d", &count);
    for (int i = 0; i < count; i = i + 1) {
        scanf("%d", &v);
        int s = collatz_steps(v);
        printf("%d\n", s);
        if (s > best_steps) {
            best_steps = s;
            best = v;
        }
    }
    printf("%d\n", best);
    return 0;
}
