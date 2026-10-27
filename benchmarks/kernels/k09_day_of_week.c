// K9: day of the week by Zeller's congruence (0 = Saturday) for input dates,
// with a leap-year test.
// input: 4 15 10 2026 1 1 2000 29 2 2024 4 7 1776
#include <stdio.h>

int is_leap(int y) {
    if ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0) {
        return 1;
    }
    return 0;
}

int zeller(int d, int m, int y) {
    if (m < 3) {
        m = m + 12;
        y = y - 1;
    }
    int k = y % 100;
    int j = y / 100;
    return (d + 13 * (m + 1) / 5 + k + k / 4 + j / 4 + 5 * j) % 7;
}

int main() {
    int n;
    int d;
    int m;
    int y;
    scanf("%d", &n);
    for (int i = 0; i < n; i = i + 1) {
        scanf("%d %d %d", &d, &m, &y);
        printf("%d\n", zeller(d, m, y));
        printf("%d\n", is_leap(y));
    }
    return 0;
}
