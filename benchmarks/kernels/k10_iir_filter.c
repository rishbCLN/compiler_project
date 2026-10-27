// K10: fixed-point first-order low-pass filter over sensor samples, with
// clamping and a running minimum and maximum, as in embedded firmware.
// input: 10 100 120 80 0 -50 300 310 290 1000 -1000
#include <stdio.h>

int clamp(int v, int lo, int hi) {
    if (v < lo) {
        return lo;
    }
    if (v > hi) {
        return hi;
    }
    return v;
}

int filter_step(int state, int sample) {
    return (3 * state + clamp(sample, -500, 500)) / 4;
}

int main() {
    int n;
    int x;
    int state = 0;
    int lo = 1000000;
    int hi = -1000000;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d", &x);
        state = filter_step(state, x);
        if (state < lo) {
            lo = state;
        }
        if (state > hi) {
            hi = state;
        }
        printf("%d\n", state);
    }
    printf("%d\n", lo);
    printf("%d\n", hi);
    return 0;
}
