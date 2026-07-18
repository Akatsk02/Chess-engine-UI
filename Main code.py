#im going to add both engine-like bot and human like bot. this is because
#the human bot uses the Custom Multi-PV approach.
#<multi-PV(multiple parallel voices) approach is a technique used in 
#programming weak chess bots by making stockfish analyze the board and
#return top 3 best moves. Then i assign custom weights to each of those
# moves based on the user's chosen difficulty.
#example weight: Level(2):[0.35, 0.40, 0.25](approximate numbers)>
#this means that the bot will play like a natural human, make mistakes 
#in volatile and critical postions and reward the user for finding
#the right tactics to punish the blunder by the bot.
#Now the engine like bot uses a simpler approach: it is made by using 
#stockfish's built in  UCI(Universal Chess Interface) engine.
#it is weakened by:
#Depth limiting: Ex: at low levels it limited to around 2-3 piles
#Scholastic Noise: this simply is a command to the bot that makes it
#purposefully play sub-Par moves at times. There are many types,
#but the one that official stockfish source code uses is called
#scholastic noise or random bias.
#this basically uses push to make stockfish play subpar moves. The push of 
# stockfish is calculated using the formulae:

#PUSH=(weakness*(topscore-candidate score)+delta*(rng.rand()<mod>weakness))/128
#Combined score=candidatescore + PUSH

#DEFINITIONS:
#Push:handicap that increases the Combined score of weaker moves so they 
# are played instead 
#Weakness:handicap scaling factor based on user's chosen skill level
# (level is between 0 to 19).[Weakness=(120-2)*level]
#Candidate score: score of how good stockfish thinks a move is. 
# (in centipawns)
#top score: candidate score of the move that stockfish think is best
#topscore-candidatescore:represents how much worse the candidate move
# is compared to the best move. 
#delta:evaluation difference between the best and worst move in the 
#candidiate pool.serves as a scaling boundary for the random noise.
#% weakness: The modulo operator caps the random integer to a
#range between 0 and (weakness - 1).

#formula of Push contains two disinct parts:

#deterministic term: [weakness*(topscore-candidate score)]
#This term naturally favors moves that are already close to the best move.
# If a candidate move is a massive blunder, the gap 
# (topScore - candidateScore) is huge. Multiplying it by weakness makes
# the push massive.This makes sure that even on easy levels stockfish
#makes less basic mistakes instead of throwing its queen away every 
#other move. 

#Scholastic term: [delta*(rng.rand()<mod>weakness)]
#This term delivers purely random noise.If high enough, this can push a
#random very weak blunder to be played my engine.
#The point of this is to lead to chaotic and catastrophic blunders at a
#low level which brings stockfish down to beginner level and somewhat
#simulates the dubiousness of low-level human gameplay.Meanwhile, At a 
#high level, this term is almost negligible making stockfish make almost
#no critical blunders while still allowing it to make slight positional
#inaccuracies

#the point of letting the user play the engine like bot (even though it 
#plays unnatural moves with obvious blunders) is because playing against
#engine teaches the user to play consistently and hold positions against
#a stockfish-like opponent using only the advantage gathered from the 
#occasional blunders that the engine makes without getting crushed by 
#a wave of perfect moves.when playing against this bot even small 
#positional errors are often punished. This forces the user to stop
#"hope chess" , be vigilant and maintain high focus throughout the game.

#Now the following chunk of code sets up the two bots using the OOP 
#approach featuring a parent chess engine class and two child classes.

import random
import chess
import chess.engine
class BaseChessEngine:
    """
    general class that handles Stockfish initialization 
    and closing for both bots
    """
    def __init__(self, stockfish_path: str):
        self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    def get_move(self, board: chess.Board, limit_time: float) -> chess.Move:
        """Each bot will have their own version of this function but its
        written here to make sure any child bot uses the same syntax
         for this function regardless of how it actually calculates the 
          move.  """
        raise NotImplementedError # prevents any attempt to directly use
        # the function as it is in the parentclass.

    def close(self):
        self.engine.quit()

class DefaultStockfishBot(BaseChessEngine):
    def __init__(self, stockfish_path: str, level: int = 10):
        super().__init__(stockfish_path) #pushes stockfish_path to parent
        
        if not (0 <= level <= 20):
            raise ValueError("Difficulty must be between 0 and 20.")
            
        self.level = level
        
        # Passes the configuration setting to Stockfish via the UCI protocol
        self.engine.configure({"Skill Level": self.level})

    def get_move(self, board: chess.Board, limit_time: float = 0.1) -> chess.Move:
        result = self.engine.play(board, chess.engine.Limit(time=limit_time))
        return result.move


class MultiPVStockfishBot(BaseChessEngine):
    """Bypasses Stockfish's native engine choices to pull the top 3 candidate moves,
    then uses custom probability weights to pick a move"""
    def __init__(self, stockfish_path: str, level: int = 2):
        # Call the parent class constructor to wake up the engine process
        super().__init__(stockfish_path)

        if not (0 <= level <= 20):
            raise ValueError("Difficulty must be between 0 and 20.")

        self.level = level

        x = level / 20.0

        p1 = 0.20 + (0.80 * x)
        remainder = 1.0 - p1
        p2 = remainder * 0.60
        p3 = remainder * 0.40

        self.weights = [p1, p2, p3]

    def get_move(self, board: chess.Board, limit_time: float = 0.3) -> chess.Move:
        """
        Analyzes the position with a MultiPV depth of 3, parses the choices,
        and makes a weighted random selection.
        """
        analysis = self.engine.analyse(
            board,
            chess.engine.Limit(time=limit_time),
            multipv=3,
        )
        candidate_moves = []
        for entry in analysis:
            if "pv" in entry and len(entry["pv"]) > 0:  # edgecase guard
                candidate_moves.append(entry["pv"][0])

        # When the game does not yield valid moves
        if not candidate_moves:
            return None

        weights = self.weights

        # for when the board has less than three moves available
        if len(candidate_moves) < len(weights):
            weights = weights[: len(candidate_moves)]

        # fix the trimmed weights so it still adds to 1
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]

        chosen_move = random.choices(candidate_moves, weights=weights, k=1)[0]
        return chosen_move
    
    #interactive interface
if __name__ == "__main__":
    STOCKFISH_PATH = "./stockfish-windows-x86-64-avx2.exe" 
    
    print("      WELCOME TO THE CHESS ENGINE      ")
    print("Select your opponent:")
    print("[1] Engine-like Bot (Levels 0-20)")
    print("[2] Human-Like Bot (Levels 0-20)")
    print("---------------------------------------")
    
    while True:
        try:
            choice = int(input("Enter bot choice (1 or 2): ").strip())
            if choice in [1, 2]:
                break
            print("Invalid selection. Please enter 1 or 2.")
        except ValueError:
            print("Please enter a valid number.")

    while True:
        try:
            user_level = int(input("Choose engine level (0 to 20): ").strip())
            if 0 <= user_level <= 20:
                break
            print("Error: Level must be strictly between 0 and 20.")
        except ValueError:
            print("Please enter a valid integer.")

    print("Choose your side:")
    print("[W] White")
    print("[B] Black")
    print("[R] Random")
    while True:
        color = input("Enter color choice (W, B, or R): ").strip().upper()
        if color in ['W', 'B', 'R']:
            break
        print("Invalid choice. Please enter W, B, or R.")

    # Determine final side assignment
    if color== 'R':
        player_color = random.choice([chess.WHITE, chess.BLACK])
    elif color == 'W':
        player_color = chess.WHITE
    else:
        player_color = chess.BLACK
            
    if choice == 1:
        bot = DefaultStockfishBot(STOCKFISH_PATH, level=user_level)
        print(f"\n[System] Initialized Default Engine Bot at Level {user_level}!")
    else:
        bot = MultiPVStockfishBot(STOCKFISH_PATH, level=user_level)
        print(f"\n[System] Initialized Human-Like Bot at Level {user_level}!")

    board = chess.Board()
    Result = None
    
    print("\nStarting position:")
    print(board)
    
    while not board.is_game_over():
        if board.turn == player_color:
            player_move = input("\nEnter your move in UCI format (e.g., e2e4) / or type q to quit: ").strip()
            if player_move == 'q':
                print("\nGame ended by user.")
                Result = "Game aborted (match inconclusive)"
                break
            try:
                board.push_uci(player_move)
                print("\nUpdated Board:")
                print(board)
            except ValueError:
                print("Invalid or illegal move! Please try again.")
                
        else:
            print("\nBot is thinking...")
            bot_move = bot.get_move(board, limit_time=0.2)
            if bot_move:
                board.push(bot_move)
                print(f"\nBot played: {bot_move}")
                print("\nUpdated Board:")
                print(board)
            else:
                print("Engine failed to generate a move.")
                break
                
    print("\nGame over!")
    if Result is None:
        Result = board.result()
    print("Result:", Result)
    
    bot.close()
