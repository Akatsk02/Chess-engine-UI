import random
import chess
import os
import chess.engine

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STOCKFISH_NAME = "stockfish-windows-x86-64-avx2.exe"

def get_script_dir():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    print(f"[DEBUG m121]: Executing get_script_dir() -> {dir_path}")
    return dir_path


def resolve_stockfish_path():
    print("[DEBUG m121]: Resolving Stockfish path...")
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path and os.path.isfile(env_path):
        print(f"[DEBUG m121]: Found Stockfish via STOCKFISH_PATH environment variable: {env_path}")
        return env_path

    bundled_path = os.path.join(SCRIPT_DIR, DEFAULT_STOCKFISH_NAME)
    if os.path.isfile(bundled_path):
        print(f"[DEBUG m121]: Found bundled Stockfish executable: {bundled_path}")
        return bundled_path

    possible_names = [
        "stockfish-windows-x86-64-avx2.exe",
        "stockfish.exe",
        "stockfish",
    ]
    for name in possible_names:
        candidate = os.path.join(SCRIPT_DIR, name)
        if os.path.isfile(candidate):
            print(f"[DEBUG m121]: Found candidate Stockfish binary in script directory: {candidate}")
            return candidate

    print(f"[DEBUG m121]: Stockfish executable not found in candidate paths. Defaulting to: {DEFAULT_STOCKFISH_NAME}")
    return DEFAULT_STOCKFISH_NAME


class BaseChessBot:
    def __init__(self, level=1):
        self.level = max(1, min(20, level))
        print(f"[DEBUG m121]: BaseChessBot initialized with level: {self.level}")
    def get_move(self, py_board, limit_time=3):
        print("[DEBUG m121]: BaseChessBot.get_move called.")
        legal_moves = list(py_board.legal_moves)
        if legal_moves:
            chosen_move = random.choice(legal_moves)
            print(f"[DEBUG m121]: BaseChessBot selecting random legal move: {chosen_move.uci()}")
            return chosen_move
        print("[DEBUG m121]: BaseChessBot found no legal moves.")
        return None

    def close(self):
        print("[DEBUG m121]: BaseChessBot close requested.")
        pass


class StockfishBot(BaseChessBot):
    def __init__(self, level=1, stockfish_path=None):
        super().__init__(level)
        self.engine = None
        self.stockfish_path = stockfish_path or resolve_stockfish_path()
        print(f"[DEBUG m121]: Attempting to initialize Stockfish engine from: {self.stockfish_path}")
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            print("[DEBUG m121]: Successfully launched Stockfish UCI process.")
        except Exception as e:
            print(f"[DEBUG m121]: ERROR launching Stockfish at '{self.stockfish_path}': {e}")
            print("[DEBUG m121]: Fallback to random legal move generator will be used.")

    def close(self):
        if self.engine:
            try:
                self.engine.quit()
                print("[DEBUG m121]: Stockfish process quit cleanly.")
            except Exception as e:
                print(f"[DEBUG m121]: Error quitting Stockfish process: {e}")


class HumanLikeBot(StockfishBot):
    """
    A human-like chess bot built on a custom Multi-PV move-selection
    formula, instead of relying on Stockfish's own built-in "Skill Level"
    / UCI_Elo weakening.

    ------------------------------------------------------------------------
    WHY NOT JUST USE UCI_Elo / UCI_LimitStrength?
    ------------------------------------------------------------------------
    Stockfish's built-in strength limiter works by (a) clamping its own
    search depth at low levels and (b) adding internal randomness to its
    move ordering. Clamping search depth doesn't make Stockfish play "like
    a human who missed something" -- it makes Stockfish genuinely blind to
    tactics beyond that depth. A human beginner still has pattern
    recognition and won't walk into an obvious one-move trap; a
    depth-limited engine will, because it can't see past its horizon at all.

    This bot instead:
      1. Always searches at FULL depth (SEARCH_DEPTH), so nothing is ever
         missed because of a shallow horizon.
      2. Asks Stockfish for its top MULTIPV candidate moves (not just the
         single best move), each with a real, fully-searched evaluation.
      3. Picks among those candidates using a weighted formula that mixes
         a deterministic "how much worse is this move" term with a random
         "noise" term scaled to the position's own volatility.

    Every "mistake" this bot makes is still a real, sane top-3 candidate
    move -- never a completely blind giveaway.

    ------------------------------------------------------------------------
    THE FORMULA
    ------------------------------------------------------------------------
    For each candidate move i out of the MULTIPV candidates returned by
    Stockfish, with centipawn evaluation score_i (from the perspective of
    the side to move):

        topScore   = max(score_i)              over all candidates
        worstScore = min(score_i)              over all candidates
        delta      = topScore - worstScore     ("volatility" of this position)

        deterministic_i = weakness * (topScore - score_i) / 100
        noise_i          = ( (random_int() % (2*weakness + 1)) - weakness ) * delta / 100
        penalty_i        = deterministic_i + noise_i
    The bot plays the candidate move with the SMALLEST penalty.

    `weakness` is an integer in [0, 100], derived from the bot's level
    (1-20): weakness = 0 means "always pick the objectively best
    candidate"; weakness near 100 means "pick almost randomly among the
    candidate pool."

    ------------------------------------------------------------------------
    WHY delta MATTERS
    ------------------------------------------------------------------------
    delta re-scales the random noise term to the position's own stakes.
    In a sharp position, candidates are far apart in evaluation, so delta
    is large and noise can swing the choice -- like a human panicking in
    a complicated position. In a quiet, near-equal position, candidates
    are close together, delta shrinks toward zero, and so does the noise
    -- the bot won't randomly prefer a move that barely differs from best.

    ------------------------------------------------------------------------
    WHY THE MODULO (%) OPERATOR
    ------------------------------------------------------------------------
    `random_int() % (2*weakness + 1)`, re-centered by subtracting `weakness`,
    folds a large random integer down into a small, bounded, symmetric range
    between -weakness and +weakness. This lets any candidate -- including
    the top move -- get its penalty nudged up or down, not just penalized.
    It mirrors the technique Stockfish's own internal Skill Level
    implementation uses, made symmetric here to model genuine uncertainty
    in a move's quality.
    ------------------------------------------------------------------------
    """

    MAX_MULTIPV = 25   # Widest candidate pool considered, at weakness=100
    SEARCH_DEPTH = 15  # Deep enough that Stockfish never misses tactics.

    def __init__(self, level=1, stockfish_path=None):
        super().__init__(level, stockfish_path)
        # Map level 1-20 onto weakness 100-0 (level 1 = weakest/most human,
        # level 20 = strongest/closest to perfect play).
        # k > 1 keeps weakness elevated longer through low/mid levels,
        # then drops off faster near the top, so mid-level bots still make
        # human-like mistakes instead of sharpening up linearly with level.
        # k = 3.0 is fairly aggressive about it; raise it for an even
        # gentler early game, lower it back toward 1 for a more linear ramp.
        k = 3.40
        self.weakness = round((((20 - self.level) / 19) ** k) * 100)
        print(
            f"[DEBUG m121]: HumanLikeBot instantiated -> Level {self.level}, "
            f"MaxMultiPV {self.MAX_MULTIPV}, Depth {self.SEARCH_DEPTH}"
        )
    def _pool_size(self, num_legal_moves):
        """weakness=0 -> pool of 1 (best move only). weakness=100 -> wide pool
        (up to MAX_POOL or all legal moves, whichever is smaller)."""
        max_pool = min(num_legal_moves, self.MAX_MULTIPV)
        size = 1 + (self.weakness / 100) * (max_pool - 1)
        return max(1, round(size))   
    def get_move(self, py_board, limit_time=10):
        """
        Selects a move using the Multi-PV weighted-penalty formula
        described above. Falls back to a single-best-move engine query,
        and then to a random legal move, if anything about the Multi-PV
        analysis fails (e.g. engine not running).
        """
        if not self.engine:
            print("[DEBUG m121]: HumanLikeBot has no active engine -> random fallback.")
            return super().get_move(py_board, limit_time)

        legal_moves = list(py_board.legal_moves)
        if not legal_moves:
            print("[DEBUG m121]: HumanLikeBot found no legal moves.")
            return None

        try:
            multipv_count = self._pool_size(len(legal_moves))
            print(
                f"[DEBUG m121]: Running Multi-PV analysis "
                f"(depth={self.SEARCH_DEPTH}, multipv={multipv_count})..."
            )
            info_list = self.engine.analyse(
                py_board,
                chess.engine.Limit(depth=self.SEARCH_DEPTH, time=limit_time),
                multipv=multipv_count,
            )

            if isinstance(info_list, dict):
                info_list = [info_list]

            candidates = []
            for info in info_list:
                pv = info.get("pv")
                score = info.get("score")
                if not pv or score is None:
                    continue
                move = pv[0]
                cp = score.pov(py_board.turn).score(mate_score=100000)
                candidates.append((move, cp))
                print(f"[DEBUG m121]: Candidate {move.uci()} -> eval {cp}cp")

            if not candidates:
                print("[DEBUG m121]: Multi-PV returned no usable candidates -> single-move fallback.")
                result = self.engine.play(py_board, chess.engine.Limit(time=limit_time))
                return result.move

            top_score = max(cp for _, cp in candidates)
            worst_score = min(cp for _, cp in candidates)
            delta = top_score - worst_score
            w = self.weakness
            print(f"[DEBUG m121]: topScore={top_score} worstScore={worst_score} delta={delta} w={w}")

            best_move = None
            best_penalty = None

            for move, cp in candidates:
                r = random.getrandbits(32)
                deterministic_term = w * (top_score - cp) / 100
                noise_term = ((r % (2 * w + 1)) - w) * (delta / 100)
                penalty = deterministic_term + noise_term

                print(
                    f"[DEBUG m121]: {move.uci()} | D={deterministic_term} "
                    f"| N={noise_term:.1f} | P={penalty:.1f}"
                )

                if best_penalty is None or penalty < best_penalty:
                    best_penalty = penalty
                    best_move = move

            print(
                f"[DEBUG m121]: HumanLikeBot selected {best_move.uci()} "
                f"(weakness={w}, pool={multipv_count}, delta={delta}, penalty={best_penalty:.1f})"
            )
            return best_move

        except Exception as e:
            print(f"[DEBUG m121]: HumanLikeBot Multi-PV analysis failed: {e} -> fallback.")
            try:
                result = self.engine.play(py_board, chess.engine.Limit(time=limit_time))
                return result.move
            except Exception as e2:
                print(f"[DEBUG m121]: Fallback engine.play also failed: {e2}")
                return super().get_move(py_board, limit_time)


class EngineBot(StockfishBot):
    def __init__(self, level=1, stockfish_path=None):
        super().__init__(level, stockfish_path)

        if self.engine and "UCI_Elo" in self.engine.options:
            elo_option = self.engine.options["UCI_Elo"]
            min_elo, max_elo = elo_option.min, elo_option.max
        else:
            min_elo, max_elo = 1320, 3190  # fallback if engine/option unavailable

        # Scale level 1-20 across the engine's ACTUAL supported Elo range,
        # so level 1 is always the true floor and level 20 the true ceiling
        # instead of a fixed formula that silently clamps at low levels.
        ELO_CEILING_FRACTION = 0.8  # cap how far up the native Elo range levels can reach
        effective_max_elo = min_elo + (max_elo - min_elo) * ELO_CEILING_FRACTION
        self.target_elo = round(min_elo + (effective_max_elo - min_elo) * (self.level - 1) / 19)
        print(f"[DEBUG m121]: EngineBot instantiated -> Target Elo: {self.target_elo}")

    def get_move(self, py_board, limit_time=0.06):
        print(f"[DEBUG m121]: EngineBot calculating move for board turn {'WHITE' if py_board.turn == chess.WHITE else 'BLACK'}...")
        if self.engine:
            try:
                self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": self.target_elo})
                result = self.engine.play(py_board, chess.engine.Limit(time=limit_time))
                print(f"[DEBUG m121]: EngineBot (Elo {self.target_elo}) selected move: {result.move.uci()}")
                return result.move
            except Exception as e:
                print(f"[DEBUG m121]: EngineBot query error: {e}")

        print("[DEBUG m121]: EngineBot falling back to base random choice.")
        return super().get_move(py_board, limit_time)


def create_bot(bot_type, level=1, stockfish_path=None):
    print(f"[DEBUG m121]: Factory create_bot called with type: '{bot_type}', level: {level}")
    if bot_type == "HUMAN_BOT":
        return HumanLikeBot(level=level, stockfish_path=stockfish_path)
    elif bot_type == "ENGINE_BOT":
        return EngineBot(level=level, stockfish_path=stockfish_path)
    print(f"[DEBUG m121]: Unknown bot_type '{bot_type}'. Defaulting to BaseChessBot.")
    return BaseChessBot(level=level)


class ChessBaseEngine:
    def __init__(self):
        self.board = chess.Board()
        print("[DEBUG m121]: ChessBaseEngine initialized with standard starting position FEN.")
