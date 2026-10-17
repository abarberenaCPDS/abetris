/*
 * Host tests for the Abetris rules (plugins/abetris/engine/src/abetris_logic.c).
 * Build and run from the project root:
 *   mkdir -p build && cc -std=c99 -Wall -Wextra -Werror -Iplugins/abetris/engine/include \
 *      tests/test_logic.c plugins/abetris/engine/src/abetris_logic.c -o build/test_logic
 *   build/test_logic
 */
#include <stdio.h>
#include <string.h>

#include "abetris_logic.h"

static int checks = 0;
static int failures = 0;

#define CHECK(cond)                                                \
    do {                                                           \
        checks++;                                                  \
        if (!(cond)) {                                             \
            failures++;                                            \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                          \
    } while (0)

/* Sorted cell keys (y * 16 + x) so shapes compare regardless of order. */
static void cell_keys(unsigned char kind, unsigned char rot, signed char ox, signed char oy, int keys[4]) {
    signed char xs[4], ys[4];
    int i, j, t;
    abl_piece_cells(kind, rot, ox, oy, xs, ys);
    for (i = 0; i < 4; i++) keys[i] = ys[i] * 16 + xs[i];
    for (i = 0; i < 4; i++) {
        for (j = i + 1; j < 4; j++) {
            if (keys[j] < keys[i]) {
                t = keys[i];
                keys[i] = keys[j];
                keys[j] = t;
            }
        }
    }
}

static int same_cells(const int a[4], const int b[4]) {
    int i;
    for (i = 0; i < 4; i++) {
        if (a[i] != b[i]) return 0;
    }
    return 1;
}

static void clear_board(void) {
    unsigned char r, c;
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) abl_board[r][c] = 0;
    }
}

static void test_spawn_shapes(void) {
    unsigned char kind;
    int keys[4];

    for (kind = 0; kind < 7; kind++) {
        cell_keys(kind, 0, 0, 0, keys);
        CHECK(keys[0] != keys[1] && keys[1] != keys[2] && keys[2] != keys[3]);
    }
    /* I: horizontal in box row 1 at spawn, vertical in box column 2 after one turn. */
    cell_keys(ABL_KIND_I, 0, 0, 0, keys);
    CHECK(keys[0] == 1 * 16 + 0 && keys[3] == 1 * 16 + 3);
    cell_keys(ABL_KIND_I, 1, 0, 0, keys);
    CHECK(keys[0] == 0 * 16 + 2 && keys[3] == 3 * 16 + 2);
    /* O never changes shape. */
    {
        int a[4], b[4];
        cell_keys(ABL_KIND_O, 0, 0, 0, a);
        cell_keys(ABL_KIND_O, 3, 0, 0, b);
        CHECK(same_cells(a, b));
    }
}

static void test_rotation_cycle(void) {
    unsigned char kind, i;
    for (kind = 0; kind < 7; kind++) {
        int start[4], now[4];
        unsigned char expect = (kind == ABL_KIND_O) ? 0 : 1;

        abl_reset(50u + kind);
        clear_board();
        abl_next = kind;
        CHECK(abl_spawn() == 1);
        cell_keys(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, start);

        /* Four clockwise turns on an empty board return to the spawn cells. */
        for (i = 0; i < 4; i++) CHECK(abl_rotate(1) == expect);
        cell_keys(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, now);
        CHECK(same_cells(start, now));

        /* Counter-clockwise undoes clockwise. */
        CHECK(abl_rotate(0) == expect);
        CHECK(abl_rotate(1) == expect);
        cell_keys(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, now);
        CHECK(same_cells(start, now));
    }
}

static void test_spawn_and_walls(void) {
    unsigned char kind;
    signed char xs[4], ys[4];
    unsigned char i;
    int minx, maxx;

    for (kind = 0; kind < 7; kind++) {
        abl_reset(1234u + kind);
        clear_board();
        abl_next = kind;
        CHECK(abl_spawn() == 1);
        CHECK(abl_cur_kind == kind);
        CHECK(abl_cur_y == 0);

        abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
        minx = 99;
        maxx = -99;
        for (i = 0; i < 4; i++) {
            if (xs[i] < minx) minx = xs[i];
            if (xs[i] > maxx) maxx = xs[i];
            CHECK(ys[i] >= 0 && ys[i] < ABL_BOARD_H);
        }
        /* Top centre: columns 3..5 for most pieces, 3..6 for I, 4..5 for O. */
        CHECK(minx >= 3 && maxx <= 6);

        while (abl_move(-1, 0)) {
        }
        abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
        minx = 99;
        for (i = 0; i < 4; i++) {
            if (xs[i] < minx) minx = xs[i];
        }
        CHECK(minx == 0);

        while (abl_move(1, 0)) {
        }
        abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
        maxx = -99;
        for (i = 0; i < 4; i++) {
            if (xs[i] > maxx) maxx = xs[i];
        }
        CHECK(maxx == ABL_BOARD_W - 1);
    }
}

static void test_rotation_blocked(void) {
    unsigned char r, c, i;
    signed char xs[4], ys[4];
    unsigned char rot;
    signed char x, y;

    /* A vertical I pressed against the left wall still turns. */
    abl_reset(7u);
    clear_board();
    abl_next = ABL_KIND_I;
    abl_spawn();
    while (abl_move(-1, 0)) {
    }
    CHECK(abl_rotate(1) == 1);
    abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
    for (i = 0; i < 4; i++) CHECK(xs[i] >= 0 && xs[i] < ABL_BOARD_W);

    /* With the board full around the piece, no orientation or kick fits. */
    abl_reset(8u);
    clear_board();
    abl_next = ABL_KIND_T;
    abl_spawn();
    rot = abl_cur_rot;
    x = abl_cur_x;
    y = abl_cur_y;
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) abl_board[r][c] = 1;
    }
    abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
    for (i = 0; i < 4; i++) abl_board[ys[i]][xs[i]] = 0;
    CHECK(abl_rotate(1) == 0);
    CHECK(abl_cur_rot == rot && abl_cur_x == x && abl_cur_y == y);

    /* O never rotates. */
    abl_reset(9u);
    clear_board();
    abl_next = ABL_KIND_O;
    abl_spawn();
    CHECK(abl_rotate(1) == 0);
}

static void test_lock_and_clear(void) {
    unsigned char c, r;
    unsigned int mask;

    abl_reset(11u);
    clear_board();
    /* Row 15 is full except column 9. Row 14 holds one cell in column 0. */
    for (c = 0; c < 9; c++) abl_board[15][c] = 2;
    abl_board[14][0] = 5;

    /* Vertical I in column 9, rows 12..15. It completes row 15 only. */
    abl_cur_kind = ABL_KIND_I;
    abl_cur_rot = 1;
    abl_cur_x = 7;
    abl_cur_y = 12;
    CHECK(abl_can_fall() == 0);
    CHECK(abl_board[14][9] == 0);
    mask = abl_lock();
    CHECK(mask == (1u << 15));
    abl_remove_rows(mask);
    abl_add_clear(1);
    /* Old row 14 (column 0 and the I's cell) drops to row 15. */
    CHECK(abl_board[15][0] == 5);
    CHECK(abl_board[15][9] == ABL_KIND_I + 1);
    for (c = 1; c < 9; c++) CHECK(abl_board[15][c] == 0);
    /* Old rows 13 and 12 held only the I's cells and shift down by one. */
    CHECK(abl_board[14][9] == ABL_KIND_I + 1 && abl_board[14][0] == 0);
    CHECK(abl_board[13][9] == ABL_KIND_I + 1);
    CHECK(abl_board[12][9] == 0);
    CHECK(abl_lines == 1);
    CHECK(abl_score == 40);

    /* Two separate full rows are removed together and the rows between shift down.
     * Kept rows from the bottom: 15,14,...,6,4,2,1,0 land on 15,...,4. */
    clear_board();
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) abl_board[r][c] = (unsigned char)(1 + (r % 6));
    }
    abl_remove_rows((1u << 3) | (1u << 5));
    CHECK(abl_board[4][0] == 1 + (2 % 6));  /* old row 2 */
    CHECK(abl_board[5][0] == 1 + (4 % 6));  /* old row 4 */
    CHECK(abl_board[15][0] == 1 + (15 % 6));
    CHECK(abl_board[0][0] == 0 && abl_board[1][0] == 0);
}

static void test_scoring_and_levels(void) {
    abl_reset(3u);
    CHECK(abl_score == 0 && abl_level == 0 && abl_lines == 0);

    abl_add_clear(4);                      /* Abetris at level 0 */
    CHECK(abl_score == 1200 && abl_lines == 4 && abl_level == 0);
    abl_add_clear(1);                      /* single at level 0 */
    CHECK(abl_score == 1240 && abl_lines == 5 && abl_level == 0);
    abl_add_clear(4);
    CHECK(abl_score == 2440 && abl_lines == 9 && abl_level == 0);
    abl_add_clear(1);                      /* tenth line: level 1 */
    CHECK(abl_score == 2480 && abl_lines == 10 && abl_level == 1);
    abl_add_clear(1);                      /* points use level 1: 40 * 2 */
    CHECK(abl_score == 2560 && abl_lines == 11 && abl_level == 1);
    abl_add_clear(4);                      /* Abetris at level 1: 1200 * 2 */
    CHECK(abl_score == 4960 && abl_lines == 15 && abl_level == 1);
    abl_add_points(2);
    CHECK(abl_score == 4962);

    /* Level 2 at 20 lines, level 3 at 30, then the level stays at 3. */
    abl_reset(4u);
    abl_add_clear(4);
    abl_add_clear(4);
    abl_add_clear(2);                      /* 10 lines */
    CHECK(abl_lines == 10 && abl_level == 1);
    abl_add_clear(4);
    abl_add_clear(4);
    abl_add_clear(2);                      /* 20 lines */
    CHECK(abl_lines == 20 && abl_level == 2);
    abl_add_clear(4);
    abl_add_clear(4);
    abl_add_clear(2);                      /* 30 lines */
    CHECK(abl_lines == 30 && abl_level == 3);
    abl_add_clear(4);
    abl_add_clear(4);
    CHECK(abl_level == 3);

    /* Score and lines cap instead of wrapping. */
    abl_reset(5u);
    {
        int i;
        for (i = 0; i < 2000; i++) abl_add_clear(4);
    }
    CHECK(abl_score == 999999UL);
    CHECK(abl_lines == 999);
}

static void test_gravity(void) {
    unsigned char lvl;
    const unsigned char expect[4] = {48, 32, 20, 12};
    abl_reset(6u);
    for (lvl = 0; lvl < 4; lvl++) {
        abl_level = lvl;
        CHECK(abl_gravity_frames() == expect[lvl]);
    }
}

static void test_bag(void) {
    unsigned char seen[7];
    unsigned char run, k, i;
    for (run = 0; run < 4; run++) {
        memset(seen, 0, sizeof seen);
        abl_reset(100u + run);
        clear_board();
        for (i = 0; i < 7; i++) {
            CHECK(abl_spawn() == 1);
            seen[abl_cur_kind] = 1;
        }
        for (k = 0; k < 7; k++) CHECK(seen[k] == 1);
    }
}

static void test_game_over(void) {
    unsigned char c, kind;
    for (kind = 0; kind < 7; kind++) {
        abl_reset(21u);
        clear_board();
        for (c = 0; c < ABL_BOARD_W; c++) {
            abl_board[0][c] = 1;
            abl_board[1][c] = 1;
        }
        abl_next = kind;
        CHECK(abl_spawn() == 0);
    }
}

static void test_fall_to_floor(void) {
    abl_reset(31u);
    clear_board();
    abl_next = ABL_KIND_O;
    abl_spawn();
    while (abl_move(0, 1)) {
    }
    CHECK(abl_can_fall() == 0);
    CHECK(abl_cur_y == ABL_BOARD_H - 2);
}

int main(void) {
    test_spawn_shapes();
    test_rotation_cycle();
    test_spawn_and_walls();
    test_rotation_blocked();
    test_lock_and_clear();
    test_scoring_and_levels();
    test_gravity();
    test_bag();
    test_game_over();
    test_fall_to_floor();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
