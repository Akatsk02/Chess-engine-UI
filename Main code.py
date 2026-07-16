import chess
board = chess.Board()
Result = None
print("Starting position:")
print(board)
while not board.is_game_over():
    player_move = input("\nEnter your move in UCI format (e.g., e2e4) /"
    "and type q to quit: ").strip()
    if player_move == 'q':
        print("\nGame ended by user.")
        Result="Game aborted (match inconclusive)"
        break
    try:
        board.push_uci(player_move)
        print("\nUpdated Board:")
        print(board)
    except ValueError:
        print("Invalid or illegal move! Please try again.")
print("\nGame over!")
if Result is None:
    Result = board.result()
print("Result:", Result)
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


