/*
 * Abetris rules: the seven pieces, rotation with wall kicks, locking, line
 * clears, scoring and levels. Plain C with no GBDK headers, so the same file
 * is compiled for the Game Boy and for host unit tests (tests/test_logic.c).
 */
#ifndef ABETRIS_LOGIC_H
#define ABETRIS_LOGIC_H

/* On the Game Boy the rules are banked code, so cross-bank calls need BANKED.
 * Host builds (tests/test_logic.c) have no bank switching, so the marker is empty. */
#if defined(__SDCC)
#include <gbdk/platform.h>
#define ABL_FN BANKED
#else
#define ABL_FN
#endif

#define ABL_BOARD_W 10
#define ABL_BOARD_H 16
#define ABL_LEVEL_MAX 3

/* Piece kinds, classic seven. Board cells store kind + 1 (0 = empty). */
#define ABL_KIND_I 0
#define ABL_KIND_O 1
#define ABL_KIND_T 2
#define ABL_KIND_S 3
#define ABL_KIND_Z 4
#define ABL_KIND_J 5
#define ABL_KIND_L 6

/* Board, active piece and panel values, read by the scene every frame. */
extern unsigned char abl_board[ABL_BOARD_H][ABL_BOARD_W];
extern signed char abl_cur_x, abl_cur_y;
extern unsigned char abl_cur_kind, abl_cur_rot, abl_next;
extern unsigned long abl_score;
extern unsigned int abl_lines;
extern unsigned char abl_level;

/* Start a new game. The seed only shuffles the piece bag. */
void abl_reset(unsigned int seed) ABL_FN;

/* Bring the next piece in at the top centre. Returns 0 if it cannot fit. */
unsigned char abl_spawn(void) ABL_FN;

/* Move the active piece. Returns 1 if it moved. */
unsigned char abl_move(signed char dx, signed char dy) ABL_FN;

/* Rotate clockwise (A) or counter-clockwise (B), trying wall kicks. */
unsigned char abl_rotate(unsigned char clockwise) ABL_FN;

/* 1 if the active piece can drop one more row. */
unsigned char abl_can_fall(void) ABL_FN;

/* Write the active piece into the board. Returns a bitmask of full rows. */
unsigned int abl_lock(void) ABL_FN;

/* Delete the rows set in mask and let the rows above fall. */
void abl_remove_rows(unsigned int mask) ABL_FN;

/* Score a clear of 1-4 rows at the current level, then update lines/level. */
void abl_add_clear(unsigned char rows) ABL_FN;

/* Soft-drop and other small point awards. */
void abl_add_points(unsigned char points) ABL_FN;

/* Frames per row for the current level (level 0 is the slowest). */
unsigned char abl_gravity_frames(void) ABL_FN;

/* Cells of a piece at offset (ox, oy), rotation rot (0..3). */
void abl_piece_cells(unsigned char kind, unsigned char rot, signed char ox, signed char oy, signed char *xs, signed char *ys) ABL_FN;

#endif
