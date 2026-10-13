// Standard C Program: Preprocessor, main(), Branches, Loops & printf
// Demonstrates native C language ingestion into the IR Compression Pipeline.

#include <stdio.h>

int main() {
    int total = 0;
    int limit = 10;
    int increment = 2;

    // Diamond Decision Branch
    if (total < limit) {
        increment = 3;
    } else {
        increment = 1;
    }

    // Iterative Loop with Back-Edge
    while (total < limit) {
        total = total + increment;
    }

    printf("Computation Complete: %d\n", total);
    return 0;
}
