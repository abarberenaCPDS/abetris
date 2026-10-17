/*
 * Abetris rules. See include/abetris_logic.h. No GBDK headers on purpose.
 *
 * Each piece is listed in its spawn orientation inside a square box (4x4 for
 * the I piece, 2x2 for O, 3x3 for the rest). Clockwise rotation maps (x, y) to
 * (n - 1 - y, x) inside the box, which keeps every piece turning about its own
 * centre. O never rotates.
 */
#include "abetris_logic.h"

#if defined(__SDCC)
#pragma bank 255
#endif

unsigned char abl_board[ABL_BOARD_H][ABL_BOARD_W];
signed char abl_cur_x, abl_cur_y;
unsigned char abl_cur_kind, abl_cur_rot, abl_next;
unsigned long abl_score;
unsigned int abl_lines;
unsigned char abl_level;

static const signed char abl_base_x[7][4] = {
    {0, 1, 2, 3}, /* I */
    {0, 1, 0, 1}, /* O */
    {1, 0, 1, 2}, /* T */
    {1, 2, 0, 1}, /* S */
    {0, 1, 1, 2}, /* Z */
    {0, 0, 1, 2}, /* J */
    {2, 0, 1, 2}, /* L */
};

static const signed char abl_base_y[7][4] = {
    {1, 1, 1, 1}, /* I */
    {0, 0, 1, 1}, /* O */
    {0, 1, 1, 1}, /* T */
    {0, 0, 1, 1}, /* S */
    {0, 0, 1, 1}, /* Z */
    {0, 1, 1, 1}, /* J */
    {0, 1, 1, 1}, /* L */
};

static const signed char abl_box[7] = {4, 2, 3, 3, 3, 3, 3};
static const signed char abl_spawn_x[7] = {3, 4, 3, 3, 3, 3, 3};

/* Wall-kick offsets, tried in order: stay, left, right, up, then wider. */
static const signed char abl_kick_x[8] = {0, -1, 1, 0, -1, 1, -2, 2};
static const signed char abl_kick_y[8] = {0, 0, 0, -1, -1, -1, 0, 0};

/* Single, double, triple, Abetris (four rows). Multiplied by level + 1. */
static const unsigned int abl_line_points[5] = {0, 40, 100, 300, 1200};

/* Frames per row by level: 48 is easy, 12 is the fastest. */
static const unsigned char abl_gravity[4] = {48, 32, 20, 12};

static unsigned int abl_rng;
static unsigned char abl_bag[7];
static unsigned char abl_bag_pos;

void abl_piece_cells(unsigned char kind, unsigned char rot, signed char ox, signed char oy, signed char *xs, signed char *ys) ABL_FN {
    unsigned char i, r;
    signed char n = abl_box[kind];
    signed char x, y, t;

    if (kind == ABL_KIND_O) rot = 0;
    for (i = 0; i < 4; i++) {
        x = abl_base_x[kind][i];
        y = abl_base_y[kind][i];
        for (r = 0; r < rot; r++) {
            t = x;
            x = (signed char)(n - 1 - y);
            y = t;
        }
        xs[i] = (signed char)(ox + x);
        ys[i] = (signed char)(oy + y);
    }
}

static unsigned char abl_collides(unsigned char kind, unsigned char rot, signed char ox, signed char oy) {
    signed char xs[4], ys[4];
    unsigned char i;

    abl_piece_cells(kind, rot, ox, oy, xs, ys);
    for (i = 0; i < 4; i++) {
        if (xs[i] < 0 || xs[i] >= ABL_BOARD_W || ys[i] < 0 || ys[i] >= ABL_BOARD_H) return 1;
        if (abl_board[ys[i]][xs[i]]) return 1;
    }
    return 0;
}

static unsigned char abl_rand_below(unsigned char n) {
    abl_rng = (unsigned int)(abl_rng * 25173u + 13849u);
    return (unsigned char)((abl_rng >> 4) % n);
}

/* 7-bag: every kind appears once in each run of seven spawns. */
static unsigned char abl_draw_kind(void) {
    unsigned char i, j, t, kind;

    if (abl_bag_pos >= 7) {
        for (i = 0; i < 7; i++) abl_bag[i] = i;
        for (i = 7; i > 1; i--) {
            j = abl_rand_below(i);
            t = abl_bag[i - 1];
            abl_bag[i - 1] = abl_bag[j];
            abl_bag[j] = t;
        }
        abl_bag_pos = 0;
    }
    kind = abl_bag[abl_bag_pos];
    abl_bag_pos++;
    return kind;
}

void abl_reset(unsigned int seed) ABL_FN {
    unsigned char r, c;

    abl_rng = (unsigned int)(seed | 1u);
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) abl_board[r][c] = 0;
    }
    abl_score = 0;
    abl_lines = 0;
    abl_level = 0;
    abl_bag_pos = 7;
    abl_next = abl_draw_kind();
    abl_cur_kind = abl_next;
    abl_cur_rot = 0;
    abl_cur_x = abl_spawn_x[abl_cur_kind];
    abl_cur_y = 0;
}

unsigned char abl_spawn(void) ABL_FN {
    abl_cur_kind = abl_next;
    abl_next = abl_draw_kind();
    abl_cur_rot = 0;
    abl_cur_x = abl_spawn_x[abl_cur_kind];
    abl_cur_y = 0;
    return !abl_collides(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y);
}

unsigned char abl_move(signed char dx, signed char dy) ABL_FN {
    if (abl_collides(abl_cur_kind, abl_cur_rot, (signed char)(abl_cur_x + dx), (signed char)(abl_cur_y + dy))) return 0;
    abl_cur_x = (signed char)(abl_cur_x + dx);
    abl_cur_y = (signed char)(abl_cur_y + dy);
    return 1;
}

unsigned char abl_rotate(unsigned char clockwise) ABL_FN {
    unsigned char next, k;

    if (abl_cur_kind == ABL_KIND_O) return 0;
    next = clockwise ? (unsigned char)((abl_cur_rot + 1) & 3) : (unsigned char)((abl_cur_rot + 3) & 3);
    for (k = 0; k < 8; k++) {
        signed char nx = (signed char)(abl_cur_x + abl_kick_x[k]);
        signed char ny = (signed char)(abl_cur_y + abl_kick_y[k]);
        if (!abl_collides(abl_cur_kind, next, nx, ny)) {
            abl_cur_rot = next;
            abl_cur_x = nx;
            abl_cur_y = ny;
            return 1;
        }
    }
    return 0;
}

unsigned char abl_can_fall(void) ABL_FN {
    return !abl_collides(abl_cur_kind, abl_cur_rot, abl_cur_x, (signed char)(abl_cur_y + 1));
}

unsigned int abl_lock(void) ABL_FN {
    signed char xs[4], ys[4];
    unsigned char i, r, c, full;
    unsigned int mask = 0;

    abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
    for (i = 0; i < 4; i++) abl_board[ys[i]][xs[i]] = (unsigned char)(abl_cur_kind + 1);

    for (r = 0; r < ABL_BOARD_H; r++) {
        full = 1;
        for (c = 0; c < ABL_BOARD_W; c++) {
            if (!abl_board[r][c]) {
                full = 0;
                break;
            }
        }
        if (full) mask |= (1u << r);
    }
    return mask;
}

void abl_remove_rows(unsigned int mask) ABL_FN {
    signed char src, dst = ABL_BOARD_H - 1;
    unsigned char r, c, removed = 0;

    for (src = ABL_BOARD_H - 1; src >= 0; src--) {
        if (mask & (1u << src)) {
            removed++;
            continue;
        }
        if (dst != src) {
            for (c = 0; c < ABL_BOARD_W; c++) abl_board[dst][c] = abl_board[src][c];
        }
        dst--;
    }
    for (r = 0; r < removed; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) abl_board[r][c] = 0;
    }
}

void abl_add_clear(unsigned char rows) ABL_FN {
    unsigned char level;

    if (rows == 0) return;
    if (rows > 4) rows = 4;
    abl_score += (unsigned long)abl_line_points[rows] * (unsigned long)(abl_level + 1);
    if (abl_score > 999999UL) abl_score = 999999UL;

    abl_lines += rows;
    if (abl_lines > 999) abl_lines = 999;

    level = (unsigned char)(abl_lines / 10);
    if (level > ABL_LEVEL_MAX) level = ABL_LEVEL_MAX;
    abl_level = level;
}

void abl_add_points(unsigned char points) ABL_FN {
    abl_score += points;
    if (abl_score > 999999UL) abl_score = 999999UL;
}

unsigned char abl_gravity_frames(void) ABL_FN {
    return abl_gravity[abl_level];
}
