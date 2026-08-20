import os
import sys
import pygame
import chess
import m121

SCRIPT_DIR = m121.get_script_dir()
STOCKFISH_PATH = m121.resolve_stockfish_path()

#Board layout constants
BOARD_SIZE = 512
SIDEBAR_WIDTH = 340
TOTAL_WIDTH = BOARD_SIZE + SIDEBAR_WIDTH
DIMENSION = 8
SQ_SIZE = BOARD_SIZE // DIMENSION

#RGB color tuples
SIDEBAR_BG = (38, 37, 34)
BTN_COLOR = (54, 52, 49)
BTN_HOVER = (75, 73, 69)
BTN_ACTIVE = (76, 175, 80)
BTN_DISABLED = (45, 43, 40)
TEXT_COLOR = (255, 255, 255)
TEXT_MUTED = (160, 160, 160)
LIGHT_SQ = (238, 238, 210)
DARK_SQ = (118, 150, 86)
HIGHLIGHT_COLOR = (255, 255, 0)
EVAL_BAR_WHITE = (240, 240, 240)
EVAL_BAR_BLACK = (50, 50, 50)

MODE_LABELS = {
    "HUMAN_BOT": "Human-like Bot",
    "ENGINE_BOT": "Engine Bot",
}

IMAGES = {}
USE_IMAGE_PIECES = False
analysis_cache = {"fen": None, "eval": 0.0, "lines": []}


def get_stockfish_analysis(engine, py_board, multipv=3, depth=15, time_limit=0.4):
    if py_board.is_game_over():
        return 0.0, []
    try:
        legal_count = len(list(py_board.legal_moves))
        info_list = engine.analyse(
            py_board,
            chess.engine.Limit(depth=depth, time=time_limit),
            multipv=min(multipv, legal_count),
        )
        if isinstance(info_list, dict):
            info_list = [info_list]

        lines = []
        for info in info_list:
            pv = info.get("pv")
            score = info.get("score")
            if not pv or score is None:
                continue
            move = pv[0]
            cp_white = score.pov(chess.WHITE).score(mate_score=100000)
            lines.append((move, cp_white / 100.0))

        eval_score = lines[0][1] if lines else 0.0
        return eval_score, lines
    except Exception as e:
        print(f"[DEBUG GUI]: Stockfish analysis failed: {e}")
        return 0.0, []

board = [
    ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
    ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
    ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
]

'''Piece Values for Dynamic Evaluation Fallback'''
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

PIECE_TEXT = {
    "wP": "P", "wR": "R", "wN": "N", "wB": "B", "wQ": "Q", "wK": "K",
    "bP": "p", "bR": "r", "bN": "n", "bB": "b", "bQ": "q", "bK": "k",
}


def load_images():
    global USE_IMAGE_PIECES
    print("[DEBUG GUI]: Loading piece assets...")
    pieces = ["wP", "wR", "wN", "wB", "wQ", "wK", "bP", "bR", "bN", "bB", "bQ", "bK"]
    image_dirs = [
        os.path.join(SCRIPT_DIR, "images"),
        os.path.join(os.getcwd(), "images"),
    ]

    for piece in pieces:
        loaded = False
        for image_dir in image_dirs:
            path = os.path.join(image_dir, f"{piece}.png")
            if os.path.isfile(path):
                IMAGES[piece] = pygame.transform.scale(
                    pygame.image.load(path), (SQ_SIZE, SQ_SIZE)
                )
                loaded = True
                break
        if not loaded:
            print(f"[DEBUG GUI]: Image asset missing for '{piece}'. Fallback to text rendering enabled.")
            USE_IMAGE_PIECES = False
            return

    USE_IMAGE_PIECES = True
    print("[GUI]: All piece image assets successfully loaded.")


def grid_to_square(row, col):
    files = ["a", "b", "c", "d", "e", "f", "g", "h"]
    ranks = ["8", "7", "6", "5", "4", "3", "2", "1"]
    square_str = files[col] + ranks[row]
    print(f"[DEBUG GUI]: Grid coordinates ({row}, {col}) mapped to UCI square: {square_str}")
    return square_str


def resolve_move(py_board, move_uci):
    print(f"[DEBUG GUI]: Resolving move string: '{move_uci}'")
    try:
        move = chess.Move.from_uci(move_uci)
        if move in py_board.legal_moves:
            print(f"[DEBUG GUI]: Valid direct legal move: {move.uci()}")
            return move
    except ValueError:
        pass

    if len(move_uci) == 4:
        print(f"[DEBUG GUI]: Checking pawn promotion variants for '{move_uci}'...")
        for promo in "qrbn":
            try:
                move = chess.Move.from_uci(move_uci + promo)
                if move in py_board.legal_moves:
                    print(f"[DEBUG GUI]: Promotion move identified: {move.uci()}")
                    return move
            except ValueError:
                continue

    print(f"[DEBUG GUI]: Move '{move_uci}' is illegal or invalid in current position.")
    return None


def evaluate_board_score(py_board):
    if py_board.is_checkmate():
        score = -999.0 if py_board.turn == chess.WHITE else 999.0
        print(f"[GUI]: Position is Checkmate. Score evaluated: {score}")
        return score
    if py_board.is_stalemate() or py_board.is_insufficient_material():
        print("[GUI]: Game ended in a draw. Score : 0.0")
        return 0.0

    score = 0
    for square in chess.SQUARES:
        piece = py_board.piece_at(square)
        if piece:
            val = PIECE_VALUES.get(piece.piece_type, 0)
            score += val if piece.color == chess.WHITE else -val

    evaluated_val = score / 100.0
    return evaluated_val


def analyze_top_lines(py_board, top_n=3):
    legal_moves = list(py_board.legal_moves)
    if not legal_moves:
        return []

    scored_moves = []
    for move in legal_moves:
        py_board.push(move)
        eval_val = evaluate_board_score(py_board)
        py_board.pop()
        scored_moves.append((move, eval_val))

    is_white = py_board.turn == chess.WHITE
    scored_moves.sort(key=lambda item: item[1], reverse=is_white)
    lines = scored_moves[:top_n]
    print(f"[DEBUG GUI]: Calculated top {len(lines)} line(s): {[f'{m.uci()}: {s:+.2f}' for m, s in lines]}")
    return lines


def sync_board(backend_board, visual_board):
    for row in range(8):
        for col in range(8):
            square = chess.square(col, 7 - row)
            piece = backend_board.piece_at(square)
            if piece:
                color = "w" if piece.color == chess.WHITE else "b"
                visual_board[row][col] = color + piece.symbol().upper()
            else:
                visual_board[row][col] = "--"


def highlight_selected_square(screen, selected_sq):
    if selected_sq != ():
        row, col = selected_sq
        s = pygame.Surface((SQ_SIZE, SQ_SIZE))
        s.set_alpha(100)
        s.fill(HIGHLIGHT_COLOR)
        screen.blit(s, (col * SQ_SIZE, row * SQ_SIZE))


def draw_pieces(screen, piece_font):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board[r][c]
            if piece == "--":
                continue

            rect = pygame.Rect(c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            if USE_IMAGE_PIECES and piece in IMAGES:
                screen.blit(IMAGES[piece], rect)
            else:
                color = TEXT_COLOR if piece.startswith("w") else (20, 20, 20)
                label = piece_font.render(PIECE_TEXT.get(piece, "?"), True, color)
                screen.blit(label, label.get_rect(center=rect.center))




def save_bot_game_if_needed(py_board, target_mode, player_color, game_saved):
    if game_saved:
        return True

    if target_mode not in ("HUMAN_BOT", "ENGINE_BOT") or not py_board.is_game_over():
        return False

    move_history = [move.uci() for move in py_board.move_stack]
    if not move_history:
        return True

    saved_games_path = os.path.join(SCRIPT_DIR, "saved_games.txt")
    print(f"[DEBUG GUI]: Game complete. Saving {len(move_history)} moves to {saved_games_path}")
    with open(saved_games_path, "a", encoding="utf-8") as f:
        f.write("\n".join(move_history) + "\n")

    return True

def draw_main_menu(screen, title_font, btn_font, menu_message=""):
    screen.fill(SIDEBAR_BG)

    title = title_font.render("PYTHON CHESS ENGINE", True, TEXT_COLOR)
    screen.blit(title, title.get_rect(center=(TOTAL_WIDTH // 2, 70)))

    human_bot_btn = pygame.Rect(TOTAL_WIDTH // 2 - 160, 140, 320, 50)
    engine_bot_btn = pygame.Rect(TOTAL_WIDTH // 2 - 160, 205, 320, 50)
    quit_btn = pygame.Rect(TOTAL_WIDTH // 2 - 160, 270, 320, 50)

    for btn, label, active in [
        (human_bot_btn, "Play vs Human-like Bot", True),
        (engine_bot_btn, "Play vs Engine Bot", True),
        (quit_btn, "Quit Game", True),
    ]:
        color = BTN_COLOR if active else BTN_DISABLED
        pygame.draw.rect(screen, color, btn, border_radius=8)
        txt_color = TEXT_COLOR if active else TEXT_MUTED
        txt = btn_font.render(label, True, txt_color)
        screen.blit(txt, txt.get_rect(center=btn.center))

    if menu_message:
        msg_font = pygame.font.SysFont("Arial", 15, bold=True)
        msg = msg_font.render(menu_message, True, (255, 180, 80))
        screen.blit(msg, msg.get_rect(center=(TOTAL_WIDTH // 2, 340)))

    return human_bot_btn, engine_bot_btn, quit_btn


def draw_level_menu(screen, title_font, btn_font, mode_title):
    screen.fill(SIDEBAR_BG)

    label = MODE_LABELS.get(mode_title, mode_title.replace("_", " "))
    title = title_font.render(f"SELECT LEVEL: {label}", True, TEXT_COLOR)
    screen.blit(title, title.get_rect(center=(TOTAL_WIDTH // 2, 50)))

    level_buttons = []
    grid_start_x = (TOTAL_WIDTH - (5 * 70 + 4 * 15)) // 2
    grid_start_y = 110

    for i in range(20):
        row = i // 5
        col = i % 5
        x = grid_start_x + col * (70 + 15)
        y = grid_start_y + row * (55 + 12)
        btn_rect = pygame.Rect(x, y, 70, 55)
        pygame.draw.rect(screen, BTN_COLOR, btn_rect, border_radius=6)

        level_txt = btn_font.render(f"Lvl {i + 1}", True, TEXT_COLOR)
        screen.blit(level_txt, level_txt.get_rect(center=btn_rect.center))
        level_buttons.append((btn_rect, i + 1))

    back_btn = pygame.Rect(TOTAL_WIDTH // 2 - 160, 425, 150, 45)
    quit_btn = pygame.Rect(TOTAL_WIDTH // 2 + 10, 425, 150, 45)

    pygame.draw.rect(screen, BTN_COLOR, back_btn, border_radius=6)
    pygame.draw.rect(screen, (180, 50, 50), quit_btn, border_radius=6)

    b_txt = btn_font.render("Back", True, TEXT_COLOR)
    q_txt = btn_font.render("Quit", True, TEXT_COLOR)
    screen.blit(b_txt, b_txt.get_rect(center=back_btn.center))
    screen.blit(q_txt, q_txt.get_rect(center=quit_btn.center))

    return level_buttons, back_btn, quit_btn


def draw_sidebar(screen, font, small_font, eval_score, status_text, show_eval, 
                 show_lines, top_lines, is_puzzle_mode=False):
    sidebar_rect = pygame.Rect(BOARD_SIZE, 0, SIDEBAR_WIDTH, BOARD_SIZE)
    pygame.draw.rect(screen, SIDEBAR_BG, sidebar_rect)

    text_surface = font.render(status_text[:42], True, TEXT_COLOR)
    screen.blit(text_surface, (BOARD_SIZE + 15, 15))

    y_offset = 50
    if show_eval:
        eval_txt = small_font.render(f"Eval: {eval_score:+.2f}", True, TEXT_COLOR)
        screen.blit(eval_txt, (BOARD_SIZE + 15, y_offset))

        bar_rect = pygame.Rect(BOARD_SIZE + 150, y_offset, 160, 16)
        pygame.draw.rect(screen, EVAL_BAR_BLACK, bar_rect)

        clamped_eval = max(-10.0, min(10.0, eval_score))
        white_pct = (clamped_eval + 10.0) / 20.0
        white_width = int(160 * white_pct)
        pygame.draw.rect(
            screen,
            EVAL_BAR_WHITE,
            pygame.Rect(BOARD_SIZE + 150, y_offset, white_width, 16),
        )
        y_offset += 30
    else:
        y_offset += 10

    if show_lines:
        lines_box = pygame.Rect(BOARD_SIZE + 15, y_offset, 310, 75)
        pygame.draw.rect(screen, BTN_DISABLED, lines_box, border_radius=6)

        header_txt = small_font.render("Top Engine Lines:", True, TEXT_COLOR)
        screen.blit(header_txt, (BOARD_SIZE + 25, y_offset + 5))

        for idx, (m, score) in enumerate(top_lines):
            line_str = f"{idx + 1}. {m.uci()} ({score:+.1f})"
            line_txt = small_font.render(line_str, True, TEXT_MUTED)
            screen.blit(line_txt, (BOARD_SIZE + 25, y_offset + 25 + (idx * 16)))

        y_offset += 85

    reset_btn = pygame.Rect(BOARD_SIZE + 15, y_offset, 148, 38)
    undo_btn = pygame.Rect(BOARD_SIZE + 177, y_offset, 148, 38)
    y_offset += 45
    eval_toggle_btn = pygame.Rect(BOARD_SIZE + 15, y_offset, 148, 35)
    lines_toggle_btn = pygame.Rect(BOARD_SIZE + 177, y_offset, 148, 35)
    y_offset += 42
   
    menu_btn = pygame.Rect(BOARD_SIZE + 15, y_offset, 148, 38)
    quit_btn = pygame.Rect(BOARD_SIZE + 177, y_offset, 148, 38)

    btn_list = [
        (reset_btn, "Reset Game", BTN_COLOR),
        (undo_btn, "Undo Move", BTN_COLOR),
        (eval_toggle_btn, "Eval: ON" if show_eval else "Eval: OFF", BTN_ACTIVE if show_eval else BTN_COLOR),
        (lines_toggle_btn, "Lines: ON" if show_lines else "Lines: OFF", BTN_ACTIVE if show_lines else BTN_COLOR),
    ]

   
    btn_list.extend([
        (menu_btn, "Main Menu", BTN_COLOR),
        (quit_btn, "Quit Game", (180, 50, 50)),
    ])

    for btn, label, bg_col in btn_list:
        pygame.draw.rect(screen, bg_col, btn, border_radius=6)
        txt = small_font.render(label, True, TEXT_COLOR)
        screen.blit(txt, txt.get_rect(center=btn.center))

    return reset_btn, undo_btn, eval_toggle_btn, lines_toggle_btn, menu_btn, quit_btn


def handle_player_move(py_board, move, target_mode,  puzzle_step):
    move_uci = move.uci()
    print(f"player move: {move_uci} ")
    py_board.push(move)
    print(f"[DEBUG GUI]: Move {move_uci} pushed to backend board successfully.")

    if py_board.is_checkmate():
        status = "Checkmate!"
    elif py_board.is_check():
        status = "Check!"
    else:
        status = "Black's Turn" if py_board.turn == chess.BLACK else "White's Turn"

    print(f"[GUI]: Board state after move -> Status: '{status}'")
    return True, puzzle_step, status


def reset_session_state(target_mode, selected_level, game_engine):
    print(f"[DEBUG GUI]: Resetting session state for Mode: {target_mode}, Level: {selected_level}")
    current_puzzle = None
    puzzle_step = 0
    status_text = "White's Turn"

    if target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
        game_engine.board.reset()
        status_text = f"Level {selected_level} - White's Turn"
        print(f"[DEBUG GUI]: Chess board reset to standard opening position.")
    return current_puzzle, puzzle_step, status_text


def main():
    print("[DEBUG GUI]: Initializing Pygame environment...")
    pygame.init()
    screen = pygame.display.set_mode((TOTAL_WIDTH, BOARD_SIZE))
    pygame.display.set_caption("Chess Engine")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("Arial", 26, bold=True)
    ui_font = pygame.font.SysFont("Arial", 18, bold=True)
    small_font = pygame.font.SysFont("Arial", 14)
    piece_font = pygame.font.SysFont("Segoe UI Symbol", 36, bold=True)

    load_images()

    game_engine = m121.ChessBaseEngine()
    active_bot = None

    game_state = "MAIN_MENU"
    target_mode = "HUMAN_BOT"
    selected_level = 1

    selected_sq = ()
    player_clicks = []
    status_text = "Welcome!"
    menu_message = ""

    show_eval = False
    show_lines = False
    eval_score = 0.0
    top_lines = []

    current_puzzle = None
    puzzle_step = 0

    player_color = chess.WHITE
    bot_move_pending = False
    bot_think_ticks = 0
    game_saved = False

    print("[DEBUG GUI]: Main application loop entering execution state.")
    running = True
    while running:
        sync_board(game_engine.board, board)

        if game_state == "PLAYING" and target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
            game_saved = save_bot_game_if_needed(
                game_engine.board, target_mode, player_color, game_saved
            )

        if game_state == "PLAYING" and (show_eval or show_lines):
            engine_ref = active_bot.engine if active_bot and getattr(active_bot, "engine", None) else None
            if engine_ref:
                current_fen = game_engine.board.fen()
                if current_fen != analysis_cache["fen"]:
                    e_score, t_lines = get_stockfish_analysis(engine_ref, game_engine.board)
                    analysis_cache["fen"] = current_fen
                    analysis_cache["eval"] = e_score
                    analysis_cache["lines"] = t_lines
                eval_score = analysis_cache["eval"]
                top_lines = analysis_cache["lines"]
            else:
                eval_score = evaluate_board_score(game_engine.board)
                top_lines = analyze_top_lines(game_engine.board, top_n=3) if show_lines else []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("[DEBUG GUI]: Pygame QUIT event received. Exiting loop...")
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                print(f"[DEBUG GUI]: Mouse click registered at position {pos} in state '{game_state}'")

                if game_state == "MAIN_MENU":
                    (
                        human_btn,
                        engine_btn,
                        q_btn,
                    ) = draw_main_menu(screen, title_font, ui_font, menu_message)

                    if human_btn.collidepoint(pos):
                        target_mode = "HUMAN_BOT"
                        game_state = "LEVEL_MENU"
                        print("[DEBUG GUI]: Main Menu -> Selected Mode: HUMAN_BOT")
                    elif engine_btn.collidepoint(pos):
                        target_mode = "ENGINE_BOT"
                        game_state = "LEVEL_MENU"
                        print("[DEBUG GUI]: Main Menu -> Selected Mode: ENGINE_BOT")
                    elif q_btn.collidepoint(pos):
                        print("[DEBUG GUI]: Main Menu -> Quit selected.")
                        running = False

                elif game_state == "LEVEL_MENU":
                    level_buttons, back_btn, q_btn = draw_level_menu(
                        screen, title_font, ui_font, target_mode
                    )

                    if back_btn.collidepoint(pos):
                        print("[DEBUG GUI]: Level Menu -> Navigating Back to MAIN_MENU")
                        game_state = "MAIN_MENU"
                    elif q_btn.collidepoint(pos):
                        print("[DEBUG GUI]: Level Menu -> Quit selected.")
                        running = False
                    else:
                        for btn_rect, lvl in level_buttons:
                            if btn_rect.collidepoint(pos):
                                selected_level = lvl
                                print(f"[DEBUG GUI]: Level Menu -> Selected Level {selected_level} for mode '{target_mode}'")
                                if active_bot:
                                    try:
                                        print("[DEBUG GUI]: Closing existing bot engine instance...")
                                        active_bot.close()
                                    except Exception as e:
                                        print(f"[DEBUG GUI]: Error closing active bot: {e}")
                                    active_bot = None

                                if target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
                                    try:
                                        active_bot = m121.create_bot(
                                            target_mode, selected_level, STOCKFISH_PATH
                                        )
                                    except Exception as e:
                                        print(f"[DEBUG GUI]: Failed to create bot instance: {e}")
                                        active_bot = None

                                (
                                    current_puzzle,
                                    puzzle_step,
                                    status_text,
                                ) = reset_session_state(
                                    target_mode, selected_level, game_engine
                                )

                                selected_sq = ()
                                player_clicks = []
                                bot_move_pending = False
                                game_saved = False
                                game_state = "PLAYING"
                                break

                elif game_state == "PLAYING":
                    x, y = pos

                    if x < BOARD_SIZE:
                        if game_engine.board.is_game_over():
                            print("[DEBUG GUI]: Click on board ignored -> Game is over.")
                            continue

                        if target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
                            if game_engine.board.turn != player_color or bot_move_pending:
                                print("[DEBUG GUI]: Click on board ignored -> Waiting for bot turn.")
                                continue

                        col = x // SQ_SIZE
                        row = y // SQ_SIZE

                        if not (0 <= row < DIMENSION and 0 <= col < DIMENSION):
                            print(f"[DEBUG GUI]: Click ignored -> row/col out of bounds ({row}, {col})")
                            continue

                        sq = (row, col)

                        if selected_sq == sq:
                            print(f"[DEBUG GUI]: Square {sq} deselected.")
                            selected_sq = ()
                            player_clicks = []
                        else:
                            selected_sq = sq
                            player_clicks.append(selected_sq)
                            print(f"[DEBUG GUI]: Square {sq} selected. Current clicks sequence: {player_clicks}")

                        if len(player_clicks) == 2:
                            from_sq = grid_to_square(
                                player_clicks[0][0], player_clicks[0][1]
                            )
                            to_sq = grid_to_square(
                                player_clicks[1][0], player_clicks[1][1]
                            )
                            uci_attempt = from_sq + to_sq
                            print(f"[DEBUG GUI]: Attempting board move from clicks: {uci_attempt}")

                            move_obj = resolve_move(game_engine.board, uci_attempt)
                            if move_obj and move_obj in game_engine.board.legal_moves:
                                (
                                    ok,
                                    puzzle_step,
                                    status_text,
                                ) = handle_player_move(
                                    game_engine.board,
                                    move_obj,
                                    target_mode,
                                    puzzle_step,
                                )

                                if ok and target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
                                    if not game_engine.board.is_game_over():
                                        bot_move_pending = True
                                        bot_think_ticks = 0
                                        print("[DEBUG GUI]: Player move executed. Triggering bot turn sequence.")

                            selected_sq = ()
                            player_clicks = []

                    else:
                        (
                            reset_btn,
                            undo_btn,
                            eval_toggle_btn,
                            lines_toggle_btn,
                            menu_btn,
                            q_btn,
                        ) = draw_sidebar(
                            screen,
                            ui_font,
                            small_font,
                            eval_score,
                            status_text,
                            show_eval,
                            show_lines,
                            top_lines,
                        )

                        if reset_btn.collidepoint(pos):
                            print("[DEBUG GUI]: Sidebar -> Reset Game button clicked.")
                            (
                                current_puzzle,
                                puzzle_step,
                                status_text,
                            ) = reset_session_state(
                                target_mode, selected_level, game_engine
                            )
                            selected_sq = ()
                            player_clicks = []
                            bot_move_pending = False
                            game_saved = False

                        elif undo_btn.collidepoint(pos):
                            print("[DEBUG GUI]: Sidebar -> Undo Move button clicked.")
                            if target_mode in ("HUMAN_BOT", "ENGINE_BOT"):
                                if len(game_engine.board.move_stack) >= 2:
                                    game_engine.board.pop()
                                    game_engine.board.pop()
                                    print("[DEBUG GUI]: Undid player move and bot move.")
                                elif len(game_engine.board.move_stack) == 1:
                                    game_engine.board.pop()
                                    print("[DEBUG GUI]: Undid single ply move.")
                                bot_move_pending = False
                                status_text = "Move Undone"
                        
                                  
                        elif eval_toggle_btn.collidepoint(pos):
                            show_eval = not show_eval
                            print(f"[DEBUG GUI]: Eval display toggled -> {show_eval}")

                        elif lines_toggle_btn.collidepoint(pos):
                            show_lines = not show_lines
                            print(f"[DEBUG GUI]: Engine lines display toggled -> {show_lines}")

                        elif menu_btn.collidepoint(pos):
                            print("[DEBUG GUI]: Sidebar -> Main Menu button clicked.")
                            if active_bot:
                                try:
                                    active_bot.close()
                                except Exception as e:
                                    print(f"[DEBUG GUI]: Error closing active bot on menu exit: {e}")
                                active_bot = None
                            game_state = "MAIN_MENU"

                        elif q_btn.collidepoint(pos):
                            print("[DEBUG GUI]: Sidebar -> Quit Game button clicked.")
                            running = False

        if game_state == "PLAYING" and bot_move_pending and active_bot:
            bot_think_ticks += 1
            if bot_think_ticks > 10:
                print(f"[DEBUG GUI]: Requesting bot move (Tick threshold reached)...")
                bot_move = active_bot.get_move(game_engine.board, limit_time=0.2)
                if bot_move and bot_move in game_engine.board.legal_moves:
                    game_engine.board.push(bot_move)
                    print(f"[DEBUG GUI]: Bot executed move: {bot_move.uci()}")
                    if game_engine.board.is_checkmate():
                        status_text = "Checkmate!"
                    elif game_engine.board.is_check():
                        status_text = "Check!"
                    else:
                        status_text = (
                            "Black's Turn" if game_engine.board.turn == chess.BLACK else "White's Turn"
                        )
                bot_move_pending = False

        screen.fill(SIDEBAR_BG)
        if game_state == "MAIN_MENU":
            draw_main_menu(screen, title_font, ui_font, menu_message)
        elif game_state == "LEVEL_MENU":
            draw_level_menu(screen, title_font, ui_font, target_mode)
        elif game_state == "PLAYING":
            for r in range(DIMENSION):
                for c in range(DIMENSION):
                    color = LIGHT_SQ if (r + c) % 2 == 0 else DARK_SQ
                    pygame.draw.rect(screen, color, pygame.Rect(c * SQ_SIZE, r * SQ_SIZE, SQ_SIZE, SQ_SIZE))

            highlight_selected_square(screen, selected_sq)
            draw_pieces(screen, piece_font)
            draw_sidebar(
                screen, ui_font, small_font, eval_score, status_text, show_eval, show_lines, top_lines, )
            

        pygame.display.flip()
        clock.tick(30)

    print("[DEBUG GUI]: Shutting down application...")
    if active_bot:
        try:
            active_bot.close()
        except Exception as e:
            print(f"[DEBUG GUI]: Error during final bot cleanup: {e}")

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()