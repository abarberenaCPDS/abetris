#pragma bank 255

#include <gbdk/platform.h>

#include "states/abetris.h"
#include "abetris_layout.h"
#include "abetris_logic.h"

#include "bankdata.h"
#include "camera.h"
#include "data/game_globals.h"
#include "data_manager.h"
#include "input.h"
#include "interrupts.h"
#include "scroll.h"
#include "vm.h"

/* Timing, in frames at 60 Hz. */
#define DAS_FRAMES 12        /* hold this long before the piece auto-repeats */
#define ARR_FRAMES 4         /* then move once every this many frames */
#define SOFT_FRAMES 2        /* frames per row while Down is held */
#define LOCK_FRAMES 24       /* grounded piece locks after this long */
#define LOCK_RESETS_MAX 12   /* moves that may restart the lock timer */
#define FLASH_FRAMES 24      /* cleared rows blink this long */
#define PAUSE_GRACE_FRAMES 30

#define ABETRIS_MSG_FRAMES 150u
#define LEVELUP_MSG_FRAMES 90u
#define MSG_FOREVER 0xFFFFu
#define MSG_MAX 10
#define MSG_ROW 7
#define MSG_COL 1

/* Sound requests. The scene script polls VAR_SFX_REQUEST and plays the match. */
#define SFX_ROTATE 1
#define SFX_LOCK 2
#define SFX_LINE 3
#define SFX_ABETRIS 4
#define SFX_LEVELUP 5
#define SFX_GAMEOVER 6
#define SFX_PAUSE 7

#define ST_PLAY 0
#define ST_FLASH 1
#define ST_PAUSE 2
#define ST_OVER 3

static UINT8 ab_state;
static UINT8 gtile[GLYPH_COUNT];           /* atlas glyph index -> VRAM tile id */
static UINT8 drawn[ABL_BOARD_H][ABL_BOARD_W]; /* glyph currently on screen */
static UINT16 pmask[ABL_BOARD_H];          /* active piece, one bit per column */
static UINT8 piece_live;

static UINT16 flash_mask;
static UINT8 flash_timer;
static UINT8 flash_on;

static UINT16 msg_timer;
static UINT8 msg_len;
static UINT8 msg_glyph[MSG_MAX];

static UINT8 gravity_timer;
static UINT8 lock_timer;
static UINT8 lock_resets;
static signed char hold_dir;
static UINT8 hold_frames;
static UINT8 pause_grace;
static UINT8 over_sent;

static UINT8 preview_dirty;
static UINT32 shown_score;
static UINT8 shown_level;
static UINT16 shown_lines;

static void put_glyph(UINT8 x, UINT8 y, UINT8 glyph) {
    UINT8 tile = gtile[glyph];
    set_bkg_tiles(x, y, 1, 1, &tile);
}

/* Glyph tile ids come from the play background's own tilemap, at the atlas
 * position. That map holds the VRAM ids the engine already uses, so nothing
 * here guesses tile numbers. */
static void load_glyph_tiles(void) {
    UINT8 i;
    UINT16 idx;
    for (i = 0; i < GLYPH_COUNT; i++) {
        idx = (UINT16)((ATLAS_Y + i / ATLAS_W) * image_tile_width + ATLAS_X + i % ATLAS_W);
        gtile[i] = ReadBankedUBYTE(image_ptr + idx, image_bank);
    }
}

static void draw_number(UINT8 x, UINT8 y, UINT8 digits, UINT32 value) {
    UINT8 i;
    for (i = digits; i > 0; i--) {
        put_glyph((UINT8)(x + i - 1), y, (UINT8)(GLYPH_DIGIT0 + (UINT8)(value % 10)));
        value /= 10;
    }
}

static UINT8 glyph_for(char ch) {
    if (ch >= 'A' && ch <= 'Z') return (UINT8)(GLYPH_A + (ch - 'A'));
    if (ch >= 'a' && ch <= 'z') return (UINT8)(GLYPH_A + (ch - 'a'));
    if (ch >= '0' && ch <= '9') return (UINT8)(GLYPH_DIGIT0 + (ch - '0'));
    if (ch == '!') return GLYPH_BANG;
    if (ch == '.') return GLYPH_DOT;
    if (ch == '-') return GLYPH_DASH;
    if (ch == ':') return GLYPH_COLON;
    if (ch == '/') return GLYPH_SLASH;
    return GLYPH_BLANK;
}

/* Show text across the middle of the well for frames (MSG_FOREVER = until cleared). */
static void say(const char *text, UINT16 frames) {
    msg_len = 0;
    while (text[msg_len] && msg_len < MSG_MAX) {
        msg_glyph[msg_len] = glyph_for(text[msg_len]);
        msg_len++;
    }
    msg_timer = frames;
}

static void tick_message(void) {
    if (msg_len == 0 || msg_timer == MSG_FOREVER) return;
    if (msg_timer == 0) {
        msg_len = 0;
    } else {
        msg_timer--;
    }
}

static void request_sfx(UINT8 id) {
    VM_GLOBAL(VAR_SFX_REQUEST) = id;
}

static void draw_preview(void) {
    signed char xs[4], ys[4];
    signed char minx = 127, miny = 127, maxx = -127, maxy = -127;
    UINT8 i, x, y, w, h, ox, oy;

    for (y = 0; y < 3; y++) {
        for (x = 0; x < 4; x++) put_glyph((UINT8)(NEXT_X + x), (UINT8)(NEXT_Y + y), GLYPH_BLANK);
    }

    abl_piece_cells(abl_next, 0, 0, 0, xs, ys);
    for (i = 0; i < 4; i++) {
        if (xs[i] < minx) minx = xs[i];
        if (xs[i] > maxx) maxx = xs[i];
        if (ys[i] < miny) miny = ys[i];
        if (ys[i] > maxy) maxy = ys[i];
    }
    w = (UINT8)(maxx - minx + 1);
    h = (UINT8)(maxy - miny + 1);
    ox = (UINT8)((4 - w) / 2);
    oy = (UINT8)((3 - h) / 2);
    for (i = 0; i < 4; i++) {
        put_glyph((UINT8)(NEXT_X + ox + (xs[i] - minx)), (UINT8)(NEXT_Y + oy + (ys[i] - miny)), GLYPH_CELL);
    }
    preview_dirty = 0;
}

static void draw_panel(void) {
    if (abl_score != shown_score) {
        shown_score = abl_score;
        draw_number(SCORE_X, SCORE_Y, SCORE_DIGITS, shown_score);
    }
    if (abl_level != shown_level) {
        shown_level = abl_level;
        draw_number(LEVEL_X, LEVEL_Y, 1, shown_level);
    }
    if (abl_lines != shown_lines) {
        shown_lines = abl_lines;
        draw_number(LINES_X, LINES_Y, LINES_DIGITS, shown_lines);
    }
    if (preview_dirty) draw_preview();
}

static void build_pmask(void) {
    signed char xs[4], ys[4];
    UINT8 i, r;

    for (r = 0; r < ABL_BOARD_H; r++) pmask[r] = 0;
    if (!piece_live) return;
    abl_piece_cells(abl_cur_kind, abl_cur_rot, abl_cur_x, abl_cur_y, xs, ys);
    for (i = 0; i < 4; i++) {
        if (xs[i] >= 0 && xs[i] < ABL_BOARD_W && ys[i] >= 0 && ys[i] < ABL_BOARD_H) {
            pmask[ys[i]] |= (UINT16)(1u << xs[i]);
        }
    }
}

/* What a well cell should show: message, blinking clear, active piece, then the board. */
static UINT8 cell_glyph(UINT8 r, UINT8 c) {
    if (msg_len && r == MSG_ROW && c >= MSG_COL && c < MSG_COL + msg_len) {
        return msg_glyph[c - MSG_COL];
    }
    if (flash_mask & (UINT16)(1u << r)) {
        return flash_on ? GLYPH_FLASH : GLYPH_EMPTY;
    }
    if (pmask[r] & (UINT16)(1u << c)) return GLYPH_CELL;
    return abl_board[r][c] ? GLYPH_CELL : GLYPH_EMPTY;
}

/* Only tiles whose glyph changed are written, so the VRAM writes stay small. */
static void draw_board(void) {
    UINT8 r, c, g;
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) {
            g = cell_glyph(r, c);
            if (drawn[r][c] != g) {
                drawn[r][c] = g;
                put_glyph((UINT8)(WELL_X + c), (UINT8)(WELL_Y + r), g);
            }
        }
    }
}

static void game_over(void) {
    ab_state = ST_OVER;
    piece_live = 0;
    over_sent = 0;
    say("GAME OVER", MSG_FOREVER);
    request_sfx(SFX_GAMEOVER);
}

static void spawn_piece(void) {
    lock_timer = 0;
    lock_resets = 0;
    gravity_timer = 0;
    hold_dir = 0;
    hold_frames = 0;
    preview_dirty = 1;
    if (abl_spawn()) {
        piece_live = 1;
    } else {
        piece_live = 0;
        game_over();
    }
}

/* A move while grounded restarts the lock timer, up to LOCK_RESETS_MAX times. */
static void after_move(void) {
    if (!abl_can_fall() && lock_resets < LOCK_RESETS_MAX) {
        lock_timer = 0;
        lock_resets++;
    }
}

static void start_flash(UINT16 mask) {
    UINT8 rows = 0, r;

    for (r = 0; r < ABL_BOARD_H; r++) {
        if (mask & (UINT16)(1u << r)) rows++;
    }
    flash_mask = mask;
    flash_timer = 0;
    flash_on = 1;
    ab_state = ST_FLASH;
    if (rows >= 4) {
        say("ABETRIS!", ABETRIS_MSG_FRAMES);
        request_sfx(SFX_ABETRIS);
    } else {
        request_sfx(SFX_LINE);
    }
}

static void finish_clear(void) {
    UINT8 rows = 0, r;
    UINT8 old_level = abl_level;
    UINT16 mask = flash_mask;

    for (r = 0; r < ABL_BOARD_H; r++) {
        if (mask & (UINT16)(1u << r)) rows++;
    }
    flash_mask = 0;
    flash_on = 0;
    abl_remove_rows(mask);
    abl_add_clear(rows);
    ab_state = ST_PLAY;
    if (abl_level > old_level) {
        request_sfx(SFX_LEVELUP);
        if (rows < 4) say("LEVEL UP", LEVELUP_MSG_FRAMES);
    }
    spawn_piece();
}

static void lock_piece(void) {
    UINT16 full = (UINT16)abl_lock();

    piece_live = 0;
    if (full) {
        start_flash(full);
    } else {
        request_sfx(SFX_LOCK);
        spawn_piece();
    }
}

static void enter_pause(void) {
    ab_state = ST_PAUSE;
    say("PAUSED", MSG_FOREVER);
    request_sfx(SFX_PAUSE);
}

static void play_frame(void) {
    signed char dir = 0;
    UINT8 soft;

    if (pause_grace) {
        pause_grace--;
    } else if (INPUT_START_PRESSED) {
        enter_pause();
        return;
    }

    /* A rotates clockwise, B counter-clockwise. The O piece never turns. */
    if (INPUT_A_PRESSED) {
        if (abl_rotate(1)) {
            after_move();
            request_sfx(SFX_ROTATE);
        }
    } else if (INPUT_B_PRESSED) {
        if (abl_rotate(0)) {
            after_move();
            request_sfx(SFX_ROTATE);
        }
    }

    if (INPUT_LEFT) {
        dir = -1;
    } else if (INPUT_RIGHT) {
        dir = 1;
    }

    /* One step on press, then delayed auto-shift while the direction is held. */
    if (dir != hold_dir) {
        hold_dir = dir;
        hold_frames = 0;
        if (dir && abl_move(dir, 0)) after_move();
    } else if (dir) {
        if (hold_frames < 255) hold_frames++;
        if (hold_frames >= DAS_FRAMES && ((hold_frames - DAS_FRAMES) % ARR_FRAMES) == 0) {
            if (abl_move(dir, 0)) after_move();
        }
    }

    soft = INPUT_DOWN ? 1 : 0;
    gravity_timer++;
    if (gravity_timer >= (soft ? SOFT_FRAMES : abl_gravity_frames())) {
        gravity_timer = 0;
        if (abl_move(0, 1)) {
            if (soft) abl_add_points(1);
        }
    }

    if (abl_can_fall()) {
        lock_timer = 0;
    } else {
        lock_timer++;
        if (lock_timer >= LOCK_FRAMES) lock_piece();
    }
}

static void flash_frame(void) {
    flash_timer++;
    flash_on = ((flash_timer / 3) & 1) ? 0 : 1;
    if (flash_timer >= FLASH_FRAMES) finish_clear();
}

static void pause_frame(void) {
    if (INPUT_START_PRESSED) {
        ab_state = ST_PLAY;
        msg_len = 0;
        request_sfx(SFX_PAUSE);
    }
}

/* After game over, Start asks the scene script to return to the title. */
static void over_frame(void) {
    if (INPUT_START_PRESSED && !over_sent) {
        over_sent = 1;
        VM_GLOBAL(VAR_GOTO_TITLE) = 1;
    }
}

void abetris_init(void) BANKED {
    UINT8 r, c;

    /* The play scene has no sprites, and the field must not scroll. */
    hide_sprites = TRUE;
    camera_settings = CAMERA_UNLOCKED;
    scroll_x_max = 0;
    scroll_y_max = 0;

    load_glyph_tiles();
    for (r = 0; r < ABL_BOARD_H; r++) {
        for (c = 0; c < ABL_BOARD_W; c++) drawn[r][c] = GLYPH_EMPTY;
    }

    abl_reset(DIV_REG);

    VM_GLOBAL(VAR_SFX_REQUEST) = 0;
    VM_GLOBAL(VAR_GOTO_TITLE) = 0;

    ab_state = ST_PLAY;
    piece_live = 0;
    flash_mask = 0;
    flash_timer = 0;
    flash_on = 0;
    msg_len = 0;
    msg_timer = 0;
    gravity_timer = 0;
    lock_timer = 0;
    lock_resets = 0;
    hold_dir = 0;
    hold_frames = 0;
    pause_grace = PAUSE_GRACE_FRAMES;
    over_sent = 0;
    shown_score = 0;
    shown_level = 0;
    shown_lines = 0;
    preview_dirty = 1;

    spawn_piece();
}

void abetris_update(void) BANKED {
    switch (ab_state) {
        case ST_PLAY: play_frame(); break;
        case ST_FLASH: flash_frame(); break;
        case ST_PAUSE: pause_frame(); break;
        case ST_OVER: over_frame(); break;
        default: break;
    }
    tick_message();
    build_pmask();
    draw_board();
    draw_panel();
}
